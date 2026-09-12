from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.device import report_device_signal_state
from app.models.domain import DeviceCredential
from app.schemas import SignalControllerStateCreate


def test_device_signal_state_write_uses_device_intersection():
    intersection_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.intersection_id = intersection_id

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
    )

    db = Mock()
    expected = Mock()

    with patch(
        "app.api.device.SignalControllerStateService"
    ) as service_class:
        service_class.return_value.update.return_value = expected

        result = report_device_signal_state(
            payload=payload,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.assert_called_once_with(db)
    service_class.return_value.update.assert_called_once_with(
        intersection_id=intersection_id,
        payload=payload,
    )


def test_device_signal_state_write_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.intersection_id = None

    payload = SignalControllerStateCreate(
        current_phase=1,
        phase_state="red",
        controller_status="online",
    )

    db = Mock()

    with pytest.raises(HTTPException) as exc:
        report_device_signal_state(
            payload=payload,
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"

def test_device_signal_state_write_passes_reported_plan():
    intersection_id = uuid4()
    plan_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.intersection_id = intersection_id

    payload = SignalControllerStateCreate(
        current_phase=3,
        phase_state="yellow",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    db = Mock()
    expected = Mock()

    with patch(
        "app.api.device.SignalControllerStateService"
    ) as service_class:
        service_class.return_value.update.return_value = expected

        result = report_device_signal_state(
            payload=payload,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.assert_called_once_with(db)
    service_class.return_value.update.assert_called_once_with(
        intersection_id=intersection_id,
        payload=payload,
    )