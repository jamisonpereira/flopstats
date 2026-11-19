import psycopg

from conftest import LOCAL_DB_URL
from flopstats import jobs


def _status(db, job_id):
    return db.execute("select status, attempts from jobs where id = %s", (job_id,)).fetchone()


def test_enqueue_idempotent(db):
    a = jobs.enqueue(db, "fetch", "fixtures:39:2023", {"league": 39})
    b = jobs.enqueue(db, "fetch", "fixtures:39:2023", {"league": 39})
    assert a == b
    assert db.execute("select count(*) from jobs").fetchone()[0] == 1
    jobs.complete(db, a)
    assert jobs.enqueue(db, "fetch", "fixtures:39:2023", {"league": 39}) == a
    assert _status(db, a)[0] == "done"


def test_enqueue_same_key_different_kind_is_separate(db):
    assert jobs.enqueue(db, "fetch", "k", {}) != jobs.enqueue(db, "build", "k", {})


def test_claim_returns_none_when_empty_and_ignores_other_kinds(db):
    jobs.enqueue(db, "build", "b1", {})
    assert jobs.claim(db, ["fetch"]) is None


def test_claim_marks_running_with_lease(db):
    jid = jobs.enqueue(db, "fetch", "k1", {"x": 1})
    job = jobs.claim(db, ["fetch"], lease_s=60)
    assert job.id == jid and job.kind == "fetch" and job.key == "k1" and job.payload == {"x": 1}
    status, lease_ok = db.execute(
        "select status, locked_until > now() + interval '50 seconds' from jobs where id = %s", (jid,)
    ).fetchone()
    assert status == "running" and lease_ok
    # A running job with a live lease is not handed out again.
    assert jobs.claim(db, ["fetch"]) is None


def test_claim_skips_locked_and_reclaims_expired_lease(db):
    first = jobs.enqueue(db, "fetch", "k1", {})
    second = jobs.enqueue(db, "fetch", "k2", {})
    with psycopg.connect(LOCAL_DB_URL) as other:
        # Another worker holds a row lock on the first job (mid-transaction).
        other.execute("select id from jobs where id = %s for update", (first,))
        job = jobs.claim(db, ["fetch"])
        assert job.id == second
        other.rollback()
    # The second job's worker crashed: its lease runs out and the job is reclaimed.
    db.execute("update jobs set locked_until = now() - interval '1 second' where id = %s", (second,))
    reclaimed = jobs.claim(db, ["fetch"])
    assert reclaimed.id in (first, second)
    again = jobs.claim(db, ["fetch"])
    assert {reclaimed.id, again.id} == {first, second}


def test_fail_with_retry_returns_to_pending_and_increments_attempts(db):
    jid = jobs.enqueue(db, "fetch", "k1", {})
    jobs.claim(db, ["fetch"])
    jobs.fail(db, jid, "HTTP 500", retry=True)
    assert _status(db, jid) == ("pending", 1)
    assert db.execute("select last_error from jobs where id = %s", (jid,)).fetchone()[0] == "HTTP 500"
    assert jobs.claim(db, ["fetch"]).id == jid


def test_fail_without_retry_is_failed_and_not_claimed(db):
    jid = jobs.enqueue(db, "fetch", "k1", {})
    jobs.claim(db, ["fetch"])
    jobs.fail(db, jid, "bad", retry=False)
    assert _status(db, jid) == ("failed", 1)
    assert jobs.claim(db, ["fetch"]) is None


def test_mark_sets_status_and_complete_is_done(db):
    a = jobs.enqueue(db, "detect", "m1", {})
    jobs.mark(db, a, "blocked_budget")
    assert _status(db, a)[0] == "blocked_budget"
    assert jobs.claim(db, ["detect"]) is None
    jobs.mark(db, a, "pending")
    jobs.complete(db, jobs.claim(db, ["detect"]).id)
    assert _status(db, a)[0] == "done"
