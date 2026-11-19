import pytest

FAKE_ENV = {
    "APIFOOTBALL_KEY": "af-secret-123",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "svc-secret-456",
    "DATABASE_URL": "postgresql://postgres:dbpass-789@db.example.co:5432/postgres",
    "GEMINI_KEY": "gem-secret-abc",
    "FOOTBALLIA_USERNAME": "fb-user-def",
    "FOOTBALLIA_PASSWORD": "fb-pass-ghi",
    "VERIFIER_OTHERCO_KEY": "ver-secret-jkl",
}
SECRET_VALUES = [v for k, v in FAKE_ENV.items() if k != "SUPABASE_URL"]


@pytest.fixture
def fake_env(monkeypatch):
    for k, v in FAKE_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("FLOPSTATS_BUDGET_USD", raising=False)
    return FAKE_ENV


@pytest.fixture
def settings(fake_env):
    from flopstats.config import Settings

    return Settings(_env_file=None)


# --- Local Supabase database (never the hosted project) -------------------------------
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DB_URL = os.environ.get(
    "FLOPSTATS_TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)


def _assert_local(url: str) -> None:
    host = urlparse(url).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(f"test database must be local, got host {host!r}")


@pytest.fixture(scope="session")
def _db_reset():
    """Rebuild the local database from migrations once per test session."""
    _assert_local(LOCAL_DB_URL)
    # `supabase db reset` targets the local stack by default (CLI v3); never pass --remote.
    subprocess.run(["supabase", "db", "reset", "--no-seed"], cwd=REPO_ROOT, check=True)


@pytest.fixture
def db(_db_reset):
    """Autocommit connection to the local database, with every public table emptied first."""
    import psycopg

    _assert_local(LOCAL_DB_URL)
    conn = psycopg.connect(LOCAL_DB_URL, autocommit=True)
    tables = [
        r[0]
        for r in conn.execute(
            "select tablename from pg_tables where schemaname = 'public'"
        ).fetchall()
    ]
    if tables:
        conn.execute(
            "truncate " + ", ".join(f'public."{t}"' for t in tables) + " restart identity cascade"
        )
    yield conn
    conn.close()
