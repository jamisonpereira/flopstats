from decimal import Decimal

import psycopg
from pydantic import SecretStr

from conftest import LOCAL_DB_URL
from flopstats import costs, jobs
from flopstats.db import connect


def test_writes_through_connect_are_committed(db, settings):
    settings.database_url = SecretStr(LOCAL_DB_URL)
    conn = connect(settings)
    try:
        conn.execute("select 1")  # a read first must not swallow later writes
        jobs.enqueue(conn, "fetch", "k1", {})
        costs.record(conn, service="gemini", model="m", units={}, usd=Decimal("0.01"), idempotency_key="x")
    finally:
        conn.close()
    with psycopg.connect(LOCAL_DB_URL) as other:
        assert other.execute("select count(*) from jobs").fetchone()[0] == 1
        assert other.execute("select count(*) from cost_ledger").fetchone()[0] == 1


def test_connections_notice_a_dead_network_instead_of_hanging(settings):
    # Pilot 2: a home internet drop left the runner waiting forever on a dead connection.
    settings.database_url = SecretStr(LOCAL_DB_URL)
    conn = connect(settings)
    try:
        params = conn.info.get_parameters()
        assert params.get("keepalives") == "1"
        assert int(params["keepalives_idle"]) <= 30 and int(params["keepalives_count"]) <= 3
        assert int(params["tcp_user_timeout"]) <= 60_000
    finally:
        conn.close()
