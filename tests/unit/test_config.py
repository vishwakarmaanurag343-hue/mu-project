"""Unit tests for configuration loading and secret safety."""

from pathlib import Path

from pydantic import SecretStr

from alphalens.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Settings should load reasonable defaults when no env is provided."""
    settings = Settings()
    assert settings.app_env == "dev"
    assert settings.log_level == "INFO"
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_base_url is None
    assert settings.llm_model is None
    assert settings.llm_api_key is None
    assert settings.cache_dir == Path("./cache")


def test_settings_secret_masking() -> None:
    """Sensitive settings must never expose raw secrets in string representations."""
    secret_val = "super-secret-key-12345"
    settings = Settings(llm_api_key=SecretStr(secret_val))

    assert secret_val not in str(settings.llm_api_key)
    assert secret_val not in repr(settings.llm_api_key)
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == secret_val


def test_get_settings_cached() -> None:
    """get_settings should return the cached singleton instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
