from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from flopstats import review, runner
from flopstats.config import Settings
from flopstats.detect.models import ScoreResult
from flopstats.detect.verify import FlopAttrs, PlayerGuess, VerifyResult
from flopstats.footballia.catalog import CatalogEntry
from flopstats.storage import LocalStorage
from flopstats.video.timesync import ClockReading

URL = "https://footballia.eu/matches/home-fc-away-fc-premier-league"
DURATION = 6000.0
KICKOFF, SECOND = 100.0, 3000.0
HOT = {1000, 1010, 2000, 4000, 5000}  # window starts the fake scorer finds suspicious


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def world(db):
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('PL', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    home = _one(db, "insert into teams (name) values ('Home FC') returning id")
    away = _one(db, "insert into teams (name) values ('Away FC') returning id")
    m = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, '2024-12-21 15:00Z') returning id", s, home, away)
    for team, num, name in [(home, 7, "Home Seven"), (home, 9, "Home Nine"), (away, 3, "Away Three"), (away, 5, "Away Five")]:
        pid = _one(db, "insert into players (display_name) values (%s) returning id", name)
        db.execute("insert into match_lineups (match_id, player_id, team_id, is_starter, shirt_number, minutes_played) values (%s, %s, %s, true, %s, 90)", (m, pid, team, num))
    db.execute("insert into match_events (match_id, team_id, minute, type, detail, comments, source_hash) values (%s, %s, 16, 'Card', 'Yellow Card', 'Simulation', 'e1')", (m, home))
    return {"match": m, "home": home, "away": away}


class FakeScorer:
    name = "fake-decision"

    def __init__(self, usd="0.001"):
        self.calls, self.usd = [], Decimal(usd)

    def score(self, segment):
        start = int(Path(segment).stem.split("_")[-1])
        self.calls.append(start)
        return ScoreResult(p_flop=0.9 if start in HOT else 0.05, usd=self.usd, raw={})


class FakeVerifier:
    name = "fake-verifier"

    def __init__(self, fail_on_call=None, conf=0.9):
        self.calls, self.fail_on_call, self.conf = 0, fail_on_call, conf

    def verify(self, segment, context):
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("verifier crashed")
        shirt = 7 if "2000" not in Path(segment).name else 44  # one flopper isn't in the lineup
        return VerifyResult(is_flop=True, type="dive", confidence=self.conf, start_s=8.0, end_s=14.0, is_replay=False,
                            flopper=PlayerGuess(team="home", shirt_number=shirt, confidence=0.9), others=[],
                            attrs=FlopAttrs(fake_pain=7, time_on_ground_s=10, contact_level="light"),
                            ref_decision="foul", usd=Decimal("0.01"))


class FakeClock:
    def __init__(self, readable=True):
        self.readable = readable

    def read(self, png):
        t = float(Path(png).stem)
        if not self.readable:
            return None
        if KICKOFF <= t < KICKOFF + 2700:
            c = t - KICKOFF
        elif t >= SECOND:
            c = 2700 + t - SECOND
        else:
            return None
        return ClockReading(int(c // 60), int(c % 60), 0.9)


def make_deps(tmp_path, *, scorer=None, verifier=None, clock=None, budget="500", entry_date=date(2024, 12, 21)):
    downloads = []

    def download(url, dest):
        downloads.append(url)
        p = Path(dest) / "match.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"full match")
        return p

    def cut(src, start, end, dest, reencode, *, audio=False):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(f"{start}-{end}".encode())
        return Path(dest)

    entry = CatalogEntry(url=URL, home="Home FC", away="Away FC", date=entry_date, competition="Premier League", season="2024-2025")
    settings = Settings(_env_file=None, FLOPSTATS_BUDGET_USD=budget)
    deps = runner.Deps(
        storage=LocalStorage(tmp_path / "store"), scorer=scorer or FakeScorer(), verifiers=[verifier or FakeVerifier()],
        clock_reader=clock or FakeClock(), download=download, entry_for=lambda conn, url: entry,
        probe_duration=lambda p: DURATION, cut=cut, frame_at=lambda src, t, dest: Path(f"{t:.3f}.png"),
        workdir=tmp_path / "work", settings=settings,
    )
    deps.downloads = downloads
    return deps


CONFIG = runner.RunConfig(candidate_threshold=0.6, prior_weight=0.2, confirm_threshold=0.85, review_threshold=0.5,
                          player_min_conf=0.6, scorer_model="fake-decision", verifier_models=["fake-verifier"],
                          primary_verifier="fake-verifier", prompt_versions={"verify": "v1"})


def counts(db):
    q = lambda t: _one(db, f"select count(*) from {t}")
    return {t: q(t) for t in ("windows", "candidates", "verifications", "incidents", "clips", "cost_ledger")}


def test_run_config_requires_thresholds():
    with pytest.raises(ValueError):
        runner.RunConfig(scorer_model="x", verifier_models=["y"], primary_verifier="y")


def test_process_match_end_to_end_with_fakes(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path)
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "done"
    c = counts(db)
    assert c["windows"] == 599  # 6000 s, 20 s every 10 s
    assert c["candidates"] == 4  # 1000+1010 merge; 2000; 4000; 5000
    assert c["incidents"] == 4 and c["clips"] == 4
    statuses = dict(db.execute("select status, count(*) from incidents group by 1").fetchall())
    assert statuses == {"confirmed": 4}
    kinds = [r[0] for r in db.execute("select kind from review_items order by id").fetchall()]
    assert kinds == ["flop_player"]  # shirt 44 isn't in the lineup
    video = db.execute("select deleted_at is not null, local_path, sync_status, match_id from videos").fetchone()
    assert video == (True, None, "ok", world["match"])
    assert not (tmp_path / "work").exists() or not list((tmp_path / "work").rglob("match.mp4"))
    paths = [r[0] for r in db.execute("select path from clips").fetchall()]
    assert all((tmp_path / "store" / p).exists() for p in paths)
    assert all(p.startswith(f"clips/{world['match']}/") for p in paths)
    # Running the finished match again does nothing.
    before = counts(db)
    again = runner.process_match(db, run, URL, deps)
    assert again.status == "done" and counts(db) == before and deps.downloads == [URL]


def test_resume_after_crash_mid_verify(db, world, tmp_path):
    # One call at a time, so the crash lands at a known point (parallel crashes: test_windows_finished_before_a_crash_are_kept).
    run = runner.create_run(db, "pilot-v1", CONFIG.model_copy(update={"workers": 1}))
    scorer = FakeScorer()
    crashing = make_deps(tmp_path, scorer=scorer, verifier=FakeVerifier(fail_on_call=3))
    with pytest.raises(RuntimeError):
        runner.process_match(db, run, URL, crashing)
    scored, before = len(scorer.calls), counts(db)
    assert before["verifications"] == 2 and before["incidents"] == 0
    verifier = FakeVerifier()
    rep = runner.process_match(db, run, URL, make_deps(tmp_path, scorer=scorer, verifier=verifier))
    assert rep.status == "done"
    assert len(scorer.calls) == scored  # no repeated window scoring
    assert verifier.calls == 2  # only the two unverified candidates
    after = counts(db)
    assert after["incidents"] == 4 and after["verifications"] == 4
    assert after["cost_ledger"] == before["cost_ledger"] + 2  # just the two new verifications


def test_budget_exhausted_stops_cleanly(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path, budget="0.12")
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "blocked_budget"
    assert _one(db, "select status from jobs where kind = 'score'") == "blocked_budget"
    spent = _one(db, "select sum(usd) from cost_ledger")
    assert spent <= Decimal("0.12")
    assert _one(db, "select count(*) from windows") == 100  # two batches of 50, the third would go over
    assert _one(db, "select count(*) from incidents") == 0


def test_needs_review_sync_skips_detection(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path, clock=FakeClock(readable=False))
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "paused_sync"
    assert _one(db, "select count(*) from windows") == 0 and deps.scorer.calls == []
    item, kind = db.execute("select id, kind from review_items").fetchone()
    assert kind == "video_sync"
    review.resolve(db, item, {"kickoff_offset_s": KICKOFF, "second_half_offset_s": SECOND})
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "done"
    assert _one(db, "select sync_status from videos") == "ok"
    assert _one(db, "select kickoff_offset_s from videos") == KICKOFF


def test_unlinked_match_pauses_until_reviewed(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path, entry_date=date(2024, 8, 1))  # no match near that date
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "paused_link" and deps.downloads == []  # nothing downloaded for an unlinked match
    item = _one(db, "select id from review_items where kind = 'match_link'")
    review.resolve(db, item, {"match_id": world["match"]})
    assert runner.process_match(db, run, URL, deps).status == "done"
    assert _one(db, "select match_id from videos") == world["match"]


def test_run_status_summary(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    runner.process_match(db, run, URL, make_deps(tmp_path))
    s = runner.status(db, run)
    assert s["jobs"]["done"] == 9 and s["incidents"] == {"confirmed": 4} and s["open_reviews"] == 1
    assert s["spent_usd"] > 0


# --- final review I5/I10 ---------------------------------------------------------------

def test_unknown_listing_link_item_is_resolvable(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path)
    deps.entry_for = lambda conn, url: None  # never seen by `watch` / `season`
    assert runner.process_match(db, run, URL, deps).status == "paused_link"
    item, subject_type, subject_id = db.execute("select id, subject_type, subject_id from review_items").fetchone()
    assert subject_type == "footballia_listing"
    assert _one(db, "select entity_type from external_refs where id = %s", subject_id) == "footballia_listing"
    review.resolve(db, item, {"match_id": world["match"]})
    assert runner.process_match(db, run, URL, deps).status == "done"


def test_concurrent_run_of_the_same_match_is_refused(db, world, tmp_path):
    import psycopg

    from conftest import LOCAL_DB_URL

    run = runner.create_run(db, "pilot-v1", CONFIG)
    deps = make_deps(tmp_path)
    video = _one(db, "insert into videos (source, source_url) values ('footballia', %s) returning id", URL)
    with psycopg.connect(LOCAL_DB_URL, autocommit=True) as other:
        assert other.execute("select pg_try_advisory_lock(%s)", (runner.match_lock_key(run, video),)).fetchone()[0]
        rep = runner.process_match(db, run, URL, deps)
        assert rep.status == "busy" and deps.scorer.calls == [] and deps.downloads == []
    assert runner.process_match(db, run, URL, deps).status == "done"  # lock released with the other session


class BlockingScorer(FakeScorer):
    def score(self, segment):
        from flopstats.detect.gemini import ContentBlocked
        if int(Path(segment).stem.split("_")[-1]) == 3000:
            raise ContentBlocked("HTTP 400 (prohibited_content: Input blocked)")
        return super().score(segment)


def test_a_blocked_window_is_stored_unscored_and_the_match_continues(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG)
    rep = runner.process_match(db, run, URL, make_deps(tmp_path, scorer=BlockingScorer()))
    assert rep.status == "done"
    assert counts(db)["windows"] == 599
    assert db.execute("select score from windows where start_s = 3000").fetchone() == (None,)


class ConcurrencyProbe:
    """Records how many calls overlap; each call sleeps briefly so overlap is observable."""

    def __init__(self):
        import threading
        self.lock, self.now, self.peak = threading.Lock(), 0, 0

    def __enter__(self):
        with self.lock:
            self.now += 1
            self.peak = max(self.peak, self.now)

    def __exit__(self, *exc):
        import time
        time.sleep(0.005)
        with self.lock:
            self.now -= 1


class SlowScorer(FakeScorer):
    def __init__(self):
        super().__init__()
        self.probe = ConcurrencyProbe()

    def score(self, segment):
        with self.probe:
            return super().score(segment)


class SlowVerifier(FakeVerifier):
    def __init__(self, name, probe):
        super().__init__()
        self.name, self.probe = name, probe

    def verify(self, segment, context):
        import time
        with self.probe:
            time.sleep(0.02)
            return super().verify(segment, context)


def test_windows_are_scored_in_parallel(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG.model_copy(update={"workers": 4}))
    scorer = SlowScorer()
    rep = runner.process_match(db, run, URL, make_deps(tmp_path, scorer=scorer))
    assert rep.status == "done"
    assert counts(db)["windows"] == 599 and len(set(scorer.calls)) == 599
    assert 1 < scorer.probe.peak <= 4


def test_verifier_calls_run_in_parallel_and_each_is_stored_once(db, world, tmp_path):
    cfg = CONFIG.model_copy(update={"workers": 4, "verifier_models": ["fake-verifier", "other"]})
    run = runner.create_run(db, "pilot-v1", cfg)
    probe = ConcurrencyProbe()
    deps = make_deps(tmp_path)
    deps.verifiers = [SlowVerifier("fake-verifier", probe), SlowVerifier("other", probe)]
    rep = runner.process_match(db, run, URL, deps)
    assert rep.status == "done"
    assert 1 < probe.peak <= 4
    rows = db.execute("select candidate_id, model, count(*) from verifications group by 1, 2").fetchall()
    assert len(rows) == 8 and all(n == 1 for _, _, n in rows)  # 4 candidates x 2 models


class FailingScorer(FakeScorer):
    def score(self, segment):
        if int(Path(segment).stem.split("_")[-1]) == 300:
            raise RuntimeError("scorer crashed")
        return super().score(segment)


def test_windows_finished_before_a_crash_are_kept(db, world, tmp_path):
    run = runner.create_run(db, "pilot-v1", CONFIG.model_copy(update={"workers": 4}))
    with pytest.raises(RuntimeError):
        runner.process_match(db, run, URL, make_deps(tmp_path, scorer=FailingScorer()))
    stored = {r[0] for r in db.execute("select start_s from windows")}
    assert 300 not in stored and {0, 290, 310} <= stored  # the rest of that batch was saved
