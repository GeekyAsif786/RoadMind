from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.device_credentials import create_device_credential
from app.schemas import DeviceCredentialCreate
from sqlalchemy.exc import IntegrityError


def test_create_device_credential_maps_integrity_error_to_409():
    db = MagicMock()

    payload = DeviceCredentialCreate(
        name="race-test-device",
        scopes=["telemetry:write"],
    )

    with patch(
        "app.api.device_credentials.DeviceCredentialService.create",
        side_effect=IntegrityError(
            "INSERT",
            {},
            Exception("duplicate"),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            create_device_credential(payload, db)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Device credential name already exists"