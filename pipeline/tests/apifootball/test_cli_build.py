from typer.testing import CliRunner

from flopstats import cli
from flopstats.apifootball.build import BuildReport


def test_build_season_cli_prints_report(settings, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "_connect", lambda s: object())

    def fake_build(conn, league, season):
        calls.append((league, season))
        return BuildReport(counts={"matches": 380, "match_events": 1000}, needs_review=5, null_player_events=5)

    monkeypatch.setattr("flopstats.apifootball.build.build_season", fake_build)
    result = CliRunner().invoke(cli.app, ["api", "build-season", "--league", "39", "--season", "2024"])
    assert result.exit_code == 0, result.output
    assert calls == [(39, 2024)]
    assert "matches: 380" in result.output
    assert "events with null player: 5 of 1000 (0.50%)" in result.output
