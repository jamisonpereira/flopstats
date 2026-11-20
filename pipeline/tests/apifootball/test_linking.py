from datetime import date

import pytest

from flopstats.apifootball.linking import backfill_nationality, find_duplicate_players, link_event_player


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def match(db):
    """A match with a home lineup: João Félix (api 1001), Mason Mount (api 1002), Luke Shaw (no api ref)."""
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('PL', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    h = _one(db, "insert into teams (name) values ('Home') returning id")
    a = _one(db, "insert into teams (name) values ('Away') returning id")
    m = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, now()) returning id", s, h, a)
    players = {}
    for name, api in (("João Félix", 1001), ("Mason Mount", 1002), ("Luke Shaw", None)):
        pid = _one(db, "insert into players (display_name) values (%s) returning id", name)
        players[name] = pid
        db.execute("insert into match_lineups (match_id, player_id, team_id, is_starter) values (%s, %s, %s, true)", (m, pid, h))
        if api:
            db.execute("insert into external_refs (entity_type, entity_id, source, source_id, confidence, status) values ('player', %s, 'api-football', %s, 1, 'linked')", (pid, str(api)))
    return {"match": m, "home": h, "away": a, "players": players, "season": s}


def test_link_by_api_id(db, match):
    r = link_event_player(db, match["match"], match["home"], 1002, "Somebody Else")
    assert (r.player_id, r.confidence, r.method) == (match["players"]["Mason Mount"], 1.0, "api_id")


def test_link_by_exact_lineup_name(db, match):
    r = link_event_player(db, match["match"], match["home"], None, "luke  shaw")
    assert (r.player_id, r.method) == (match["players"]["Luke Shaw"], "exact_name")
    assert r.confidence == 0.95


def test_link_fuzzy_accent_insensitive(db, match):
    r = link_event_player(db, match["match"], match["home"], 99999, "Joao Felix")
    assert r.player_id == match["players"]["João Félix"]
    assert r.method in ("exact_name", "fuzzy")


def test_link_fuzzy_spelling_variant(db, match):
    r = link_event_player(db, match["match"], match["home"], None, "Mason Mountt")
    assert (r.player_id, r.method) == (match["players"]["Mason Mount"], "fuzzy")
    assert 0.9 <= r.confidence < 1.0


def test_name_only_searches_the_given_team_lineup(db, match):
    r = link_event_player(db, match["match"], match["away"], None, "Luke Shaw", event_id=5)
    assert r.player_id is None


def test_unlinkable_creates_review_item_and_returns_none(db, match):
    r = link_event_player(db, match["match"], match["home"], 424242, "Totally Unknown", event_id=77)
    assert (r.player_id, r.method) == (None, "none")
    kind, subject_type, subject_id, payload = db.execute(
        "select kind, subject_type, subject_id, payload from review_items"
    ).fetchone()
    assert (kind, subject_type, subject_id) == ("player_link", "match_event", 77)
    assert payload["name"] == "Totally Unknown" and payload["api_player_id"] == 424242
    assert payload["match_id"] == match["match"] and len(payload["guesses"]) == 3
    # Linking the same event again does not pile up review items.
    link_event_player(db, match["match"], match["home"], 424242, "Totally Unknown", event_id=77)
    assert _one(db, "select count(*) from review_items") == 1


def test_find_duplicate_players(db):
    ids = [
        _one(db, "insert into players (display_name, birth_date) values (%s, %s) returning id", n, d)
        for n, d in (("Ángel Gomes", date(2000, 8, 31)), ("angel  gomes", date(2000, 8, 31)),
                     ("Angel Gomes", date(1999, 1, 1)), ("Someone Else", date(2000, 8, 31)),
                     ("Angel Gomes", None))
    ]
    assert find_duplicate_players(db) == [(ids[0], ids[1])]


class FakeClient:
    def __init__(self, data):
        self.data, self.calls = data, []

    def player(self, player_id, season):
        self.calls.append((player_id, season))
        return self.data.get(player_id, [])


def test_backfill_nationality(db, match):
    client = FakeClient({
        1001: [{"player": {"id": 1001, "firstname": "João", "lastname": "Félix", "nationality": "Portugal", "birth": {"date": "1999-11-10"}}}],
        1002: [{"player": {"id": 1002, "nationality": None, "birth": {"date": None}}}],
    })
    assert backfill_nationality(db, client, 2024) == 1
    assert sorted(client.calls) == [(1001, 2024), (1002, 2024)]  # Luke Shaw has no API id
    row = db.execute(
        "select c.name, p.first_name, p.last_name, p.birth_date from players p join countries c on c.id = p.nationality_country_id where p.id = %s",
        (match["players"]["João Félix"],),
    ).fetchone()
    assert row == ("Portugal", "João", "Félix", date(1999, 11, 10))
    client.calls.clear()
    assert backfill_nationality(db, client, 2024) == 0
    assert client.calls == [(1002, 2024)]  # already-filled players are not fetched again
