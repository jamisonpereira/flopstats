import httpx
import respx
from typer.testing import CliRunner

from flopstats import cli

BASE = "https://v3.football.api-sports.io"


def _ok(body):
    return httpx.Response(200, json=body, headers={"X-RateLimit-Remaining": "299", "x-ratelimit-requests-remaining": "7000"})


@respx.mock
def test_fetch_season_stores_season_list_and_fixture_batches(db, settings, monkeypatch):
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "_connect", lambda s: db)
    season = {"errors": [], "response": [{"fixture": {"id": i}} for i in range(1, 26)]}
    respx.get(f"{BASE}/fixtures", params={"league": "39", "season": "2024"}).mock(return_value=_ok(season))
    batches = respx.get(f"{BASE}/fixtures").mock(
        side_effect=lambda r: _ok({"errors": [], "response": [{"fixture": {"id": int(i)}} for i in r.url.params["ids"].split("-")]})
    )
    result = CliRunner().invoke(cli.app, ["api", "fetch-season", "--league", "39", "--season", "2024"])
    assert result.exit_code == 0, result.output
    assert batches.call_count == 2  # 25 fixtures -> 20 + 5
    assert db.execute("select count(*) from api_raw").fetchone()[0] == 3
    assert "25 fixtures" in result.output
    assert settings.apifootball_key.get_secret_value() not in result.output
