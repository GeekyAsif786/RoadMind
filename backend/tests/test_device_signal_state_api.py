from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.device import get_device_signal_state
from app.models.domain import DeviceCredential


def test_device_signal_state_uses_device_intersection():
    intersection_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.intersection_id = intersection_id

    db = Mock()
    expected_state = Mock()

    with patch("app.api.device.SignalStateService") as service_class:
        service_class.return_value.get.return_value = expected_state

        result = get_device_signal_state(
            device=device,
            db=db,
        )

    assert result is expected_state
    service_class.assert_called_once_with(db)
    service_class.return_value.get.assert_called_once_with(intersection_id)


def test_device_signal_state_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.intersection_id = None

    db = Mock()

    with pytest.raises(HTTPException) as exc:
        get_device_signal_state(
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"