from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import SignalControlCommand
from app.services.signal_control_ack_service import SignalControlAckService


def make_command(
    *,
    device_id,
    status="accepted",
    expires_at=None,
):
    command = Mock(spec=SignalControlCommand)
    command.id = uuid4()
    command.device_id = device_id
    command.intersection_id = uuid4()
    command.plan_id = uuid4()
    command.phase_number = 1
    command.status = status
    command.expires_at = expires_at
    command.acknowledged_at = None
    return command


def make_phase():
    phase = Mock()
    phase.direction = "N"
    phase.green_seconds = 22
    phase.yellow_seconds = 4
    return phase


def test_acknowledge_accepts_own_active_command():
    db = Mock()
    service = SignalControlAckService(db)

    device_id = uuid4()
    command = make_command(
        device_id=device_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    acknowledged = make_command(
        device_id=device_id,
        expires_at=command.expires_at,
        status="acknowledged",
    )
    acknowledged.id = command.id
    acknowledged.intersection_id = command.intersection_id
    acknowledged.plan_id = command.plan_id
    acknowledged.phase_number = command.phase_number

    service.commands.get = Mock(return_value=command)
    service.commands.acknowledge = Mock(return_value=acknowledged)
    service.signals.get_phase = Mock(return_value=make_phase())

    result = service.acknowledge(
        command_id=command.id,
        device_id=device_id,
    )

    assert result.command_id == command.id
    assert result.intersection_id == command.intersection_id
    assert result.plan_id == command.plan_id
    assert result.phase_number == command.phase_number
    assert result.direction == "N"
    assert result.green_seconds == 22
    assert result.yellow_seconds == 4
    assert result.status == "acknowledged"
    assert result.expires_at == acknowledged.expires_at

    service.commands.get.assert_called_once_with(command.id)
    service.commands.acknowledge.assert_called_once()
    ack_args = service.commands.acknowledge.call_args

    assert ack_args.kwargs["command"] is command
    assert isinstance(ack_args.kwargs["acknowledged_at"], datetime)
    service.signals.get_phase.assert_called_once_with(
        plan_id=acknowledged.plan_id,
        phase_number=acknowledged.phase_number,
    )


def test_acknowledge_rejects_unknown_command():
    db = Mock()
    service = SignalControlAckService(db)

    command_id = uuid4()
    device_id = uuid4()

    service.commands.get = Mock(return_value=None)
    service.commands.acknowledge = Mock()

    with pytest.raises(HTTPException) as exc:
        service.acknowledge(
            command_id=command_id,
            device_id=device_id,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Signal control command not found"
    service.commands.acknowledge.assert_not_called()


def test_acknowledge_rejects_command_owned_by_another_device():
    db = Mock()
    service = SignalControlAckService(db)

    owner_device_id = uuid4()
    other_device_id = uuid4()

    command = make_command(
        device_id=owner_device_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    service.commands.get = Mock(return_value=command)
    service.commands.acknowledge = Mock()

    with pytest.raises(HTTPException) as exc:
        service.acknowledge(
            command_id=command.id,
            device_id=other_device_id,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not authorized to acknowledge this command"
    service.commands.acknowledge.assert_not_called()


def test_acknowledge_rejects_non_accepted_command():
    db = Mock()
    service = SignalControlAckService(db)

    device_id = uuid4()

    command = make_command(
        device_id=device_id,
        status="acknowledged",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    service.commands.get = Mock(return_value=command)
    service.commands.acknowledge = Mock()

    with pytest.raises(HTTPException) as exc:
        service.acknowledge(
            command_id=command.id,
            device_id=device_id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Signal control command is not awaiting acknowledgement"
    service.commands.acknowledge.assert_not_called()


def test_acknowledge_rejects_expired_command():
    db = Mock()
    service = SignalControlAckService(db)

    device_id = uuid4()

    command = make_command(
        device_id=device_id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    service.commands.get = Mock(return_value=command)
    service.commands.acknowledge = Mock()

    with pytest.raises(HTTPException) as exc:
        service.acknowledge(
            command_id=command.id,
            device_id=device_id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Signal control command has expired"
    service.commands.acknowledge.assert_not_called()