from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SignalControllerState


class SignalControllerStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, intersection_id: UUID) -> SignalControllerState | None:
        return self.db.get(SignalControllerState, intersection_id)

    def upsert(
        self,
        intersection_id: UUID,
        current_phase: int,
        phase_state: str,
        controller_status: str,
        reported_plan_id: UUID | None = None,
        phase_started_at: datetime | None = None,
    ) -> SignalControllerState:
        state = self.get(intersection_id)

        if state is None:
            state = SignalControllerState(
                intersection_id=intersection_id,
            )
            self.db.add(state)

        state.current_phase = current_phase
        state.phase_state = phase_state
        state.controller_status = controller_status
        state.reported_plan_id = reported_plan_id
        state.phase_started_at = phase_started_at
        state.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(state)
        return state