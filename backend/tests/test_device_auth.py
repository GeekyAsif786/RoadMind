from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.device_credentials import hash_device_credential
from app.models.domain import DeviceCredential
from app.core.auth import get_current_device, require_device_scope

def test_get_current_device_rejects_missing_credential():
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        get_current_device("", db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing device credential"


def test_get_current_device_rejects_invalid_format():
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        get_current_device("not-a-valid-credential", db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid device credential"


def test_get_current_device_rejects_unknown_credential():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_current_device("dev_unknown.secret", db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid device credential"

def test_get_current_device_accepts_valid_credential():
    db = MagicMock()

    secret = "test-device-secret"
    credential_id = "dev_test123"

    device = MagicMock(spec=DeviceCredential)
    device.credential_id = credential_id
    device.credential_hash = hash_device_credential(secret)
    device.is_active = True
    device.expires_at = None
    device.last_used_at = None

    db.scalar.return_value = device

    result = get_current_device(
        f"{credential_id}.{secret}",
        db,
    )

    assert result is device
    assert device.last_used_at is not None
    db.commit.assert_called_once()

def test_get_current_device_rejects_inactive_device():
    db = MagicMock()

    # The query filters inactive devices, so the database should return no match.
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_current_device("dev_inactive.secret", db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid device credential"


def test_get_current_device_rejects_expired_device():
    from datetime import UTC, datetime, timedelta

    db = MagicMock()

    secret = "expired-secret"
    credential_id = "dev_expired"

    device = MagicMock(spec=DeviceCredential)
    device.credential_id = credential_id
    device.credential_hash = hash_device_credential(secret)
    device.is_active = True
    device.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    device.last_used_at = None

    db.scalar.return_value = device

    with pytest.raises(HTTPException) as exc:
        get_current_device(
            f"{credential_id}.{secret}",
            db,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Device credential expired"

def test_require_device_scope_allows_device_with_scope():
    device = MagicMock(spec=DeviceCredential)
    device.scopes = ["telemetry:write", "detection:write"]

    dependency = require_device_scope("telemetry:write")
    result = dependency(device)

    assert result is device

def test_require_device_scope_rejects_missing_scope():
    device = MagicMock(spec=DeviceCredential)
    device.scopes = ["telemetry:write"]

    dependency = require_device_scope("detection:write")

    with pytest.raises(HTTPException) as exc:
        dependency(device)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device lacks required scope"