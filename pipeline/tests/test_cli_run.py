import json
from datetime import date

from typer.testing import CliRunner

from flopstats import cli, runner
from flopstats.footballia.catalog import CatalogEntry

CFG = {"candidate_threshold": 0.6, "prior_weight": 0.2, "confirm_threshold": 0.85, "review_threshold": 0.5,
       "player_min_conf": 0.6, "scorer_model": "gemini-decision-1", "verifier_models": ["gemini-3.8-flash"],
       "primary_verifier": "gemini-3.8-flash", "prices": {"gemini-3.8-flash": {"input": 0.5, "output": 3}}}


def _patch(monkeypatch, db, settings):
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "_connect", lambda s: db)


def test_run_create_and_status(db, settings, monkeypatch, tmp_path):
    _patch(monkeypatch, db, settings)
    f = tmp_path / "pilot.json"
    f.write_text(json.dumps(CFG))
    r = CliRunner().invoke(cli.app, ["run", "create", "--name", "pilot-v1", "--config", str(f)])
    assert r.exit_code == 0, r.output
    run_id = int(r.output.strip().split()[-1])
    s = CliRunner().invoke(cli.app, ["run", "status", "--run", str(run_id)])
    assert s.exit_code == 0 and "spent" in s.output and "open reviews: 0" in s.output


def test_run_create_rejects_missing_thresholds(db, settings, monkeypatch, tmp_path):
    _patch(monkeypatch, db, settings)
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({"scorer_model": "x", "verifier_models": ["y"], "primary_verifier": "y"}))
    assert CliRunner().invoke(cli.app, ["run", "create", "--name", "bad", "--config", str(f)]).exit_code != 0


def test_run_season_limits_and_urls(db, settings, monkeypatch, tmp_path):
    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = [CatalogEntry(url=f"https://footballia.eu/matches/m{i}", home="A", away="B", date=date(2024, 9, i),
                            competition="Premier League", season="2024-2025") for i in range(1, 6)]
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    done = []
    monkeypatch.setattr(runner, "process_match", lambda conn, run, url, deps: done.append(url) or runner.MatchReport("done"))
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--league", "39", "--season", "2024", "--limit", "2"])
    assert r.exit_code == 0, r.output and done == [entries[0].url, entries[1].url]
    done.clear()
    urls = f"{entries[4].url},{entries[2].url}"
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--league", "39", "--season", "2024", "--urls", urls])
    assert r.exit_code == 0, r.output
    assert done == [entries[2].url, entries[4].url]  # listing order, restricted to --urls


def test_run_season_stops_on_budget(db, settings, monkeypatch):
    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = [CatalogEntry(url=f"https://footballia.eu/matches/m{i}", home="A", away="B", date=date(2024, 9, i),
                            competition="Premier League", season="2024-2025") for i in range(1, 4)]
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    done = []
    monkeypatch.setattr(runner, "process_match", lambda conn, run, url, deps: done.append(url) or runner.MatchReport("blocked_budget"))
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--league", "39", "--season", "2024"])
    assert r.exit_code == 0 and len(done) == 1 and "budget" in r.output


def test_build_deps_reads_the_clock_with_the_configured_gemini_model(tmp_path, monkeypatch):
    from pydantic import SecretStr

    from flopstats import runner
    from flopstats.config import Settings
    from flopstats.detect.gemini import GeminiClockReader

    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, gemini_key=SecretStr("k"), storage_backend="local", storage_local_root=str(tmp_path))
    cfg = runner.RunConfig(**CFG)
    deps = cli._build_deps(settings, cfg)
    assert isinstance(deps.clock_reader, GeminiClockReader) and deps.clock_reader.name == "gemini-3.8-flash"


def test_build_deps_scores_windows_from_a_working_copy(tmp_path, monkeypatch):
    from pydantic import SecretStr

    from flopstats.config import Settings
    from flopstats.video import ffmpeg

    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, gemini_key=SecretStr("k"), storage_backend="local", storage_local_root=str(tmp_path))
    deps = cli._build_deps(settings, runner.RunConfig(**CFG))
    assert deps.working_copy is ffmpeg.working_copy and deps.window is ffmpeg.window


def _season_entries(n):
    return [CatalogEntry(url=f"https://footballia.eu/matches/m{i}", home="A", away="B", date=date(2024, 9, i),
                         competition="Premier League", season="2024-2025") for i in range(1, n + 1)]


def test_run_season_parallel_processes_each_match_once_two_at_a_time(db, settings, monkeypatch):
    import threading
    import time

    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = _season_entries(6)
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    lock, state, done = threading.Lock(), {"now": 0, "peak": 0}, []

    def process(conn, run, url, deps):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
            done.append(url)
        return runner.MatchReport("done")

    monkeypatch.setattr(runner, "process_match", process)
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--season", "2024", "--parallel", "2"])
    assert r.exit_code == 0, r.output
    assert sorted(done) == sorted(e.url for e in entries) and state["peak"] == 2
    assert "'done': 6" in r.output


def test_run_season_parallel_stops_starting_matches_on_budget(db, settings, monkeypatch):
    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = _season_entries(6)
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    started = []
    monkeypatch.setattr(runner, "process_match",
                        lambda conn, run, url, deps: started.append(url) or runner.MatchReport("blocked_budget"))
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--season", "2024", "--parallel", "2"])
    assert r.exit_code == 0, r.output
    assert len(started) <= 2 and "budget reached" in r.output


def test_run_season_waits_out_a_network_drop_and_retries_the_match(db, settings, monkeypatch):
    import psycopg

    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = _season_entries(3)
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    from conftest import LOCAL_DB_URL

    slept, connects, calls = [], [], []
    monkeypatch.setattr(cli, "_sleep", slept.append)
    monkeypatch.setattr(cli, "_connect", lambda s: connects.append(1) or psycopg.connect(LOCAL_DB_URL, autocommit=True))

    def process(conn, run, url, deps):
        calls.append(url)
        if url.endswith("m2") and calls.count(url) == 1:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return runner.MatchReport("done")

    monkeypatch.setattr(runner, "process_match", process)
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--season", "2024"])
    assert r.exit_code == 0, r.output
    assert calls.count(entries[1].url) == 2  # retried, not skipped
    assert "'done': 3" in r.output and "error" not in r.output.split("season")[-1]
    assert len(connects) >= 2  # reconnected after the drop
    assert "network" in r.output.lower()


def test_run_season_gives_up_on_a_match_that_keeps_losing_the_network(db, settings, monkeypatch):
    import httpx

    _patch(monkeypatch, db, settings)
    run_id = runner.create_run(db, "pilot", runner.RunConfig(**CFG))
    entries = _season_entries(2)
    monkeypatch.setattr("flopstats.footballia.catalog.list_season", lambda client, league, season, **kw: entries)
    monkeypatch.setattr(cli, "_build_deps", lambda settings, cfg: object())
    monkeypatch.setattr(cli, "_sleep", lambda s: None)
    import psycopg

    from conftest import LOCAL_DB_URL

    monkeypatch.setattr(cli, "_connect", lambda s: psycopg.connect(LOCAL_DB_URL, autocommit=True))

    def process(conn, run, url, deps):
        if url.endswith("m1"):
            raise httpx.ReadTimeout("timed out")
        return runner.MatchReport("done")

    monkeypatch.setattr(runner, "process_match", process)
    r = CliRunner().invoke(cli.app, ["run", "season", "--run", str(run_id), "--season", "2024"])
    assert r.exit_code == 0, r.output
    assert "'error': 1" in r.output and "'done': 1" in r.output
