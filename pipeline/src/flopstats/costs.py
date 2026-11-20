"""AI spend ledger and the budget guard. Every charge is recorded once per idempotency key."""

from __future__ import annotations

from decimal import Decimal

import psycopg
from psycopg.types.json import Jsonb

from flopstats.config import Settings


class BudgetExceeded(Exception):
    pass


def record(
    conn: psycopg.Connection,
    *,
    service: str,
    model: str | None,
    units: dict,
    usd: Decimal,
    idempotency_key: str,
    run_id: int | None = None,
    match_id: int | None = None,
) -> bool:
    """Record a charge. Returns False (and records nothing) if the key already exists."""
    with conn.transaction():
        row = conn.execute(
            "insert into cost_ledger (run_id, match_id, service, model, units, usd, idempotency_key) "
            "values (%s, %s, %s, %s, %s, %s, %s) on conflict (idempotency_key) do nothing returning id",
            (run_id, match_id, service, model, Jsonb(units), usd, idempotency_key),
        ).fetchone()
    return row is not None


def spent(conn: psycopg.Connection) -> Decimal:
    return conn.execute("select coalesce(sum(usd), 0) from cost_ledger").fetchone()[0]


def guard(conn: psycopg.Connection, settings: Settings, estimate_usd: Decimal) -> None:
    """Raise BudgetExceeded if this spend would take the total over the budget."""
    total = spent(conn)
    if total + estimate_usd > settings.budget_usd:
        raise BudgetExceeded(
            f"spent {total} + estimate {estimate_usd} would exceed budget {settings.budget_usd} USD"
        )
