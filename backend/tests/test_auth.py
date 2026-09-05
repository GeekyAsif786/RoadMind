"""Tests for API-key authentication (constant-time comparison).

Behavior must be unchanged from a plain `!=`: valid key passes, wrong/missing
key is rejected with 401, and auth-disabled short-circuits. The only difference
is that the comparison is now constant-time (secrets.compare_digest).
"""

import asyncio

import pytest
from fastapi import HTTPException


def _run(coro):
    return asyncio.run(coro)


def _predictor_settings(monkeypatch, tmp_path, *, enable_auth, api_key):
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ENABLE_AUTH", "true" if enable_auth else "false")
    monkeypatch.setenv("API_KEY", api_key)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()


def test_auth_disabled_allows_any_key(monkeypatch, tmp_path):
    from app.core.auth import require_api_key
    from app.core.config import get_settings

    _predictor_settings(monkeypatch, tmp_path, enable_auth=False, api_key="whatever")
    # Should not raise even with an empty header.
    _run(require_api_key(x_api_key=""))
    get_settings.cache_clear()


def test_valid_key_passes(monkeypatch, tmp_path):
    from app.core.auth import require_api_key
    from app.core.config import get_settings

    _predictor_settings(monkeypatch, tmp_path, enable_auth=True, api_key="correct-key")
    _run(require_api_key(x_api_key="correct-key"))
    get_settings.cache_clear()


def test_wrong_key_rejected(monkeypatch, tmp_path):
    from app.core.auth import require_api_key
    from app.core.config import get_settings

    _predictor_settings(monkeypatch, tmp_path, enable_auth=True, api_key="correct-key")
    with pytest.raises(HTTPException) as exc:
        _run(require_api_key(x_api_key="wrong-key"))
    assert exc.value.status_code == 401
    get_settings.cache_clear()


def test_missing_key_rejected(monkeypatch, tmp_path):
    from app.core.auth import require_api_key
    from app.core.config import get_settings

    _predictor_settings(monkeypatch, tmp_path, enable_auth=True, api_key="correct-key")
    with pytest.raises(HTTPException) as exc:
        _run(require_api_key(x_api_key=""))
    assert exc.value.status_code == 401
    get_settings.cache_clear()
