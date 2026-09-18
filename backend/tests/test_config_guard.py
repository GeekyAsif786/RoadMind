"""Tests for the production API-key startup guard in app.core.config."""

import pytest


def _clear_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_production_with_default_api_key_fails_fast(monkeypatch, tmp_path):
    from app.core.config import DEFAULT_INSECURE_API_KEY, get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_KEY", DEFAULT_INSECURE_API_KEY)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="default development API key"):
        get_settings()

    get_settings.cache_clear()


def test_production_with_secure_settings_boots(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_KEY", "a-real-strong-key")
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "false")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://admin.roadmind.example",
    )
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))

    get_settings.cache_clear()

    settings = get_settings()

    assert settings.environment == "production"
    assert settings.api_key == "a-real-strong-key"
    assert settings.enable_auth is True
    assert settings.auto_create_tables is False
    assert settings.session_cookie_secure is True
    assert settings.cors_origin_list == [
        "https://admin.roadmind.example"
    ]

    get_settings.cache_clear()

def test_development_with_default_api_key_is_allowed(monkeypatch, tmp_path):
    from app.core.config import DEFAULT_INSECURE_API_KEY, get_settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("API_KEY", DEFAULT_INSECURE_API_KEY)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.api_key == DEFAULT_INSECURE_API_KEY

    get_settings.cache_clear()
