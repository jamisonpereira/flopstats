import json
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from flopstats.apifootball.build import build_season, normalize_referee
from flopstats.apifootball.client import params_hash

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "apifootball"
TABLES = ["countries", "leagues", "seasons", "venues", "teams", "team_seasons", "players",
          "player_team_seasons", "coaches", "referees", "matches", "match_lineups", "match_events",
          "external_refs"]


def _store(db, endpoint, params, body):
    db.execute(
        "insert into api_raw (endpoint, params, params_hash, status_code, body) values (%s, %s, %s, 200, %s)",
        (endpoint, Jsonb({k: str(v) for k, v in params.items()}), params_hash(endpoint, params), Jsonb(body)),
    )


@pytest.fixture
def raw(db):
    load = lambda n: json.loads((FIXTURES / n).read_text())
    _store(db, "fixtures", {"league": 39, "season": 2024}, load("fixtures_season.json"))
    _store(db, "fixtures", {"ids": "1208021-1208022"}, load("fixtures_details.json"))
    return db


def _counts(db):
    return {t: db.execute(f"select count(*) from {t}").fetchone()[0] for t in TABLES}


def _one(db, sql, *params):
    return db.execute(sql, params).fetchone()


def test_build_creates_matches_teams_venue_referee(raw):
    report = build_season(raw, 39, 2024)
    db = raw
    assert report.counts["matches"] == 2
    home, away, venue, ref, round_, status, gh, ga, hc, ac = _one(
        db,
        "select h.name, a.name, v.name, r.name, m.round, m.status, m.goals_home, m.goals_away, "
        "hc.name, ac.name from matches m join teams h on h.id = m.home_team_id "
        "join teams a on a.id = m.away_team_id join venues v on v.id = m.venue_id "
        "join referees r on r.id = m.referee_id join coaches hc on hc.id = m.home_coach_id "
        "join coaches ac on ac.id = m.away_coach_id join external_refs x on x.entity_id = m.id "
        "and x.entity_type = 'match' and x.source = 'api-football' and x.source_id = '1208021'",
    )
    assert (home, away, venue, ref) == ("Manchester United", "Fulham", "Old Trafford", "R. Jones")
    assert (round_, status, gh, ga) == ("Regular Season - 1", "FT", 1, 0)
    assert (hc, ac) == ("E. ten Hag", "Marco Silva")
    assert _one(db, "select count(*) from teams")[0] == 4
    league, year, start, end = _one(
        db, "select l.name, s.year, s.start_date::text, s.end_date::text from seasons s join leagues l on l.id = s.league_id"
    )
    assert (league, year, start, end) == ("Premier League", 2024, "2024-08-16", "2024-08-17")
    assert _one(db, "select count(*) from team_seasons")[0] == 4
    assert _one(db, "select logo_source_url from teams where name = 'Fulham'")[0].endswith("/teams/36.png")
    assert _one(db, "select logo_path from teams where name = 'Fulham'")[0] is None


def test_build_is_idempotent(raw):
    first = build_season(raw, 39, 2024)
    after_first = _counts(raw)
    second = build_season(raw, 39, 2024)
    assert _counts(raw) == after_first
    assert first.counts == second.counts


def test_simulation_card_comment_preserved(raw):
    build_season(raw, 39, 2024)
    rows = raw.execute(
        "select p.display_name, e.detail, e.minute from match_events e join players p on p.id = e.player_id "
        "where e.type = 'Card' and e.comments = 'Simulation'"
    ).fetchall()
    assert rows == [("Mason Mount", "Yellow Card", 18)]


def test_var_penalty_cancelled_preserved(raw):
    build_season(raw, 39, 2024)
    rows = raw.execute(
        "select p.display_name from match_events e join players p on p.id = e.player_id "
        "where e.type = 'Var' and e.detail = 'Penalty cancelled'"
    ).fetchall()
    assert rows == [("Mohamed Salah",)]


def test_lineup_stats_loaded(raw):
    build_season(raw, 39, 2024)
    row = _one(
        raw,
        "select l.fouls_drawn, l.minutes_played, l.fouls_committed, l.yellow_cards, l.is_starter, "
        "l.shirt_number, l.position from match_lineups l join players p on p.id = l.player_id "
        "where p.display_name = 'Mason Mount'",
    )
    assert row == (3, 90, 1, 1, True, 7, "M")
    sub = _one(raw, "select is_starter, minutes_played from match_lineups l join players p on p.id = l.player_id where p.display_name = 'Joshua Zirkzee'")
    assert sub == (False, 29)
    assert _one(raw, "select penalties_won from match_lineups l join players p on p.id = l.player_id where p.display_name = 'Mohamed Salah'")[0] == 1
    assert _one(raw, "select penalties_committed from match_lineups l join players p on p.id = l.player_id where p.display_name = 'Calvin Bassey'")[0] == 1
    assert _one(raw, "select shirt_number, position from player_team_seasons pts join players p on p.id = pts.player_id where p.display_name = 'Mason Mount'") == (7, "M")


def test_event_assist_and_extra_minute(raw):
    build_season(raw, 39, 2024)
    sub = _one(raw, "select a.display_name from match_events e join players a on a.id = e.assist_player_id where e.type = 'subst'")
    assert sub == ("Joshua Zirkzee",)
    assert _one(raw, "select extra_minute from match_events where comments = 'Argument'")[0] == 3


def test_unknown_event_player_left_null_and_counted(raw):
    report = build_season(raw, 39, 2024)
    assert _one(raw, "select player_id from match_events where comments = 'Argument'")[0] is None
    assert report.needs_review == 1


def test_event_source_hash_is_fixture_plus_event_json(raw):
    import hashlib

    build_season(raw, 39, 2024)
    body = json.loads((FIXTURES / "fixtures_details.json").read_text())
    event = body["response"][0]["events"][0]
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(f"1208021:{canonical}".encode()).hexdigest()
    assert _one(raw, "select count(*) from match_events where source_hash = %s", expected)[0] == 1


@pytest.mark.parametrize(
    "raw_name, expected",
    [("T. Robinson, England", "T. Robinson"), ("  Michael   Oliver ", "Michael Oliver"), ("A. Taylor", "A. Taylor")],
)
def test_normalize_referee(raw_name, expected):
    assert normalize_referee(raw_name) == expected


def test_referee_suffix_stripped_in_db(raw):
    build_season(raw, 39, 2024)
    names = {r[0] for r in raw.execute("select name from referees").fetchall()}
    assert names == {"R. Jones", "T. Robinson"}


def test_build_unlinkable_event_player_creates_review_item(raw):
    build_season(raw, 39, 2024)
    build_season(raw, 39, 2024)  # a rebuild does not add a second item
    rows = raw.execute(
        "select r.kind, r.subject_type, r.payload->>'name' from review_items r "
        "join match_events e on e.id = r.subject_id where e.comments = 'Argument'"
    ).fetchall()
    assert rows == [("player_link", "match_event", "Unknown Bench Player")]


def test_build_links_event_player_by_lineup_name_when_api_id_missing(raw):
    body = json.loads((FIXTURES / "fixtures_details.json").read_text())
    ev = body["response"][1]["events"][1]  # Salah goal
    ev["player"]["id"] = None
    raw.execute("update api_raw set body = %s where params ? 'ids'", (Jsonb(body),))
    report = build_season(raw, 39, 2024)
    name = _one(raw, "select p.display_name from match_events e join players p on p.id = e.player_id where e.type = 'Goal' and e.minute = 60")[0]
    assert name == "Mohamed Salah"
    assert report.null_player_events == 1  # only the unknown bench player
    assert report.null_player_pct == pytest.approx(100 / 7)


def test_report_counts_distinct_rows(raw):
    body = json.loads((FIXTURES / "fixtures_details.json").read_text())
    body["response"][1]["fixture"]["referee"] = "R. Jones"  # same referee in both matches
    raw.execute("update api_raw set body = %s where params ? 'ids'", (Jsonb(body),))
    report = build_season(raw, 39, 2024)
    assert report.counts["referees"] == 1
    counts = _counts(raw)
    for table in ("teams", "players", "venues", "referees", "coaches", "matches", "match_lineups",
                  "match_events", "team_seasons", "player_team_seasons"):
        assert report.counts[table] == counts[table], table


def test_rebuild_keeps_a_reviewed_event_player(raw):
    from flopstats import review

    build_season(raw, 39, 2024)
    item, event_id = raw.execute("select id, subject_id from review_items where kind = 'player_link'").fetchone()
    salah = _one(raw, "select id from players where display_name = 'Mohamed Salah'")[0]
    raw.execute("update match_events set player_id = %s where id = %s", (salah, event_id))  # what the review screen does
    review.resolve(raw, item, {"player_id": salah})
    build_season(raw, 39, 2024)
    assert _one(raw, "select player_id from match_events where id = %s", event_id)[0] == salah
    assert _one(raw, "select count(*) from review_items where kind = 'player_link'")[0] == 1
