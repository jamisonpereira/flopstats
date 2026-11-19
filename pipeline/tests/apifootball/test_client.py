import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from flopstats.apifootball.client import ApiError, ApiFootball, RateLimited

BASE = "https://v3.football.api-sports.io"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "apifootball"
KEY = "af-test-key"


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeClock:
    def __init__(self, start):
        self.t = start
        self.sleeps: list[float] = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 11, 19, 12, 0, 30, tzinfo=UTC))


@pytest.fixture
def api(db, clock):
    return ApiFootball(db, KEY, sleep=clock.sleep, now=clock.now)


def ok(body=None, minute="299", day="7400"):
    return httpx.Response(
        200,
        json=body if body is not None else {"errors": [], "response": []},
        headers={"X-RateLimit-Remaining": minute, "x-ratelimit-requests-remaining": day},
    )


def raw_count(db):
    return db.execute("select count(*) from api_raw").fetchone()[0]


@respx.mock
def test_get_returns_cached_raw_without_http(api, db):
    route = respx.get(f"{BASE}/fixtures").mock(return_value=ok(load("fixtures_season.json")))
    first = api.get("fixtures", {"league": 39, "season": 2024})
    assert route.call_count == 1
    assert route.calls[0].request.headers["x-apisports-key"] == KEY
    second = api.get("fixtures", {"season": "2024", "league": "39"})  # same params, other order/type
    assert route.call_count == 1
    assert first == second
    assert raw_count(db) == 1


@respx.mock
def test_errors_field_with_200_is_failure(api, db):
    respx.get(f"{BASE}/fixtures").mock(return_value=ok(load("error_token.json")))
    with pytest.raises(ApiError) as exc:
        api.get("fixtures", {"league": 39, "season": 2024})
    assert "token" in str(exc.value)
    assert raw_count(db) == 0


@respx.mock
def test_pauses_when_minute_remaining_zero(api, clock):
    respx.get(f"{BASE}/venues").mock(side_effect=[ok(minute="0"), ok()])
    api.get("venues", {"id": 1})
    assert clock.sleeps == []
    api.get("venues", {"id": 2})
    assert clock.sleeps == [30.0]  # 12:00:30 -> 12:01:00


@respx.mock
def test_daily_remaining_zero_raises_rate_limited(api, db):
    route = respx.get(f"{BASE}/venues").mock(return_value=ok(day="0"))
    api.get("venues", {"id": 1})  # this response is good and is stored
    with pytest.raises(RateLimited) as exc:
        api.get("venues", {"id": 2})
    assert route.call_count == 1
    assert exc.value.retry_at == datetime(2026, 11, 20, tzinfo=UTC)
    assert raw_count(db) == 1


@respx.mock
def test_daily_limit_error_body_raises_rate_limited(api, db):
    respx.get(f"{BASE}/venues").mock(
        return_value=ok({"errors": {"requests": "You have reached the request limit for the day"}, "response": []})
    )
    with pytest.raises(RateLimited):
        api.get("venues", {"id": 1})
    assert raw_count(db) == 0


@respx.mock
def test_minute_limit_error_body_waits_and_retries(api, clock):
    respx.get(f"{BASE}/venues").mock(
        side_effect=[ok({"errors": {"rateLimit": "Too many requests"}, "response": []}), ok()]
    )
    api.get("venues", {"id": 1})
    assert clock.sleeps == [30.0]


@respx.mock
def test_retries_5xx_then_succeeds(api, clock):
    route = respx.get(f"{BASE}/venues").mock(
        side_effect=[httpx.Response(502), httpx.Response(503), ok()]
    )
    api.get("venues", {"id": 1})
    assert route.call_count == 3
    assert len(clock.sleeps) == 2


@respx.mock
def test_gives_up_after_3_retries_and_stores_nothing(api, db):
    route = respx.get(f"{BASE}/venues").mock(return_value=httpx.Response(500))
    with pytest.raises(ApiError):
        api.get("venues", {"id": 1})
    assert route.call_count == 4  # first try + 3 retries
    assert raw_count(db) == 0


@respx.mock
def test_fixtures_by_ids_chunks_by_20(api):
    route = respx.get(f"{BASE}/fixtures").mock(
        side_effect=lambda req: ok(
            {"errors": [], "response": [{"fixture": {"id": int(i)}} for i in req.url.params["ids"].split("-")]}
        )
    )
    ids = list(range(1, 46))
    out = api.fixtures_by_ids(ids)
    sent = [r.request.url.params["ids"].split("-") for r in route.calls]
    assert [len(s) for s in sent] == [20, 20, 5]
    assert [f["fixture"]["id"] for f in out] == ids


@respx.mock
def test_helpers_hit_expected_endpoints(api):
    respx.get(f"{BASE}/fixtures", params={"league": "39", "season": "2024"}).mock(
        return_value=ok(load("fixtures_season.json"))
    )
    respx.get(f"{BASE}/players/squads", params={"team": "33"}).mock(return_value=ok({"errors": [], "response": [{"team": {"id": 33}}]}))
    respx.get(f"{BASE}/coachs", params={"team": "33"}).mock(return_value=ok({"errors": [], "response": [{"id": 1}]}))
    respx.get(f"{BASE}/venues", params={"id": "556"}).mock(return_value=ok({"errors": [], "response": [{"id": 556}]}))
    respx.get(f"{BASE}/players", params={"id": "276", "season": "2024"}).mock(return_value=ok({"errors": [], "response": [{"player": {"id": 276}}]}))
    assert len(api.fixtures_for_season(39, 2024)) == 2
    assert api.squad(33) == [{"team": {"id": 33}}]
    assert api.coaches(33) == [{"id": 1}]
    assert api.venue(556) == [{"id": 556}]
    assert api.player(276, 2024) == [{"player": {"id": 276}}]
