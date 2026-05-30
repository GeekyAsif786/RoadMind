from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import IntersectionSignalState


class SignalStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, intersection_id: UUID) -> IntersectionSignalState | None:
        return self.db.get(IntersectionSignalState, intersection_id)

    def upsert(
        self,
        intersection_id: UUID,
        last_density: float,
        last_vehicle_count: int,
        decision_source: str,
        last_signal_plan_id: UUID | None = None,
        last_detection_timestamp: datetime | None = None,
    ) -> IntersectionSignalState:
        state = self.get(intersection_id)
        if state is None:
            state = IntersectionSignalState(intersection_id=intersection_id)
            self.db.add(state)
        state.last_density = last_density
        state.last_vehicle_count = last_vehicle_count
        state.last_signal_plan_id = last_signal_plan_id
        state.last_detection_timestamp = last_detection_timestamp
        state.decision_source = decision_source
        state.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(state)
        return state
