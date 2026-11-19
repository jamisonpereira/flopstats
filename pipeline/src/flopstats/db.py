"""Database connection helpers."""

from __future__ import annotations

import psycopg

from flopstats.config import Settings, get_settings


def connect(settings: Settings | None = None) -> psycopg.Connection:
    settings = settings or get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(settings.database_url.get_secret_value(), connect_timeout=10)
