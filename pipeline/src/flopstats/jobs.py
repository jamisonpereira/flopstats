"""Postgres job queue and load log. Safe for several workers (FOR UPDATE SKIP LOCKED)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

STATUSES = ("pending", "running", "done", "failed", "needs_review", "blocked_budget")


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    key: str
    payload: dict[str, Any]
    attempts: int


def enqueue(conn: psycopg.Connection, kind: str, key: str, payload: dict) -> int:
    """Add a job once. Re-enqueueing an existing (kind, key) returns its id untouched."""
    with conn.transaction():
        row = conn.execute(
            "insert into jobs (kind, key, payload) values (%s, %s, %s) "
            "on conflict (kind, key) do nothing returning id",
            (kind, key, Jsonb(payload)),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "select id from jobs where kind = %s and key = %s", (kind, key)
            ).fetchone()
    return row[0]


def claim(conn: psycopg.Connection, kinds: list[str], lease_s: int = 900) -> Job | None:
    """Take the oldest claimable job: pending, or running with an expired lease."""
    with conn.transaction():
        row = conn.execute(
            """
            update jobs set status = 'running',
                            locked_until = now() + make_interval(secs => %(lease)s)
            where id = (
              select id from jobs
              where kind = any(%(kinds)s)
                and (status = 'pending'
                     or (status = 'running' and (locked_until is null or locked_until < now())))
              order by id
              limit 1
              for update skip locked
            )
            returning id, kind, key, payload, attempts
            """,
            {"kinds": list(kinds), "lease": lease_s},
        ).fetchone()
    return Job(*row) if row else None


def complete(conn: psycopg.Connection, job_id: int) -> None:
    with conn.transaction():
        conn.execute(
            "update jobs set status = 'done', locked_until = null, last_error = null where id = %s",
            (job_id,),
        )


def fail(conn: psycopg.Connection, job_id: int, err: str, retry: bool) -> None:
    """Record a failure. With retry the job goes back to pending; otherwise it is failed."""
    with conn.transaction():
        conn.execute(
            "update jobs set status = %s, attempts = attempts + 1, last_error = %s, "
            "locked_until = null where id = %s",
            ("pending" if retry else "failed", err, job_id),
        )


def mark(conn: psycopg.Connection, job_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown job status {status!r}")
    with conn.transaction():
        conn.execute(
            "update jobs set status = %s, locked_until = null where id = %s", (status, job_id)
        )

