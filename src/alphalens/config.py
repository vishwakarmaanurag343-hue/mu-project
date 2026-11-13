"""Application settings, loaded from environment and validated at startup."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Secrets use SecretStr so they never print."""

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database & Storage
    database_url: str = "sqlite:///./alphalens.db"
    cache_dir: Path = Path("./cache")

    # Authentication & Session Security
    jwt_secret_key: SecretStr = SecretStr("insecure-dev-secret-change-in-prod-at-least-32-chars")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # LLM Settings
    llm_provider: str = "openai_compatible"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
