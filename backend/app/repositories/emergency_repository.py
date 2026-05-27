from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import EmergencyCorridor, EmergencyEvent


class EmergencyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event: EmergencyEvent) -> EmergencyEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get(self, event_id: UUID) -> EmergencyEvent | None:
        return self.db.get(EmergencyEvent, event_id)

    def clear_active_for_intersection(self, intersection_id: UUID) -> int:
        events = self.active(intersection_id)
        now = datetime.now(UTC)
        for event in events:
            event.status = "cleared"
            event.cleared_at = now
        self.db.commit()
        return len(events)

    def active(self, intersection_id: UUID | None = None) -> list[EmergencyEvent]:
        statement = select(EmergencyEvent).where(EmergencyEvent.status == "active")
        if intersection_id:
            statement = statement.where(EmergencyEvent.intersection_id == intersection_id)
        return list(self.db.scalars(statement.order_by(desc(EmergencyEvent.severity))).all())

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[EmergencyEvent]:
        statement = select(EmergencyEvent)
        if intersection_id:
            statement = statement.where(EmergencyEvent.intersection_id == intersection_id)
        statement = statement.order_by(desc(EmergencyEvent.detected_at)).limit(limit)
        return list(self.db.scalars(statement).all())

    def get_corridors(self, emergency_id: UUID) -> list[EmergencyCorridor]:
        return (
            self.db.query(EmergencyCorridor)
            .filter(EmergencyCorridor.emergency_id == emergency_id)
            .order_by(EmergencyCorridor.sequence_order)
            .all()
        )

    def clear(self, event_id: UUID) -> EmergencyEvent | None:
        event = self.db.get(EmergencyEvent, event_id)
        if not event:
            return None
        event.status = "cleared"
        event.cleared_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(event)
        return event
