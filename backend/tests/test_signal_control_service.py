from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import SignalControlCommand as SignalControlCommandModel
from app.schemas import SignalControlCommand
from app.services.signal_control_service import SignalControlService


def make_payload(plan_id=None, phase_number=2):
    return SignalControlCommand(
        plan_id=plan_id or uuid4(),
        phase_number=phase_number,
    )


def make_plan(
    *,
    intersection_id,
    plan_id=None,
    expires_at=None,
):
    plan = Mock()
    plan.id = plan_id or uuid4()
    plan.intersection_id = intersection_id
    plan.expires_at = expires_at
    return plan


def make_phase(*, phase_number=2):
    phase = Mock()
    phase.phase_number = phase_number
    phase.direction = "S"
    phase.green_seconds = 18
    phase.yellow_seconds = 4
    return phase


def test_create_command_accepts_valid_plan_and_phase():
    db = Mock()
    service = SignalControlService(db)

    device_id = uuid4()
    intersection_id = uuid4()
    plan = make_plan(
        intersection_id=intersection_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    phase = make_phase()

    payload = make_payload(
        plan_id=plan.id,
        phase_number=phase.phase_number,
    )

    saved = Mock(spec=SignalControlCommandModel)
    saved.id = uuid4()
    saved.intersection_id = intersection_id
    saved.plan_id = plan.id
    saved.phase_number = phase.phase_number
    saved.status = "accepted"
    saved.expires_at = plan.expires_at

    service.signals.get = Mock(return_value=plan)
    service.signals.get_phase = Mock(return_value=phase)
    service.commands.create = Mock(return_value=saved)

    result = service.create_command(
        device_id=device_id,
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result.command_id == saved.id
    assert result.intersection_id == intersection_id
    assert result.plan_id == plan.id
    assert result.phase_number == phase.phase_number
    assert result.direction == "S"
    assert result.green_seconds == 18
    assert result.yellow_seconds == 4
    assert result.status == "accepted"

    service.signals.get.assert_called_once_with(plan.id)
    service.signals.get_phase.assert_called_once_with(
        plan_id=plan.id,
        phase_number=phase.phase_number,
    )
    service.commands.create.assert_called_once()


def test_create_command_rejects_unknown_plan():
    db = Mock()
    service = SignalControlService(db)

    intersection_id = uuid4()
    payload = make_payload()

    service.signals.get = Mock(return_value=None)
    service.commands.create = Mock()

    with pytest.raises(HTTPException) as exc:
        service.create_command(
            device_id=uuid4(),
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Signal plan not found"
    service.commands.create.assert_not_called()


def test_create_command_rejects_plan_from_other_intersection():
    db = Mock()
    service = SignalControlService(db)

    intersection_id = uuid4()
    foreign_intersection_id = uuid4()

    plan = make_plan(
        intersection_id=foreign_intersection_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    payload = make_payload(plan_id=plan.id)

    service.signals.get = Mock(return_value=plan)
    service.commands.create = Mock()

    with pytest.raises(HTTPException) as exc:
        service.create_command(
            device_id=uuid4(),
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Signal plan does not belong to this intersection"
    service.commands.create.assert_not_called()


def test_create_command_rejects_expired_plan():
    db = Mock()
    service = SignalControlService(db)

    intersection_id = uuid4()

    plan = make_plan(
        intersection_id=intersection_id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    payload = make_payload(plan_id=plan.id)

    service.signals.get = Mock(return_value=plan)
    service.commands.create = Mock()

    with pytest.raises(HTTPException) as exc:
        service.create_command(
            device_id=uuid4(),
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Signal plan has expired"
    service.commands.create.assert_not_called()


def test_create_command_rejects_unknown_phase():
    db = Mock()
    service = SignalControlService(db)

    intersection_id = uuid4()

    plan = make_plan(
        intersection_id=intersection_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    payload = make_payload(
        plan_id=plan.id,
        phase_number=16,
    )

    service.signals.get = Mock(return_value=plan)
    service.signals.get_phase = Mock(return_value=None)
    service.commands.create = Mock()

    with pytest.raises(HTTPException) as exc:
        service.create_command(
            device_id=uuid4(),
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Signal phase not found"
    service.commands.create.assert_not_called()

def test_pending_commands_are_scoped_to_device():
    db = Mock()
    service = SignalControlService(db)

    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()
    command_id = uuid4()

    command = Mock(spec=SignalControlCommandModel)
    command.id = command_id
    command.intersection_id = intersection_id
    command.plan_id = plan_id
    command.phase_number = 2
    command.status = "accepted"
    command.expires_at = datetime.now(UTC) + timedelta(minutes=5)

    phase = Mock()
    phase.direction = "S"
    phase.green_seconds = 18
    phase.yellow_seconds = 4

    expected = [
        command,
    ]

    service.commands.pending_for_device = Mock(return_value=expected)
    service.signals.get_phase = Mock(return_value=phase)

    result = service.pending_commands(
        device_id=device_id,
        limit=5,
    )

    assert len(result) == 1
    assert result[0].command_id == command_id
    assert result[0].intersection_id == intersection_id
    assert result[0].plan_id == plan_id
    assert result[0].phase_number == 2
    assert result[0].direction == "S"
    assert result[0].green_seconds == 18
    assert result[0].yellow_seconds == 4
    assert result[0].status == "accepted"

    service.commands.pending_for_device.assert_called_once_with(
        device_id=device_id,
        limit=5,
    )
    service.signals.get_phase.assert_called_once_with(
        plan_id=plan_id,
        phase_number=2,
    )