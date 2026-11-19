from decimal import Decimal

from conftest import SECRET_VALUES


def test_settings_reads_env(settings):
    assert settings.apifootball_key.get_secret_value() == "af-secret-123"
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_key.get_secret_value() == "svc-secret-456"
    assert settings.database_url.get_secret_value().startswith("postgresql://")
    assert settings.gemini_key.get_secret_value() == "gem-secret-abc"
    assert settings.footballia_username.get_secret_value() == "fb-user-def"
    assert settings.footballia_password.get_secret_value() == "fb-pass-ghi"
    assert settings.budget_usd == Decimal("500")
    assert {k: v.get_secret_value() for k, v in settings.verifier_keys.items()} == {
        "otherco": "ver-secret-jkl"
    }


def test_settings_budget_override(fake_env, monkeypatch):
    from flopstats.config import Settings

    monkeypatch.setenv("FLOPSTATS_BUDGET_USD", "123.45")
    assert Settings(_env_file=None).budget_usd == Decimal("123.45")


def test_settings_never_repr_secrets(settings):
    text = repr(settings) + str(settings)
    for secret in SECRET_VALUES:
        assert secret not in text


def test_settings_reads_dotenv_file_including_verifier_keys(tmp_path, monkeypatch):
    from flopstats.config import Settings

    for k in ("GEMINI_KEY", "VERIFIER_OTHERCO_KEY", "VERIFIER_FILECO_KEY"):
        monkeypatch.delenv(k, raising=False)
    env_file = tmp_path / "fixture.env"
    env_file.write_text("GEMINI_KEY=from-file\nVERIFIER_FILECO_KEY=file-ver\n")
    s = Settings(_env_file=env_file)
    assert s.gemini_key.get_secret_value() == "from-file"
    assert s.verifier_keys["fileco"].get_secret_value() == "file-ver"
