from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas import SignalControllerStateCreate
from app.services.signal_controller_state_service import (
    SignalControllerStateService,
)


def make_service():
    db = Mock()
    service = SignalControllerStateService(db)

    service.commands = Mock()
    service.controller_states = Mock()
    service.signals = Mock()

    return service


def make_command(
    *,
    command_id,
    device_id,
    intersection_id,
    plan_id,
    phase_number=1,
    status="acknowledged",
    expires_at=None,
    execution_reported_at=None,
):
    command = Mock()
    command.id = command_id
    command.device_id = device_id
    command.intersection_id = intersection_id
    command.plan_id = plan_id
    command.phase_number = phase_number
    command.status = status
    command.expires_at = expires_at
    command.execution_reported_at = execution_reported_at
    return command


def make_payload(
    *,
    plan_id,
    phase_number=1,
):
    return SignalControllerStateCreate(
        current_phase=phase_number,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
        phase_started_at=datetime.now(UTC),
    )


def test_first_execution_report_marks_command_as_reported():
    service = make_service()

    command_id = uuid4()
    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
    )

    state = Mock()

    service.commands.get_for_update.return_value = command
    service.update = Mock(return_value=state)

    payload = make_payload(
        plan_id=plan_id,
        phase_number=1,
    )

    result = service.report_command_execution(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result is state
    assert command.execution_reported_at is not None

    service.commands.get_for_update.assert_called_once_with(command_id)

    service.update.assert_called_once_with(
        intersection_id=intersection_id,
        payload=payload,
        commit=False,
    )

    service.db.commit.assert_called_once()
    service.db.refresh.assert_called_once_with(state)


def test_duplicate_execution_report_returns_existing_state_without_update():
    service = make_service()

    command_id = uuid4()
    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        execution_reported_at=datetime.now(UTC) - timedelta(seconds=10),
    )

    existing_state = Mock()

    service.commands.get_for_update.return_value = command
    service.controller_states.get.return_value = existing_state
    service.update = Mock()

    payload = make_payload(
        plan_id=plan_id,
        phase_number=1,
    )

    result = service.report_command_execution(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result is existing_state

    service.commands.get_for_update.assert_called_once_with(command_id)

    service.controller_states.get.assert_called_once_with(
        intersection_id
    )

    service.update.assert_not_called()
    service.db.commit.assert_not_called()


def test_duplicate_execution_report_with_wrong_phase_is_rejected():
    service = make_service()

    command_id = uuid4()
    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        phase_number=1,
        execution_reported_at=datetime.now(UTC),
    )

    service.commands.get_for_update.return_value = command

    payload = make_payload(
        plan_id=plan_id,
        phase_number=2,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.report_command_execution(
            command_id=command_id,
            device_id=device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Reported phase does not match the control command"
    )

    service.commands.get_for_update.assert_called_once_with(command_id)
    service.db.commit.assert_not_called()


def test_reported_command_without_controller_state_returns_conflict():
    service = make_service()

    command_id = uuid4()
    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        execution_reported_at=datetime.now(UTC),
    )

    service.commands.get_for_update.return_value = command
    service.controller_states.get.return_value = None

    payload = make_payload(
        plan_id=plan_id,
        phase_number=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.report_command_execution(
            command_id=command_id,
            device_id=device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Execution was already reported but controller state is unavailable"
    )

    service.commands.get_for_update.assert_called_once_with(command_id)
    service.db.commit.assert_not_called()


def test_execution_report_rolls_back_when_controller_state_update_fails():
    service = make_service()

    command_id = uuid4()
    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        command_id=command_id,
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
    )

    service.commands.get_for_update.return_value = command

    expected_error = RuntimeError("controller state update failed")

    service.update = Mock(side_effect=expected_error)

    payload = make_payload(
        plan_id=plan_id,
        phase_number=1,
    )

    with pytest.raises(RuntimeError, match="controller state update failed"):
        service.report_command_execution(
            command_id=command_id,
            device_id=device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert command.execution_reported_at is not None

    service.update.assert_called_once_with(
        intersection_id=intersection_id,
        payload=payload,
        commit=False,
    )

    service.db.rollback.assert_called_once()
    service.db.commit.assert_not_called()