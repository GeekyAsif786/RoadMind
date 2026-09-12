from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.device import create_device_signal_control
from app.models.domain import DeviceCredential
from app.schemas import SignalControlCommand


def test_device_signal_control_uses_device_intersection():
    intersection_id = uuid4()
    plan_id = uuid4()
    device_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.id = device_id
    device.intersection_id = intersection_id

    payload = SignalControlCommand(
        plan_id=plan_id,
        phase_number=2,
    )

    db = Mock()
    expected = Mock()

    with patch(
        "app.api.device.SignalControlService"
    ) as service_class:
        service_class.return_value.create_command.return_value = expected

        result = create_device_signal_control(
            payload=payload,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.assert_called_once_with(db)
    service_class.return_value.create_command.assert_called_once_with(
        device_id=device_id,
        intersection_id=intersection_id,
        payload=payload,
    )


def test_device_signal_control_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.id = uuid4()
    device.intersection_id = None

    payload = SignalControlCommand(
        plan_id=uuid4(),
        phase_number=2,
    )

    db = Mock()

    with pytest.raises(HTTPException) as exc:
        create_device_signal_control(
            payload=payload,
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"