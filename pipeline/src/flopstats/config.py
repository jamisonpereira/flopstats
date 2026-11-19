"""Runtime settings. Secrets come from the environment or a git-ignored `.env` in the
working directory (run commands from the repo root). Values are SecretStr so they never
appear in repr/str/logs."""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_VERIFIER_RE = re.compile(r"^verifier_(.+)_key$", re.IGNORECASE)


class _VerifierKeysSource(PydanticBaseSettingsSource):
    """Collects VERIFIER_<NAME>_KEY entries from env and .env into `verifier_keys`."""

    def __init__(self, settings_cls, *sources: PydanticBaseSettingsSource):
        super().__init__(settings_cls)
        self._sources = sources

    def get_field_value(self, field, field_name):  # pragma: no cover - unused
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        keys: dict[str, str] = {}
        for source in self._sources:  # later sources win: env overrides .env
            for name, value in (getattr(source, "env_vars", None) or {}).items():
                m = _VERIFIER_RE.match(name)
                if m and value:
                    keys[m.group(1).lower()] = value
        return {"verifier_keys": keys} if keys else {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    apifootball_key: SecretStr | None = None
    supabase_url: str | None = None
    supabase_service_key: SecretStr | None = None
    database_url: SecretStr | None = None
    gemini_key: SecretStr | None = None
    footballia_username: SecretStr | None = None
    footballia_password: SecretStr | None = None
    budget_usd: Decimal = Field(default=Decimal("500"), validation_alias="FLOPSTATS_BUDGET_USD")
    verifier_keys: dict[str, SecretStr] = Field(default_factory=dict)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        dotenv = dotenv_settings if isinstance(dotenv_settings, DotEnvSettingsSource) else None
        env = env_settings if isinstance(env_settings, EnvSettingsSource) else None
        verifiers = _VerifierKeysSource(settings_cls, *[s for s in (dotenv, env) if s])
        return (init_settings, env_settings, dotenv_settings, verifiers, file_secret_settings)

    def secret_values(self) -> list[str]:
        """Every secret value, for redacting text before it is shown."""
        out = [
            s.get_secret_value()
            for s in (
                self.apifootball_key,
                self.supabase_service_key,
                self.database_url,
                self.gemini_key,
                self.footballia_username,
                self.footballia_password,
                *self.verifier_keys.values(),
            )
            if s is not None and s.get_secret_value()
        ]
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
