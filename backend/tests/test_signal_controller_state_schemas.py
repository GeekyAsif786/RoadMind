import pytest
from pydantic import ValidationError

from app.schemas import SignalControllerStateCreate


def test_signal_controller_state_accepts_valid_payload():
    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
    )

    assert payload.current_phase == 2
    assert payload.phase_state == "green"
    assert payload.controller_status == "online"


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_phase", 0),
        ("current_phase", 17),
        ("phase_state", "flashing"),
        ("controller_status", "offline"),
    ],
)
def test_signal_controller_state_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        SignalControllerStateCreate(**{field: value})