import pytest
from psycopg import errors

CORE_TABLES = {
    "countries", "leagues", "seasons", "venues", "teams", "team_seasons", "players",
    "player_team_seasons", "coaches", "referees", "matches", "match_lineups",
    "match_events", "external_refs", "review_items",
}


def _one(db, sql, *params):
    return db.execute(sql, params).fetchone()[0]


def _make_match(db) -> int:
    country = _one(db, "insert into countries (name, code) values ('England', 'GB') returning id")
    league = _one(db, "insert into leagues (name, country_id, type) values ('Premier League', %s, 'League') returning id", country)
    season = _one(db, "insert into seasons (league_id, year) values (%s, 2023) returning id", league)
    home = _one(db, "insert into teams (name, country_id) values ('Home FC', %s) returning id", country)
    away = _one(db, "insert into teams (name, country_id) values ('Away FC', %s) returning id", country)
    return _one(
        db,
        "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) "
        "values (%s, %s, %s, '2023-08-12 14:00Z') returning id",
        season, home, away,
    )


def test_core_tables_exist(db):
    rows = db.execute("select tablename from pg_tables where schemaname = 'public'").fetchall()
    assert CORE_TABLES <= {r[0] for r in rows}


def test_core_tables_have_rls_and_no_policies(db):
    rows = db.execute(
        "select relname, relrowsecurity from pg_class "
        "where relnamespace = 'public'::regnamespace and relkind = 'r'"
    ).fetchall()
    rls = dict(rows)
    assert all(rls[t] for t in CORE_TABLES), {t for t in CORE_TABLES if not rls[t]}
    assert _one(db, "select count(*) from pg_policies where schemaname = 'public'") == 0


def test_updated_at_trigger_bumps_on_update(db):
    cid = _one(db, "insert into countries (name) values ('Spain') returning id")
    before = _one(db, "select updated_at from countries where id = %s", cid)
    db.execute("update countries set code = 'ES' where id = %s", (cid,))
    after = _one(db, "select updated_at from countries where id = %s", cid)
    assert after > before


def test_external_ref_unique(db):
    sql = (
        "insert into external_refs (entity_type, source, source_id, confidence, status) "
        "values ('team', 'api-football', '33', 1.0, 'linked')"
    )
    db.execute(sql)
    with pytest.raises(errors.UniqueViolation):
        db.execute(sql)


def test_external_ref_status_check(db):
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "insert into external_refs (entity_type, source, source_id, status) "
            "values ('team', 'api-football', '34', 'maybe')"
        )


def test_match_event_source_hash_unique(db):
    match = _make_match(db)
    team = _one(db, "select home_team_id from matches where id = %s", match)
    sql = (
        "insert into match_events (match_id, team_id, minute, type, detail, source_hash) "
        "values (%s, %s, 23, 'Card', 'Yellow Card', 'abc123')"
    )
    db.execute(sql, (match, team))
    with pytest.raises(errors.UniqueViolation):
        db.execute(sql, (match, team))


def test_deleting_match_cascades_to_events_but_team_is_restricted(db):
    match = _make_match(db)
    team = _one(db, "select home_team_id from matches where id = %s", match)
    db.execute(
        "insert into match_events (match_id, team_id, minute, type, source_hash) "
        "values (%s, %s, 5, 'Goal', 'h1')", (match, team),
    )
    with pytest.raises(errors.ForeignKeyViolation):
        db.execute("delete from teams where id = %s", (team,))
    db.execute("delete from matches where id = %s", (match,))
    assert _one(db, "select count(*) from match_events") == 0


def test_review_item_kind_check(db):
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "insert into review_items (kind, subject_type, subject_id, payload) "
            "values ('banana', 'match', 1, '{}')"
        )
    db.execute(
        "insert into review_items (kind, subject_type, subject_id, payload) "
        "values ('player_link', 'match_event', 1, '{}')"
    )
    assert _one(db, "select status from review_items") == "open"
