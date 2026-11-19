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
