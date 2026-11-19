"""`verify-setup`: one cheap call per service. Never prints secret values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from flopstats.config import Settings
from flopstats.db import connect as db_connect

APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 15.0


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    skipped: bool = False


class _Missing(Exception):
    pass


def _require(value, env_name: str):
    if value is None:
        raise _Missing(f"{env_name} not set")
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


def _redact(text: str, secrets: list[str]) -> str:
    for s in sorted(secrets, key=len, reverse=True):
        text = text.replace(s, "***")
    return text


def _http_error(resp: httpx.Response) -> str | None:
    if resp.status_code >= 400:
        return f"HTTP {resp.status_code}"
    return None


def _check_api_football(s: Settings, client: httpx.Client) -> str:
    key = _require(s.apifootball_key, "APIFOOTBALL_KEY")
    resp = client.get(f"{APIFOOTBALL_BASE}/status", headers={"x-apisports-key": key})
    if err := _http_error(resp):
        raise RuntimeError(err)
    body = resp.json()
    # API-Football reports errors as HTTP 200 with a non-empty `errors` field.
    if body.get("errors"):
        errors = body["errors"]
        summary = "; ".join(f"{k}: {v}" for k, v in errors.items()) if isinstance(errors, dict) else str(errors)
        raise RuntimeError(f"API error: {summary}")
    r = body.get("response") or {}
    plan = (r.get("subscription") or {}).get("plan", "?")
    req = r.get("requests") or {}
    return f"plan {plan}, {req.get('current', '?')}/{req.get('limit_day', '?')} requests today"


def _check_db(s: Settings, connect: Callable) -> str:
    _require(s.database_url, "DATABASE_URL")
    conn = connect(s)
    try:
        row = conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
    if not row or row[0] != 1:
        raise RuntimeError("SELECT 1 returned unexpected result")
    return "SELECT 1"


def _check_storage(s: Settings, client: httpx.Client) -> str:
    url = _require(s.supabase_url, "SUPABASE_URL")
    key = _require(s.supabase_service_key, "SUPABASE_SERVICE_KEY")
    resp = client.get(
        f"{url.rstrip('/')}/storage/v1/bucket",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    if err := _http_error(resp):
        raise RuntimeError(err)
    return f"{len(resp.json())} bucket(s)"


def _check_gemini(s: Settings, client: httpx.Client) -> str:
    key = _require(s.gemini_key, "GEMINI_KEY")
    resp = client.get(
        f"{GEMINI_BASE}/models", params={"pageSize": 1}, headers={"x-goog-api-key": key}
    )
    if err := _http_error(resp):
        raise RuntimeError(err)
    return "key accepted (models listed)"


def check_all(settings: Settings, *, connect: Callable = db_connect) -> list[CheckResult]:
    secrets = settings.secret_values()
    results: list[CheckResult] = []

    def run(name: str, fn: Callable[[], str]) -> None:
        try:
            results.append(CheckResult(name, True, _redact(fn(), secrets)))
        except Exception as exc:  # noqa: BLE001 - every failure becomes a FAIL line
            msg = str(exc) if isinstance(exc, (_Missing, RuntimeError)) else f"{type(exc).__name__}: {exc}"
            results.append(CheckResult(name, False, _redact(msg, secrets)))

    with httpx.Client(timeout=TIMEOUT) as client:
        run("api-football", lambda: _check_api_football(settings, client))
        run("supabase-db", lambda: _check_db(settings, connect))
        run("supabase-storage", lambda: _check_storage(settings, client))
        run("gemini", lambda: _check_gemini(settings, client))
    # Task 9 provides footballia.login(); until then the check is skipped.
    results.append(CheckResult("footballia-login", True, "skipped (login() arrives in Task 9)", skipped=True))
    return results
