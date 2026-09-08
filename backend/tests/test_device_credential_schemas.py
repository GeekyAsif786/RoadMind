from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import DeviceCredentialCreate


def test_device_credential_create_accepts_valid_data():
    payload = DeviceCredentialCreate(
        name="edge-camera-01",
        scopes=["telemetry:write", "detection:write"],
        intersection_id=uuid4(),
    )

    assert payload.name == "edge-camera-01"
    assert payload.scopes == ["telemetry:write", "detection:write"]


def test_device_credential_create_requires_scope():
    with pytest.raises(ValidationError):
        DeviceCredentialCreate(
            name="edge-camera-01",
            scopes=[],
        )


def test_device_credential_create_allows_no_intersection():
    payload = DeviceCredentialCreate(
        name="central-api-client",
        scopes=["prediction:read"],
    )

    assert payload.intersection_id is None

def test_device_credential_create_rejects_unknown_scope():
    with pytest.raises(ValidationError):
        DeviceCredentialCreate(
            name="edge-camera-01",
            scopes=["telemetry:write", "admin:everything"],
        )


def test_device_credential_create_removes_duplicate_scopes():
    payload = DeviceCredentialCreate(
        name="edge-camera-01",
        scopes=["telemetry:write", "telemetry:write"],
    )

    assert payload.scopes == ["telemetry:write"]