"""API-Football v3 client: rate-limit aware, and every good response is stored raw once.

- A response is "good" only if it is HTTP 200 *and* its `errors` field is empty. API-Football
  reports failures as HTTP 200 with a non-empty `errors` (Review Focus #1); those raise and are
  never stored, so a later run retries them.
- Bodies are cached in `api_raw` by `params_hash`; a stored call is never repeated.
- Limits come from response headers: `X-RateLimit-Remaining` (per minute) pauses until the next
  minute; `x-ratelimit-requests-remaining` (per day) raises `RateLimited` until 00:00 UTC.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
from psycopg.types.json import Jsonb

DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
MAX_IDS_PER_CALL = 20
RETRIES_5XX = 3
MAX_MINUTE_WAITS = 3


class ApiError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_at: datetime):
        super().__init__(f"API-Football daily limit reached; retry at {retry_at.isoformat()}")
        self.retry_at = retry_at


class _MinuteLimited(Exception):
    pass


def params_hash(endpoint: str, params: dict) -> str:
    canonical = json.dumps({str(k): str(v) for k, v in params.items()}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{endpoint.strip('/')}?{canonical}".encode()).hexdigest()


def _next_minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0) + timedelta(minutes=1)


def _next_utc_midnight(t: datetime) -> datetime:
    t = t.astimezone(UTC)
    return t.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _int_header(resp: httpx.Response, name: str) -> int | None:
    value = resp.headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


class ApiFootball:
    def __init__(
        self,
        conn: psycopg.Connection,
        key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._conn = conn
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30.0)
        self._headers = {"x-apisports-key": key}
        self._sleep = sleep
        self._now = now
        self._paused_until: datetime | None = None
        self._daily_retry_at: datetime | None = None

    # --- core -----------------------------------------------------------------------

    def get(self, endpoint: str, params: dict) -> dict:
        """Stored body if this call was made before; otherwise fetch, validate and store."""
        endpoint = endpoint.strip("/")
        h = params_hash(endpoint, params)
        row = self._conn.execute("select body from api_raw where params_hash = %s", (h,)).fetchone()
        if row is not None:
            return row[0]
        body, status = self._fetch(endpoint, params)
        with self._conn.transaction():
            self._conn.execute(
                "insert into api_raw (endpoint, params, params_hash, status_code, body) "
                "values (%s, %s, %s, %s, %s) on conflict (params_hash) do nothing",
                (endpoint, Jsonb({str(k): str(v) for k, v in params.items()}), h, status, Jsonb(body)),
            )
        return body

    def _fetch(self, endpoint: str, params: dict) -> tuple[dict, int]:
        server_errors = 0
        minute_waits = 0
        while True:
            self._wait_for_limits()
            try:
                resp = self._http.get(f"{self._base}/{endpoint}", params=params, headers=self._headers)
            except httpx.TransportError as exc:
                server_errors += 1
                if server_errors > RETRIES_5XX:
                    raise ApiError(f"{endpoint}: {type(exc).__name__}") from None
                self._sleep(2.0 ** (server_errors - 1))
                continue
            self._read_limit_headers(resp)
            if resp.status_code >= 500:
                server_errors += 1
                if server_errors > RETRIES_5XX:
                    raise ApiError(f"{endpoint}: HTTP {resp.status_code} after {RETRIES_5XX} retries")
                self._sleep(2.0 ** (server_errors - 1))
                continue
            try:
                return self._validate(endpoint, resp), resp.status_code
            except _MinuteLimited:
                minute_waits += 1
                if minute_waits > MAX_MINUTE_WAITS:
                    raise ApiError(f"{endpoint}: still per-minute limited after {MAX_MINUTE_WAITS} waits") from None
                self._paused_until = _next_minute(self._now())

    def _wait_for_limits(self) -> None:
        if self._daily_retry_at is not None:
            if self._now() < self._daily_retry_at:
                raise RateLimited(self._daily_retry_at)
            self._daily_retry_at = None
        if self._paused_until is not None:
            wait = (self._paused_until - self._now()).total_seconds()
            if wait > 0:
                self._sleep(wait)
            self._paused_until = None

    def _read_limit_headers(self, resp: httpx.Response) -> None:
        if _int_header(resp, "X-RateLimit-Remaining") == 0:
            self._paused_until = _next_minute(self._now())
        if _int_header(resp, "x-ratelimit-requests-remaining") == 0:
            self._daily_retry_at = _next_utc_midnight(self._now())

    def _validate(self, endpoint: str, resp: httpx.Response) -> dict:
        if resp.status_code == 429:
            raise _MinuteLimited()
        if resp.status_code != 200:
            raise ApiError(f"{endpoint}: HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            raise ApiError(f"{endpoint}: response is not JSON") from None
        if not isinstance(body, dict):
            raise ApiError(f"{endpoint}: unexpected body type {type(body).__name__}")
        errors = body.get("errors")
        if errors:
            keys = set(errors) if isinstance(errors, dict) else set()
            if "requests" in keys:
                self._daily_retry_at = _next_utc_midnight(self._now())
                raise RateLimited(self._daily_retry_at)
            if "rateLimit" in keys:
                raise _MinuteLimited()
            summary = "; ".join(f"{k}: {v}" for k, v in errors.items()) if isinstance(errors, dict) else str(errors)
            raise ApiError(f"{endpoint}: API error: {summary}")
        if "response" not in body:
            raise ApiError(f"{endpoint}: body has no 'response' field")
        return body

    # --- endpoints ------------------------------------------------------------------

    def _response(self, endpoint: str, params: dict) -> list[Any]:
        return self.get(endpoint, params)["response"]

    def fixtures_for_season(self, league: int, season: int) -> list[dict]:
        return self._response("fixtures", {"league": league, "season": season})

    def fixtures_by_ids(self, ids: list[int]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ids), MAX_IDS_PER_CALL):
            chunk = ids[i : i + MAX_IDS_PER_CALL]
            out.extend(self._response("fixtures", {"ids": "-".join(str(x) for x in chunk)}))
        return out

    def squad(self, team: int) -> list[dict]:
        return self._response("players/squads", {"team": team})

    def coaches(self, team: int) -> list[dict]:
        return self._response("coachs", {"team": team})

    def venue(self, venue_id: int) -> list[dict]:
        return self._response("venues", {"id": venue_id})

    def player(self, player_id: int, season: int) -> list[dict]:
        return self._response("players", {"id": player_id, "season": season})
