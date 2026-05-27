from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import EmergencyEvent
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.schemas import EmergencyCreate
from app.services.optimization_service import SignalOptimizationService


class EmergencyService:
    def __init__(self, db: Session):
        self.intersections = IntersectionRepository(db)
        self.emergencies = EmergencyRepository(db)
        self.optimizer = SignalOptimizationService(db)

    def create(self, payload: EmergencyCreate) -> EmergencyEvent:
        if not self.intersections.get(payload.intersection_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")
        self.emergencies.clear_active_for_intersection(payload.intersection_id)
        event = self.emergencies.create(EmergencyEvent(**payload.model_dump()))
        self.optimizer.optimize_for_emergency(event, horizon_minutes=5)
        return event

    def active(self, intersection_id: UUID | None = None) -> list[EmergencyEvent]:
        return self.emergencies.active(intersection_id)

    def clear_active_for_intersection(self, intersection_id: UUID):
        if not self.intersections.get(intersection_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")
        self.emergencies.clear_active_for_intersection(intersection_id)
        return self.optimizer.optimize(intersection_id, horizon_minutes=15)

    def clear(self, event_id: UUID) -> EmergencyEvent:
        event = self.emergencies.clear(event_id)
        if not event:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency event not found")
        return event
