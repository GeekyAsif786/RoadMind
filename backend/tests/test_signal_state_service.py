from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.services.signal_state_service import SignalStateService


def test_get_signal_state_returns_state():
    db = Mock()
    service = SignalStateService(db)

    intersection_id = uuid4()
    expected = Mock()

    service.signal_states.get = Mock(return_value=expected)

    result = service.get(intersection_id)

    assert result is expected
    service.signal_states.get.assert_called_once_with(intersection_id)

def test_get_signal_state_raises_404_when_missing():
    db = Mock()
    service = SignalStateService(db)

    intersection_id = uuid4()
    service.signal_states.get = Mock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        service.get(intersection_id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Signal state not found"