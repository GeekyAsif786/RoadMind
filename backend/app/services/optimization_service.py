from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmergencyEvent, SignalPlan
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.traffic_repository import TrafficRepository
from app.services.density_service import DensityService


class SignalOptimizationService:
    def __init__(self, db: Session):
        self.settings = get_settings()
        self.intersections = IntersectionRepository(db)
        self.traffic = TrafficRepository(db)
        self.signals = SignalRepository(db)
        self.emergencies = EmergencyRepository(db)
        self.density_service = DensityService()

    def optimize(self, intersection_id: UUID, horizon_minutes: int = 15) -> SignalPlan:
        intersection = self.intersections.get(intersection_id)
        if not intersection:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")

        active_emergencies = self.emergencies.active(intersection_id)
        latest = self.traffic.latest(intersection_id, limit=1)
        latest_density = latest[0].density if latest else 0.0

        if active_emergencies:
            strongest = active_emergencies[0]
            return self.optimize_for_emergency(strongest, horizon_minutes=horizon_minutes)
        else:
            density_class = self.density_service.classify(latest_density)
            green_seconds = self._green_time(latest_density)
            priority = density_class
            reason = f"Adaptive timing based on latest density {latest_density:.2f} ({density_class})."

        plan = SignalPlan(
            intersection_id=intersection_id,
            green_seconds=green_seconds,
            yellow_seconds=self.settings.yellow_seconds,
            red_seconds=self.settings.red_clearance_seconds,
            priority=priority,
            reason=reason,
            expires_at=datetime.now(UTC) + timedelta(minutes=horizon_minutes),
        )
        return self.signals.create(plan)

    def optimize_for_emergency(self, emergency: EmergencyEvent, horizon_minutes: int = 5) -> SignalPlan:
        green_seconds = self._emergency_green_time(emergency.severity)
        plan = SignalPlan(
            intersection_id=emergency.intersection_id,
            green_seconds=green_seconds,
            yellow_seconds=self.settings.yellow_seconds,
            red_seconds=self.settings.red_clearance_seconds,
            priority="emergency",
            reason=(
                f"Emergency priority for {emergency.vehicle_type} approaching "
                f"from {emergency.direction}; severity {emergency.severity}/10."
            ),
            expires_at=datetime.now(UTC) + timedelta(minutes=horizon_minutes),
        )
        return self.signals.create(plan)

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[SignalPlan]:
        return self.signals.latest(intersection_id=intersection_id, limit=limit)

    def _green_time(self, density: float) -> int:
        span = self.settings.max_green_seconds - self.settings.min_green_seconds
        return int(self.settings.min_green_seconds + (max(0.0, min(density, 1.0)) * span))

    def _emergency_green_time(self, severity: int) -> int:
        severity_ratio = (max(1, min(severity, 10)) - 1) / 9
        span = self.settings.max_green_seconds - self.settings.min_green_seconds
        return int(round(self.settings.min_green_seconds + (severity_ratio * span)))
