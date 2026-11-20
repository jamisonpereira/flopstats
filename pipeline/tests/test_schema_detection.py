import pytest
from psycopg import errors

DETECTION_TABLES = {"videos", "detection_runs", "windows", "candidates", "verifications", "incidents",
                    "incident_players", "clips", "reviews"}


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def ctx(db):
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('PL', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    h = _one(db, "insert into teams (name) values ('Home') returning id")
    a = _one(db, "insert into teams (name) values ('Away') returning id")
    m = _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, now()) returning id", s, h, a)
    v = _one(db, "insert into videos (match_id, source, source_url, duration_s) values (%s, 'footballia', 'https://footballia.eu/matches/x', 5700) returning id", m)
    r = _one(db, "insert into detection_runs (name, config) values ('pilot-1', '{\"window_s\": 20, \"step_s\": 10}') returning id")
    return {"match": m, "home": h, "video": v, "run": r}


def _incident(db, ctx, type_="dive", key="k1"):
    return _one(
        db,
        "insert into incidents (run_id, match_id, video_id, type, video_start_s, video_end_s, team_id, "
        "confidence, status, dedupe_key) values (%s, %s, %s, %s, 100, 112, %s, 0.8, 'review', %s) returning id",
        ctx["run"], ctx["match"], ctx["video"], type_, ctx["home"], key,
    )


def test_detection_tables_exist(db):
    rows = db.execute("select tablename from pg_tables where schemaname = 'public'").fetchall()
    assert DETECTION_TABLES <= {r[0] for r in rows}


def test_detection_tables_have_rls(db):
    rls = dict(db.execute(
        "select relname, relrowsecurity from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r'"
    ).fetchall())
    assert all(rls[t] for t in DETECTION_TABLES)


@pytest.mark.parametrize("type_", ["dive", "exaggeration", "feigned_injury", "time_wasting"])
def test_incident_type_check_accepts_the_four_types(db, ctx, type_):
    _incident(db, ctx, type_, key=type_)


def test_incident_type_check_rejects_unknown(db, ctx):
    with pytest.raises(errors.CheckViolation):
        _incident(db, ctx, "flop")


def test_incident_dedupe_unique(db, ctx):
    _incident(db, ctx, key="same")
    with pytest.raises(errors.UniqueViolation):
        _incident(db, ctx, "exaggeration", key="same")


def test_window_unique_per_run_video_start(db, ctx):
    sql = "insert into windows (run_id, video_id, start_s, end_s, score) values (%s, %s, 0, 20, 0.1)"
    db.execute(sql, (ctx["run"], ctx["video"]))
    with pytest.raises(errors.UniqueViolation):
        db.execute(sql, (ctx["run"], ctx["video"]))


def test_verification_unique_per_candidate_model(db, ctx):
    cand = _one(db, "insert into candidates (run_id, video_id, start_s, end_s, final_score, status) values (%s, %s, 0, 20, 0.7, 'pending') returning id", ctx["run"], ctx["video"])
    sql = "insert into verifications (candidate_id, model, answers, confidence, usd) values (%s, 'gemini-pro', '{}', 0.9, 0.01)"
    db.execute(sql, (cand,))
    with pytest.raises(errors.UniqueViolation):
        db.execute(sql, (cand,))
    with pytest.raises(errors.CheckViolation):
        db.execute("update candidates set status = 'maybe' where id = %s", (cand,))


def test_status_role_decision_checks(db, ctx):
    inc = _incident(db, ctx)
    with pytest.raises(errors.CheckViolation):
        db.execute("update incidents set status = 'unsure' where id = %s", (inc,))
    with pytest.raises(errors.CheckViolation):
        db.execute("update incidents set ref_decision = 'booking' where id = %s", (inc,))
    with pytest.raises(errors.CheckViolation):
        db.execute("insert into incident_players (incident_id, team_id, role) values (%s, %s, 'victim')", (inc, ctx["home"]))
    with pytest.raises(errors.CheckViolation):
        db.execute("insert into reviews (incident_id, decision) values (%s, 'maybe')", (inc,))
    with pytest.raises(errors.CheckViolation):
        db.execute("update videos set sync_status = 'done' where id = %s", (ctx["video"],))


def test_clip_one_per_incident(db, ctx):
    inc = _incident(db, ctx)
    sql = "insert into clips (incident_id, path, duration_s, bytes) values (%s, 'clips/1/1.mp4', 14, 1000)"
    db.execute(sql, (inc,))
    with pytest.raises(errors.UniqueViolation):
        db.execute(sql, (inc,))


def test_cost_ledger_run_id_references_detection_runs(db, ctx):
    db.execute("insert into cost_ledger (run_id, service, usd, idempotency_key) values (%s, 'gemini', 0.01, 'a')", (ctx["run"],))
    with pytest.raises(errors.ForeignKeyViolation):
        db.execute("insert into cost_ledger (run_id, service, usd, idempotency_key) values (999999, 'gemini', 0.01, 'b')")


def test_reviewed_incident_cannot_be_silently_deleted_with_its_run(db, ctx):
    inc = _incident(db, ctx)
    db.execute("insert into reviews (incident_id, decision, reason) values (%s, 'confirm', 'clear dive')", (inc,))
    with pytest.raises(errors.ForeignKeyViolation):
        db.execute("delete from detection_runs where id = %s", (ctx["run"],))
