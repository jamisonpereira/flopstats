from decimal import Decimal

import pytest

from flopstats.detect import enrich
from flopstats.detect.enrich import CandidateRef, DecideConfig, EventRow, LineupEntry, MatchContext
from flopstats.detect.sim import SimWeights
from flopstats.detect.verify import FlopAttrs, PlayerGuess, VerifyResult
from flopstats.video.timesync import SyncResult

SYNC = SyncResult(kickoff_offset_s=100.0, second_half_offset_s=3700.0, status="ok")
CFG = DecideConfig(confirm_t=0.85, review_t=0.5, review_cap=None, min_player_conf=0.6, weights=SimWeights())


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def world(db):
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('PL', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    home = _one(db, "insert into teams (name) values ('Home') returning id")
    away = _one(db, "insert into teams (name) values ('Away') returning id")
    m = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, now()) returning id", s, home, away)
    lineup = []
    for team, num, name in [(home, 7, "Mason Mount"), (home, 9, "Rasmus Hojlund"), (home, 10, "Marcus Rashford"),
                            (home, 4, "Matthijs de Ligt"), (away, 3, "Calvin Bassey")]:
        pid = _one(db, "insert into players (display_name) values (%s) returning id", name)
        db.execute("insert into match_lineups (match_id, player_id, team_id, is_starter, shirt_number) values (%s, %s, %s, true, %s)", (m, pid, team, num))
        lineup.append(LineupEntry(player_id=pid, team_id=team, shirt_number=num, name=name))
    v = _one(db, "insert into videos (match_id, source, source_url) values (%s, 'footballia', 'u') returning id", m)
    r = _one(db, "insert into detection_runs (name, config) values ('r1', '{}') returning id")
    cand = _one(db, "insert into candidates (run_id, video_id, start_s, end_s, final_score, status) values (%s, %s, 1300, 1340, 0.8, 'verified') returning id", r, v)
    events = [EventRow(minute=21, extra_minute=None, type="Card", detail="Yellow Card", comments="Foul", team_id=away)]
    ctx = MatchContext(id=m, home_team_id=home, away_team_id=away, lineup=lineup, events=events)
    return {"match": ctx, "run": r, "cand": CandidateRef(id=cand, video_id=v, start_s=1300.0), "home": home, "away": away, "lineup": lineup}


def R(conf=0.9, shirt=7, team="home", name=None, start=5.0, **kw):
    return VerifyResult(is_flop=True, type="dive", confidence=conf, start_s=start, end_s=start + 6, is_replay=False,
                        flopper=PlayerGuess(team=team, shirt_number=shirt, name=name, confidence=0.9),
                        others=[PlayerGuess(team="away", shirt_number=3, confidence=0.8)],
                        attrs=FlopAttrs(fake_pain=7, time_on_ground_s=12, contact_level="light"), ref_decision="foul",
                        usd=Decimal("0.01"), **kw)


def test_attribute_by_shirt_number(world):
    a = enrich.attribute(PlayerGuess(team="home", shirt_number=9, confidence=0.8), world["lineup"], world["home"], 0.6)
    assert a.player_id == world["lineup"][1].player_id and a.confidence == 0.8


def test_attribute_falls_back_to_name(world):
    a = enrich.attribute(PlayerGuess(team="home", shirt_number=None, name="Rashford", confidence=0.9), world["lineup"], world["home"], 0.6)
    assert a.player_id == world["lineup"][2].player_id


def test_attribute_low_confidence_is_unattributed(world):
    a = enrich.attribute(PlayerGuess(team="home", shirt_number=9, confidence=0.3), world["lineup"], world["home"], 0.6)
    assert a.player_id is None and len(a.guesses) == 3


def test_attribute_only_within_team(world):
    a = enrich.attribute(PlayerGuess(team="away", shirt_number=7, confidence=0.9), world["lineup"], world["away"], 0.6)
    assert a.player_id is None


def test_consequence_penalty_scored(world):
    h, a = world["home"], world["away"]
    events = [EventRow(31, None, "Goal", "Penalty", None, h), EventRow(30, None, "Card", "Yellow Card", "Foul", a)]
    c = enrich.consequence(events, 29, 40, h)  # flop at 29:40; booking in minute 30, penalty scored in minute 31
    assert c == {"penalty_awarded": True, "penalty_scored": True, "opponent_booked": True, "goal_within_60s": False}
    far = enrich.consequence(events, 10, 0, h)
    assert not any(far.values())
    own_card = enrich.consequence([EventRow(30, None, "Card", "Yellow Card", "Simulation", h)], 29, 40, h)
    assert own_card["opponent_booked"] is False


def test_consequence_missed_penalty_and_goal(world):
    h = world["home"]
    c = enrich.consequence([EventRow(76, None, "Goal", "Missed Penalty", None, h), EventRow(75, None, "Goal", "Normal Goal", None, h)], 74, 30, h)
    assert c["penalty_awarded"] and not c["penalty_scored"] and c["goal_within_60s"]


def test_persist_writes_incident_players_and_sim(world, db):
    iid = enrich.persist(db, world["run"], world["cand"], R(conf=0.9), SYNC, world["match"], CFG)
    row = db.execute("select status, type, team_id, game_minute, game_second, video_start_s, ref_decision, "
                     "ref_penalized_team_id, sim_score, consequence, attrs from incidents where id = %s", (iid,)).fetchone()
    status, type_, team, minute, second, vstart, ref, penal, sim, cons, attrs = row
    assert (status, type_, team, ref, penal) == ("confirmed", "dive", world["home"], "foul", world["away"])
    assert (minute, second, vstart) == (20, 5, 1305.0)  # 1305 - 100 = 1205 s = 20:05
    assert cons["opponent_booked"] is True  # away yellow in minute 21
    assert sim > 0 and attrs["fake_pain"] == 7
    players = db.execute("select role, player_id, team_id from incident_players where incident_id = %s order by role desc", (iid,)).fetchall()
    assert players == [("flopper", world["lineup"][0].player_id, world["home"]), ("alleged_fouler", world["lineup"][4].player_id, world["away"])]
    assert _one(db, "select count(*) from review_items") == 0


def test_borderline_creates_flop_verdict_item(world, db):
    iid = enrich.persist(db, world["run"], world["cand"], R(conf=0.6), SYNC, world["match"], CFG)
    assert db.execute("select kind, subject_type, subject_id from review_items").fetchall() == [("flop_verdict", "incident", iid)]


def test_unattributed_flopper_creates_flop_player_item_and_team_only(world, db):
    iid = enrich.persist(db, world["run"], world["cand"], R(conf=0.9, shirt=44), SYNC, world["match"], CFG)
    assert _one(db, "select team_id from incidents where id = %s", iid) == world["home"]
    player_id, team_id = db.execute("select player_id, team_id from incident_players where incident_id = %s and role = 'flopper'", (iid,)).fetchone()
    assert player_id is None and team_id == world["home"]
    kind, payload = db.execute("select kind, payload from review_items").fetchone()
    assert kind == "flop_player" and len(payload["guesses"]) == 3
    assert all(g["team_id"] == world["home"] for g in payload["guesses"])


def test_persist_idempotent(world, db):
    a = enrich.persist(db, world["run"], world["cand"], R(conf=0.6, shirt=44), SYNC, world["match"], CFG)
    b = enrich.persist(db, world["run"], world["cand"], R(conf=0.6, shirt=44), SYNC, world["match"], CFG)
    assert a == b
    assert _one(db, "select count(*) from incidents") == 1
    assert _one(db, "select count(*) from incident_players") == 2
    assert _one(db, "select count(*) from review_items") == 2  # flop_verdict + flop_player, once each


def test_review_cap_counts_this_match_in_this_run(world, db):
    cfg = DecideConfig(confirm_t=0.85, review_t=0.5, review_cap=1, min_player_conf=0.6, weights=SimWeights())
    first = enrich.persist(db, world["run"], world["cand"], R(conf=0.6, start=1.0), SYNC, world["match"], cfg)
    second = enrich.persist(db, world["run"], world["cand"], R(conf=0.6, shirt=9, start=30.0), SYNC, world["match"], cfg)
    statuses = dict(db.execute("select id, status from incidents").fetchall())
    assert statuses == {first: "review", second: "ai_judged"}


def test_persist_records_ai_status(world, db):
    iid = enrich.persist(db, world["run"], world["cand"], R(conf=0.6), SYNC, world["match"], CFG)
    assert _one(db, "select ai_status from incidents where id = %s", iid) == "review"
