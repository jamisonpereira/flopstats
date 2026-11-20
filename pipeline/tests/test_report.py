from decimal import Decimal

import pytest
from psycopg.types.json import Jsonb

from flopstats import report


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def w(db):
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('PL', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    h = _one(db, "insert into teams (name) values ('Home') returning id")
    a = _one(db, "insert into teams (name) values ('Away') returning id")
    run = _one(db, "insert into detection_runs (name, config) values ('pilot', '{}') returning id")
    matches, videos = [], []
    for i in range(2):
        m = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, now()) returning id", s, h, a)
        v = _one(db, "insert into videos (match_id, source, source_url, sync_status) values (%s, 'footballia', %s, 'ok') returning id", m, f"u{i}")
        db.execute("insert into jobs (kind, key, status) values ('score', %s, 'done')", (f"{run}:{v}:score",))
        matches.append(m)
        videos.append(v)
    return {"run": run, "home": h, "away": a, "matches": matches, "videos": videos}


def incident(db, w, *, ai_status, status=None, minute=10, second=0, key=None, match=0, cand=None):
    return _one(db, "insert into incidents (run_id, match_id, video_id, candidate_id, type, video_start_s, video_end_s, game_minute, "
                    "game_second, team_id, confidence, status, ai_status, dedupe_key) values (%s, %s, %s, %s, 'dive', 0, 5, %s, %s, %s, 0.9, %s, %s, %s) returning id",
                w["run"], w["matches"][match], w["videos"][match], cand, minute, second, w["home"], status or ai_status, ai_status,
                key or f"{match}:{minute}:{second}")


def reviewed(db, incident_id, decision):
    db.execute("insert into reviews (incident_id, decision) values (%s, %s)", (incident_id, decision))


def test_precision_counts_only_reviewed_confirmed(db, w):
    a = incident(db, w, ai_status="confirmed", minute=1)
    b = incident(db, w, ai_status="confirmed", minute=2)
    c = incident(db, w, ai_status="ai_judged", minute=3)
    incident(db, w, ai_status="confirmed", minute=4)  # never reviewed: not counted
    d = incident(db, w, ai_status="review", minute=5)  # sent to review by the AI: not an AI-confirmed flop
    reviewed(db, a, "confirm")
    reviewed(db, b, "reject")
    reviewed(db, c, "change_type")  # still a flop, just another type
    reviewed(db, d, "reject")
    reviewed(db, a, "set_player")  # naming the player is not a verdict
    p = report.precision(db, w["run"])
    assert (p.agreed, p.reviewed) == (2, 3) and p.rate == pytest.approx(2 / 3)


def test_precision_uses_latest_verdict(db, w):
    a = incident(db, w, ai_status="confirmed")
    reviewed(db, a, "reject")
    reviewed(db, a, "confirm")
    assert report.precision(db, w["run"]).agreed == 1


def known_dive(db, w, minute, *, kind="sim", match=0):
    if kind == "sim":
        db.execute("insert into match_events (match_id, team_id, minute, type, detail, comments, source_hash) values (%s, %s, %s, 'Card', 'Yellow Card', 'Simulation', %s)",
                   (w["matches"][match], w["home"], minute, f"k{match}{minute}"))
    else:
        db.execute("insert into match_events (match_id, team_id, minute, type, detail, source_hash) values (%s, %s, %s, 'Var', 'Penalty cancelled', %s)",
                   (w["matches"][match], w["home"], minute, f"v{match}{minute}"))


def test_known_dive_found_within_60s(db, w):
    known_dive(db, w, 20)  # minute 20 = clock 19:00-20:00
    incident(db, w, ai_status="confirmed", minute=20, second=50)  # 50 s after the minute ends
    known_dive(db, w, 70, kind="var", match=1)
    incident(db, w, ai_status="review", minute=68, second=10, match=1)  # 50 s before the minute starts
    r = report.known_dive_recall(db, w["run"])
    assert (r.found, r.total, r.missed) == (2, 2, [])


def test_known_dive_missed_listed(db, w):
    known_dive(db, w, 20)
    incident(db, w, ai_status="confirmed", minute=22, second=30)  # 150 s away
    known_dive(db, w, 30)
    incident(db, w, ai_status="rejected", minute=30)  # rejected incidents don't count
    db.execute("insert into match_events (match_id, team_id, minute, type, detail, comments, source_hash) values (%s, %s, 40, 'Card', 'Yellow Card', 'Foul', 'x')",
               (w["matches"][0], w["home"]))  # not a known dive
    r = report.known_dive_recall(db, w["run"])
    assert (r.found, r.total) == (0, 2)
    assert [(m["minute"], m["type"]) for m in r.missed] == [(20, "Card"), (30, "Card")]


def test_known_dives_only_from_matches_in_the_run(db, w):
    other = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) select season_id, home_team_id, away_team_id, now() from matches limit 1 returning id")
    db.execute("insert into match_events (match_id, team_id, minute, type, detail, comments, source_hash) values (%s, %s, 5, 'Card', 'Yellow Card', 'Simulation', 'o')",
               (other, w["home"]))
    assert report.known_dive_recall(db, w["run"]).total == 0


def test_verifier_comparison_per_model(db, w):
    def cand(i):
        return _one(db, "insert into candidates (run_id, video_id, start_s, end_s, final_score, status) values (%s, %s, %s, %s, 0.8, 'verified') returning id",
                    w["run"], w["videos"][0], i * 100, i * 100 + 20)

    def verification(c, model, is_flop, usd):
        db.execute("insert into verifications (candidate_id, model, answers, confidence, usd) values (%s, %s, %s, 0.8, %s)",
                   (c, model, Jsonb({"is_flop": is_flop}), usd))

    c1, c2 = cand(1), cand(2)
    i1 = incident(db, w, ai_status="confirmed", minute=1, cand=c1)
    i2 = incident(db, w, ai_status="review", minute=2, cand=c2)
    reviewed(db, i1, "confirm")
    reviewed(db, i2, "reject")
    verification(c1, "pro", True, "0.04"); verification(c2, "pro", True, "0.04")
    verification(c1, "flash", True, "0.01"); verification(c2, "flash", False, "0.01")
    stats = {s.model: s for s in report.verifier_comparison(db, w["run"])}
    assert (stats["pro"].agreed_with_jamison, stats["pro"].reviewed) == (1, 2)
    assert (stats["flash"].agreed_with_jamison, stats["flash"].reviewed) == (2, 2)
    assert stats["pro"].usd_per_match == pytest.approx(0.04)  # $0.08 over 2 matches
    assert stats["flash"].usd_per_match == pytest.approx(0.01)


def test_cost_projection_scales_by_matches(db, w):
    for i, usd in enumerate(["0.30", "0.50"]):
        db.execute("insert into cost_ledger (run_id, match_id, service, usd, idempotency_key) values (%s, %s, 'score', %s, %s)",
                   (w["run"], w["matches"][i], usd, f"k{i}"))
    assert report.cost_projection(db, w["run"], 380) == Decimal("152.00")  # $0.40 per match


def test_ai_status_is_kept_when_reviews_change_status(db, w):
    a = incident(db, w, ai_status="review")
    db.execute("update incidents set status = 'confirmed' where id = %s", (a,))
    assert _one(db, "select ai_status from incidents where id = %s", a) == "review"


def test_report_cli_pass_fail(db, w, settings, monkeypatch):
    from typer.testing import CliRunner

    from flopstats import cli

    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "_connect", lambda s: db)
    a = incident(db, w, ai_status="confirmed", minute=20, second=10)
    reviewed(db, a, "confirm")
    known_dive(db, w, 20)
    known_dive(db, w, 80)
    out = CliRunner().invoke(cli.app, ["report", "--run", str(w["run"])]).output
    assert "precision: 1/1 = 100%" in out and "known-dive recall: 1/2 = 50%" in out
    assert "missed: match" in out and "PASS precision" in out and "FAIL known-dive recall" in out
