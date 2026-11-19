from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from flopstats import cli
from flopstats.footballia.catalog import CatalogEntry


def _entries():
    return [CatalogEntry(url=f"https://footballia.eu/matches/m{i}", home="A", away="B", date=date(2026, 11, i),
                         competition="Premier League", season="2026-2027") for i in (1, 2)]


def test_watch_records_first_seen(db, settings, monkeypatch):
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "_connect", lambda s: db)
    seen = {}

    def fake_list(client, league, season, **kw):
        seen["args"] = (league, season)
        return _entries()

    monkeypatch.setattr("flopstats.footballia.catalog.list_season", fake_list)
    r1 = CliRunner().invoke(cli.app, ["footballia", "watch", "--season", "2026-2027"])
    r2 = CliRunner().invoke(cli.app, ["footballia", "watch", "--season", "2026-2027"])
    assert r1.exit_code == 0, r1.output
    assert seen["args"] == ("premier-league", "2026-2027")
    assert "2 listed, 2 new" in r1.output and "2 listed, 0 new" in r2.output


def test_watch_defaults_to_current_season():
    assert cli._current_season(date(2026, 11, 19)) == "2026-2027"
    assert cli._current_season(date(2027, 3, 1)) == "2026-2027"
    assert cli._current_season(date(2027, 7, 31)) == "2026-2027"
    assert cli._current_season(date(2027, 8, 1)) == "2027-2028"


def test_fetch_downloads_with_session(settings, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    calls = {}
    monkeypatch.setattr("flopstats.footballia.download.session", lambda u, p: calls.setdefault("session", object()))

    def fake_fetch(url, dest, *, client):
        calls["fetch"] = (url, dest, client)
        out = Path(dest) / "m.mp4"
        return out

    monkeypatch.setattr("flopstats.footballia.download.fetch_match", fake_fetch)
    monkeypatch.setattr("flopstats.footballia.download.probe_duration_s", lambda p: 5700.0)
    r = CliRunner().invoke(cli.app, ["footballia", "fetch", "--url", "https://footballia.eu/matches/x", "--dest", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert calls["fetch"][0] == "https://footballia.eu/matches/x" and calls["fetch"][2] is calls["session"]
    assert "95.0 min" in r.output
    assert settings.footballia_password.get_secret_value() not in r.output
