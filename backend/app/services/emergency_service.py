from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmergencyCorridor, EmergencyEvent
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.schemas import EmergencyCreate
from app.services.optimization_service import SignalOptimizationService

AVG_INTERSECTION_SPACING_M = 400


class EmergencySignalContext(BaseModel):
    id: UUID
    intersection_id: UUID
    vehicle_type: str
    direction: str
    severity: int


class EmergencyService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
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

    def create_corridor(
        self,
        emergency_id: UUID,
        intersection_ids: list[UUID],
        avg_speed_kmh: float = 30.0,
    ) -> list[EmergencyCorridor]:
        if not self.emergencies.get(emergency_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency event not found")
        if not intersection_ids:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one intersection is required")
        for intersection_id in intersection_ids:
            if not self.intersections.get(intersection_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Intersection not found: {intersection_id}")

        avg_speed_ms = max((avg_speed_kmh * 1000) / 3600, 0.1)
        time_per_intersection = AVG_INTERSECTION_SPACING_M / avg_speed_ms
        corridors: list[EmergencyCorridor] = []

        for i, intersection_id in enumerate(intersection_ids):
            offset_seconds = int(i * time_per_intersection)
            corridor = EmergencyCorridor(
                emergency_id=emergency_id,
                intersection_id=intersection_id,
                sequence_order=i,
                green_offset_seconds=offset_seconds,
                status="pending",
            )
            self.db.add(corridor)

            active = self.emergencies.active(intersection_id)
            emergency = active[0] if active else self._synthetic_emergency(emergency_id, intersection_id)
            self.optimizer.optimize_for_emergency(emergency, horizon_minutes=max(5 + i, int((offset_seconds + 120) / 60)))
            corridors.append(corridor)

        self.db.commit()
        for corridor in corridors:
            self.db.refresh(corridor)
        return corridors

    def _synthetic_emergency(self, emergency_id: UUID, intersection_id: UUID):
        return EmergencySignalContext(
            id=emergency_id,
            intersection_id=intersection_id,
            vehicle_type="ambulance",
            direction="ALL",
            severity=8,
        )
