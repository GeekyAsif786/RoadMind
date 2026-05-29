from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.models import TrafficObservation
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.traffic_repository import TrafficRepository
from app.schemas import TrafficObservationCreate
from app.services.density_service import DensityService


class TrafficService:
    def __init__(self, db: Session):
        self.intersections = IntersectionRepository(db)
        self.traffic = TrafficRepository(db)
        self.density = DensityService()

    def create_observation(self, payload: TrafficObservationCreate) -> TrafficObservation:
        intersection = self.intersections.get(payload.intersection_id)
        if not intersection:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")

        density = payload.density
        if density is None:
            density = self.density.calculate(
                payload.vehicle_count,
                intersection.lanes,
                road_type=intersection.road_type,
            )

        observation = TrafficObservation(
            intersection_id=payload.intersection_id,
            direction=payload.direction,
            vehicle_count=payload.vehicle_count,
            density=density,
            avg_speed=payload.avg_speed,
            occupancy=payload.occupancy,
            weather_condition=payload.weather_condition,
            pcu_total=payload.pcu_total,
            source=payload.source,
            captured_at=payload.captured_at or datetime.now(UTC),
        )
        saved = self.traffic.create(observation)
        cache = get_cache()
        cache.delete_prefix("dashboard:summary:")
        cache.delete_prefix("traffic:latest:")
        return saved

    def latest(self, intersection_id: UUID | None = None, limit: int = 20) -> list[TrafficObservation]:
        return self.traffic.latest(intersection_id=intersection_id, limit=limit)
