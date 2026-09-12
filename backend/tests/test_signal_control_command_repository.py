from unittest.mock import Mock
from uuid import uuid4
from datetime import UTC, datetime,timedelta
from app.models import SignalControlCommand
from app.repositories.signal_control_command_repository import (
    SignalControlCommandRepository,
)


def test_create_saves_command():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    command = Mock(spec=SignalControlCommand)

    result = repository.create(command)

    assert result is command
    db.add.assert_called_once_with(command)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(command)


def test_get_returns_command():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    command_id = uuid4()
    expected = Mock(spec=SignalControlCommand)

    db.get.return_value = expected

    result = repository.get(command_id)

    assert result is expected
    db.get.assert_called_once_with(
        SignalControlCommand,
        command_id,
    )

def test_acknowledge_updates_command():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    command = Mock(spec=SignalControlCommand)
    command.acknowledged_at = None
    command.status = "accepted"

    acknowledged_at = datetime.now(UTC)

    result = repository.acknowledge(
        command=command,
        acknowledged_at=acknowledged_at,
    )

    assert result is command
    assert command.acknowledged_at == acknowledged_at
    assert command.status == "acknowledged"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(command)

def test_get_returns_none_when_missing():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    command_id = uuid4()

    db.get.return_value = None

    result = repository.get(command_id)

    assert result is None
    db.get.assert_called_once_with(
        SignalControlCommand,
        command_id,
    )


def test_latest_returns_commands():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    expected = [Mock(spec=SignalControlCommand), Mock(spec=SignalControlCommand)]

    db.scalars.return_value.all.return_value = expected

    result = repository.latest(
        intersection_id=None,
        limit=10,
    )

    assert result == expected
    db.scalars.assert_called_once()


def test_latest_can_filter_by_intersection():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    intersection_id = uuid4()
    expected = [Mock(spec=SignalControlCommand)]

    db.scalars.return_value.all.return_value = expected

    result = repository.latest(
        intersection_id=intersection_id,
        limit=5,
    )

    assert result == expected
    db.scalars.assert_called_once()

def test_pending_for_device_returns_accepted_unacknowledged_commands():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    device_id = uuid4()
    expected = [Mock(spec=SignalControlCommand)]

    db.scalars.return_value.all.return_value = expected

    result = repository.pending_for_device(
        device_id=device_id,
        limit=10,
    )

    assert result == expected
    db.scalars.assert_called_once()


def test_pending_for_device_can_limit_results():
    db = Mock()
    repository = SignalControlCommandRepository(db)

    device_id = uuid4()
    expected = [Mock(spec=SignalControlCommand)]

    db.scalars.return_value.all.return_value = expected

    result = repository.pending_for_device(
        device_id=device_id,
        limit=3,
    )

    assert result == expected
    db.scalars.assert_called_once()