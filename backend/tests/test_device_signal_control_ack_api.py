from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.device import acknowledge_device_signal_control
from app.models.domain import DeviceCredential


def test_device_signal_control_ack_uses_authenticated_device():
    command_id = uuid4()
    device_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.id = device_id

    db = Mock()
    expected = Mock()

    with patch(
        "app.api.device.SignalControlAckService"
    ) as service_class:
        service_class.return_value.acknowledge.return_value = expected

        result = acknowledge_device_signal_control(
            command_id=command_id,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.assert_called_once_with(db)
    service_class.return_value.acknowledge.assert_called_once_with(
        command_id=command_id,
        device_id=device_id,
    )


def test_device_signal_control_ack_requires_device_identity():
    # The endpoint receives the authenticated device from the dependency.
    # This test confirms it passes that identity to the service rather than
    # accepting a device_id from the request.
    command_id = uuid4()
    device = Mock(spec=DeviceCredential)
    device.id = uuid4()

    db = Mock()
    expected = Mock()

    with patch(
        "app.api.device.SignalControlAckService"
    ) as service_class:
        service_class.return_value.acknowledge.return_value = expected

        result = acknowledge_device_signal_control(
            command_id=command_id,
            device=device,
            db=db,
        )

    assert result is expected
    service_class.return_value.acknowledge.assert_called_once_with(
        command_id=command_id,
        device_id=device.id,
    )