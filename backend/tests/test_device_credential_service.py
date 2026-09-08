from unittest.mock import MagicMock

import pytest
from uuid import uuid4
from app.core.device_credentials import (
    generate_device_credential,
    hash_device_credential,
    verify_device_credential,
)
from sqlalchemy.exc import IntegrityError
from app.models.domain import DeviceCredential
from app.services.device_credential_service import DeviceCredentialService


def test_generated_device_credential_can_be_verified():
    secret = generate_device_credential()
    hashed = hash_device_credential(secret)

    assert verify_device_credential(secret, hashed)


def test_create_rejects_duplicate_name():
    db = MagicMock()

    existing = MagicMock(spec=DeviceCredential)
    db.scalar.return_value = existing

    with pytest.raises(ValueError, match="Device credential name already exists"):
        DeviceCredentialService().create(
            db=db,
            name="existing-device",
            scopes=["telemetry:write"],
        )


def test_create_rejects_unknown_intersection():
    db = MagicMock()
    db.scalar.side_effect = [None, None]

    with pytest.raises(ValueError, match="Intersection not found"):
        DeviceCredentialService().create(
            db=db,
            name="new-device",
            scopes=["telemetry:write"],
            intersection_id=uuid4(),
        )

def test_create_rolls_back_on_integrity_error():
    db = MagicMock()

    # First scalar() call: no duplicate name.
    # Second scalar() call isn't needed because no intersection was supplied.
    db.scalar.return_value = None
    db.commit.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate"),
    )

    with pytest.raises(IntegrityError):
        DeviceCredentialService().create(
            db=db,
            name="database-error-test",
            scopes=["telemetry:write"],
        )

    db.rollback.assert_called_once()

def test_revoke_rejects_unknown_device():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(ValueError, match="Device credential not found"):
        DeviceCredentialService().revoke(
            db=db,
            device_id=uuid4(),
        )


def test_revoke_rejects_already_revoked_device():
    db = MagicMock()

    device = MagicMock(spec=DeviceCredential)
    device.is_active = False

    db.scalar.return_value = device

    with pytest.raises(ValueError, match="Device credential already revoked"):
        DeviceCredentialService().revoke(
            db=db,
            device_id=uuid4(),
        )

def test_list_returns_devices_newest_first():
    db = MagicMock()

    first = MagicMock(spec=DeviceCredential)
    second = MagicMock(spec=DeviceCredential)

    db.scalars.return_value.all.return_value = [second, first]

    result = DeviceCredentialService().list(db)

    assert result == [second, first]