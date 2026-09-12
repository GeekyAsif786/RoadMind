from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import SignalControllerState, SignalPlan
from app.schemas import SignalControllerStateCreate
from app.services.signal_controller_state_service import (
    SignalControllerStateService,
)


def test_update_without_reported_plan_delegates_to_repository():
    db = Mock()
    service = SignalControllerStateService(db)

    intersection_id = uuid4()

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
    )

    expected = Mock(spec=SignalControllerState)
    service.controller_states.upsert = Mock(return_value=expected)
    service.signals.get = Mock()
    result = service.update(
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result is expected
    service.signals.get.assert_not_called()
    service.controller_states.upsert.assert_called_once_with(
        intersection_id=intersection_id,
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=None,
        phase_started_at=None,
    )


def test_update_rejects_missing_reported_plan():
    db = Mock()
    service = SignalControllerStateService(db)

    intersection_id = uuid4()
    plan_id = uuid4()

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    service.signals.get = Mock(return_value=None)
    service.controller_states.upsert = Mock()
    with pytest.raises(HTTPException) as exc:
        service.update(
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Signal plan not found"
    service.controller_states.upsert.assert_not_called()


def test_update_rejects_plan_from_other_intersection():
    db = Mock()
    service = SignalControllerStateService(db)

    intersection_id = uuid4()

    plan = Mock(spec=SignalPlan)
    plan.id = uuid4()
    plan.intersection_id = uuid4()
    plan.expires_at = datetime.now(UTC) + timedelta(minutes=5)

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan.id,
    )

    service.signals.get = Mock(return_value=plan)
    service.controller_states.upsert = Mock()
    with pytest.raises(HTTPException) as exc:
        service.update(
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Signal plan does not belong to this intersection"
    service.controller_states.upsert.assert_not_called()


def test_update_rejects_expired_plan():
    db = Mock()
    service = SignalControllerStateService(db)

    intersection_id = uuid4()

    plan = Mock(spec=SignalPlan)
    plan.id = uuid4()
    plan.intersection_id = intersection_id
    plan.expires_at = datetime.now(UTC) - timedelta(minutes=1)

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan.id,
    )

    service.signals.get = Mock(return_value=plan)
    service.controller_states.upsert = Mock()
    with pytest.raises(HTTPException) as exc:
        service.update(
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Signal plan has expired"
    service.controller_states.upsert.assert_not_called()


def test_update_accepts_valid_reported_plan():
    db = Mock()
    service = SignalControllerStateService(db)

    intersection_id = uuid4()

    plan = Mock(spec=SignalPlan)
    plan.id = uuid4()
    plan.intersection_id = intersection_id
    plan.expires_at = datetime.now(UTC) + timedelta(minutes=5)

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan.id,
    )

    expected = Mock(spec=SignalControllerState)

    service.signals.get = Mock(return_value=plan)
    service.controller_states.upsert = Mock(return_value=expected)

    result = service.update(
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result is expected
    service.signals.get.assert_called_once_with(plan.id)
    service.controller_states.upsert.assert_called_once_with(
        intersection_id=intersection_id,
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan.id,
        phase_started_at=None,
    )

def make_command(
    *,
    device_id,
    intersection_id,
    plan_id,
    phase_number=2,
    status="acknowledged",
    expires_at=None,
):
    command = Mock()
    command.id = uuid4()
    command.device_id = device_id
    command.intersection_id = intersection_id
    command.plan_id = plan_id
    command.phase_number = phase_number
    command.status = status
    command.expires_at = expires_at
    return command


def test_report_command_execution_accepts_matching_acknowledged_command():
    db = Mock()
    service = SignalControllerStateService(db)

    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        phase_number=2,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    expected = Mock(spec=SignalControllerState)

    service.commands.get = Mock(return_value=command)
    service.update = Mock(return_value=expected)

    result = service.report_command_execution(
        command_id=command.id,
        device_id=device_id,
        intersection_id=intersection_id,
        payload=payload,
    )

    assert result is expected
    service.commands.get.assert_called_once_with(command.id)
    service.update.assert_called_once_with(
        intersection_id=intersection_id,
        payload=payload,
    )


def test_report_command_execution_rejects_wrong_device():
    db = Mock()
    service = SignalControllerStateService(db)

    owner_device_id = uuid4()
    other_device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        device_id=owner_device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
    )

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    service.commands.get = Mock(return_value=command)
    service.controller_states.upsert = Mock()

    with pytest.raises(HTTPException) as exc:
        service.report_command_execution(
            command_id=command.id,
            device_id=other_device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not authorized to report this command"
    service.controller_states.upsert.assert_not_called()


def test_report_command_execution_rejects_unacknowledged_command():
    db = Mock()
    service = SignalControllerStateService(db)

    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        status="accepted",
    )

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    service.commands.get = Mock(return_value=command)
    service.controller_states.upsert = Mock()

    with pytest.raises(HTTPException) as exc:
        service.report_command_execution(
            command_id=command.id,
            device_id=device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == (
        "Signal control command must be acknowledged before execution is reported"
    )
    service.controller_states.upsert.assert_not_called()


def test_report_command_execution_rejects_mismatched_phase():
    db = Mock()
    service = SignalControllerStateService(db)

    device_id = uuid4()
    intersection_id = uuid4()
    plan_id = uuid4()

    command = make_command(
        device_id=device_id,
        intersection_id=intersection_id,
        plan_id=plan_id,
        phase_number=2,
    )

    payload = SignalControllerStateCreate(
        current_phase=3,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
    )

    service.commands.get = Mock(return_value=command)
    service.controller_states.upsert = Mock()

    with pytest.raises(HTTPException) as exc:
        service.report_command_execution(
            command_id=command.id,
            device_id=device_id,
            intersection_id=intersection_id,
            payload=payload,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Reported phase does not match the control command"
    service.controller_states.upsert.assert_not_called()