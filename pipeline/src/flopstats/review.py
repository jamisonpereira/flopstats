"""Review items: the "never guess silently" queue that Jamison works through."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

KINDS = ("match_link", "video_sync", "player_link", "flop_verdict", "flop_player")


def create(conn: psycopg.Connection, kind: str, subject_type: str, subject_id: int | None, payload: dict) -> int:
    """Open a review item. While one is open for (kind, subject_type, subject_id), return it instead."""
    with conn.transaction():
        # Serialize concurrent creators for the same subject.
        conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"review:{kind}:{subject_type}:{subject_id}",),
        )
        row = conn.execute(
            "select id from review_items where kind = %s and subject_type = %s "
            "and subject_id is not distinct from %s and status = 'open' order by id limit 1",
            (kind, subject_type, subject_id),
        ).fetchone()
        if row:
            return row[0]
        return conn.execute(
            "insert into review_items (kind, subject_type, subject_id, payload) values (%s, %s, %s, %s) returning id",
            (kind, subject_type, subject_id, Jsonb(payload)),
        ).fetchone()[0]


def resolve(conn: psycopg.Connection, item_id: int, resolution: dict) -> None:
    with conn.transaction():
        cur = conn.execute(
            "update review_items set status = 'resolved', resolution = %s, resolved_at = now() "
            "where id = %s and status = 'open'",
            (Jsonb(resolution), item_id),
        )
        if cur.rowcount != 1:
            raise ValueError(f"review item {item_id} is not open")
