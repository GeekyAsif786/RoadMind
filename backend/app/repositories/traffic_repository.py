from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import TrafficObservation


class TrafficRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, observation: TrafficObservation) -> TrafficObservation:
        self.db.add(observation)
        self.db.commit()
        self.db.refresh(observation)
        return observation

    def latest(self, intersection_id: UUID | None = None, limit: int = 20) -> list[TrafficObservation]:
        statement = select(TrafficObservation)
        if intersection_id:
            statement = statement.where(TrafficObservation.intersection_id == intersection_id)
        statement = statement.order_by(desc(TrafficObservation.captured_at)).limit(limit)
        return list(self.db.scalars(statement).all())

    def history(self, since: datetime | None = None) -> list[TrafficObservation]:
        statement = select(TrafficObservation).order_by(TrafficObservation.captured_at)
        if since:
            statement = statement.where(TrafficObservation.captured_at >= since)
        return list(self.db.scalars(statement).all())
