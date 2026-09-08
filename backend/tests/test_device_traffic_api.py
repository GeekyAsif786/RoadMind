from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.traffic import create_observation
from app.models.domain import DeviceCredential


def make_payload(intersection_id):
    return Mock(
        intersection_id=intersection_id,
    )


def test_device_telemetry_rejects_other_intersection():
    device = Mock(spec=DeviceCredential)
    device.intersection_id = uuid4()

    payload = make_payload(uuid4())
    db = Mock()

    with pytest.raises(HTTPException) as exc:
        create_observation(
            payload=payload,
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not authorized for this intersection"


def test_device_telemetry_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.intersection_id = None

    payload = make_payload(uuid4())
    db = Mock()

    with pytest.raises(HTTPException) as exc:
        create_observation(
            payload=payload,
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"


def test_device_telemetry_allows_own_intersection():
    intersection_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.intersection_id = intersection_id

    payload = make_payload(intersection_id)
    db = Mock()
    expected = Mock()

    with patch("app.api.traffic.TrafficService") as service_class:
        service_class.return_value.create_observation.return_value = expected

        result = create_observation(
            payload=payload,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.assert_called_once_with(db)
    service_class.return_value.create_observation.assert_called_once_with(payload)