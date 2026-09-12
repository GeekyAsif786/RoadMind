from unittest.mock import Mock
from uuid import uuid4

from app.models import SignalPlan,SignalPhase
from app.repositories.signal_repository import SignalRepository


def test_get_returns_signal_plan():
    db = Mock()
    repository = SignalRepository(db)

    plan_id = uuid4()
    expected = Mock(spec=SignalPlan)

    db.get.return_value = expected

    result = repository.get(plan_id)

    assert result is expected
    db.get.assert_called_once_with(
        SignalPlan,
        plan_id,
    )

def test_get_phase_returns_matching_phase():
    db = Mock()
    repository = SignalRepository(db)

    plan_id = uuid4()
    phase_number = 2
    expected = Mock(spec=SignalPhase)

    db.scalar.return_value = expected

    result = repository.get_phase(
        plan_id=plan_id,
        phase_number=phase_number,
    )

    assert result is expected
    db.scalar.assert_called_once()

def test_get_phase_returns_none_when_missing():
    db = Mock()
    repository = SignalRepository(db)

    plan_id = uuid4()

    db.scalar.return_value = None

    result = repository.get_phase(
        plan_id=plan_id,
        phase_number=99,
    )

    assert result is None
    db.scalar.assert_called_once()