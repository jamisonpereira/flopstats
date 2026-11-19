"""Database connection helpers.

Connections are autocommit: each statement commits on its own, and every multi-statement
write in the codebase wraps itself in `with conn.transaction():`, which is then a real
BEGIN/COMMIT. (On a non-autocommit connection that block would only be a savepoint inside
a transaction nobody commits, and the writes would be lost on close.)
"""

from __future__ import annotations

import psycopg

from flopstats.config import Settings, get_settings


def connect(settings: Settings | None = None) -> psycopg.Connection:
    settings = settings or get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(
        settings.database_url.get_secret_value(), autocommit=True, connect_timeout=10
    )
