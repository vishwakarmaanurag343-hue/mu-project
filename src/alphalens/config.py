"""Application settings, loaded from environment and validated at startup."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Secrets use SecretStr so they never print."""

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database & Storage
    database_url: str = "sqlite:///./alphalens.db"
    cache_dir: Path = Path("./cache")
    upload_dir: Path = Path("./data/uploads")

    # Authentication & Session Security
    jwt_secret_key: SecretStr = SecretStr("insecure-dev-secret-change-in-prod-at-least-32-chars")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Evidence & Security Allowlist (Legacy)
    allowed_evidence_domains: list[str] = [
        "bseindia.com",
        "nseindia.com",
        "rbi.org.in",
        "sebi.gov.in",
        "mca.gov.in",
    ]

    # External Data Fetcher & HTTP Client Configuration
    allowed_domains: list[str] = Field(default_factory=list)
    http_connect_timeout: float = 5.0
    http_read_timeout: float = 15.0
    http_write_timeout: float = 5.0
    http_pool_timeout: float = 5.0
    http_max_response_bytes: int = 10 * 1024 * 1024  # 10 MB default
    http_user_agent: str = (
        "AlphaLens/0.1.0 (+https://github.com/alphalens; contact@alphalens.internal)"
    )
    http_rate_limit_per_second: float = 1.0  # Token bucket rate per host
    http_cache_max_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB diskcache cap
    http_offline: bool | None = None  # None -> auto-defaults to True in test env

    # Cache Namespace TTLs (in seconds)
    cache_ttl_prices: int = 12 * 3600  # 12 hours
    cache_ttl_fundamentals: int = 7 * 86400  # 7 days
    cache_ttl_news: int = 3600  # 1 hour
    cache_ttl_constituents: int = 30 * 86400  # 30 days
    cache_ttl_announcements: int = 6 * 3600  # 6 hours

    # Reference Data & Benchmark
    reference_dir: Path = Path("./data/reference")
    allow_price_only_benchmark: bool = False

    # LLM Settings
    llm_provider: str = "openai_compatible"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None

    @property
    def is_offline(self) -> bool:
        """Return effective offline status; defaults to True when app_env is test."""
        if self.http_offline is not None:
            return self.http_offline
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
