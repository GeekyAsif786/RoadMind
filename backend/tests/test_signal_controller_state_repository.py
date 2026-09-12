from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from app.models import SignalControllerState, SignalPlan
from app.repositories.signal_controller_state_repository import (
    SignalControllerStateRepository,
)
from app.repositories.signal_repository import SignalRepository


def test_get_returns_state():
    db = Mock()
    repository = SignalControllerStateRepository(db)

    intersection_id = uuid4()
    expected = Mock(spec=SignalControllerState)

    db.get.return_value = expected

    result = repository.get(intersection_id)

    assert result is expected
    db.get.assert_called_once_with(
        SignalControllerState,
        intersection_id,
    )


def test_upsert_creates_new_state():
    db = Mock()
    repository = SignalControllerStateRepository(db)

    intersection_id = uuid4()
    phase_started_at = datetime.now(UTC)

    db.get.return_value = None

    result = repository.upsert(
        intersection_id=intersection_id,
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=None,
        phase_started_at=phase_started_at,
    )

    assert isinstance(result, SignalControllerState)
    assert result.intersection_id == intersection_id
    assert result.current_phase == 2
    assert result.phase_state == "green"
    assert result.controller_status == "online"
    assert result.reported_plan_id is None
    assert result.phase_started_at == phase_started_at
    assert result.updated_at is not None

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_upsert_updates_existing_state():
    db = Mock()
    repository = SignalControllerStateRepository(db)

    intersection_id = uuid4()
    existing = Mock(spec=SignalControllerState)

    db.get.return_value = existing

    repository.upsert(
        intersection_id=intersection_id,
        current_phase=3,
        phase_state="yellow",
        controller_status="degraded",
    )

    assert existing.current_phase == 3
    assert existing.phase_state == "yellow"
    assert existing.controller_status == "degraded"
    assert existing.reported_plan_id is None
    assert existing.phase_started_at is None
    assert existing.updated_at is not None

    db.add.assert_not_called()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(existing)
