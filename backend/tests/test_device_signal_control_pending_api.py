from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.device import get_pending_device_signal_controls
from app.models.domain import DeviceCredential


def test_device_signal_control_pending_uses_authenticated_device():
    device_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.id = device_id
    device.intersection_id = uuid4()

    db = Mock()
    expected = [Mock(), Mock()]

    with patch(
        "app.api.device.SignalControlService"
    ) as service_class:
        service_class.return_value.pending_commands.return_value = expected

        result = get_pending_device_signal_controls(
            device=device,
            db=db,
        )

    assert result == expected

    service_class.assert_called_once_with(db)
    service_class.return_value.pending_commands.assert_called_once_with(
        device_id=device_id,
        limit=10,
    )


def test_device_signal_control_pending_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.id = uuid4()
    device.intersection_id = None

    db = Mock()

    with pytest.raises(HTTPException) as exc:
        get_pending_device_signal_controls(
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"
