import datetime as dt
import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmergencyEvent, SignalPhase, SignalPlan
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.traffic_repository import TrafficRepository
from app.services.density_service import DensityService

logger = logging.getLogger(__name__)

MONSOON_MONTHS = {6, 7, 8, 9}
WEATHER_MULTIPLIERS: dict[str, float] = {
    "clear": 1.0,
    "light_rain": 1.15,
    "heavy_rain": 1.35,
    "fog": 1.25,
    "smog": 1.10,
}


class EmergencyLike(Protocol):
    intersection_id: UUID
    vehicle_type: str
    direction: str
    severity: int


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
        latest_weather = latest[0].weather_condition if latest else "clear"

        if active_emergencies:
            strongest = active_emergencies[0]
            return self.optimize_for_emergency(strongest, horizon_minutes=horizon_minutes)
        else:
            density_class = self.density_service.classify(latest_density)
            green_seconds = self._green_time(latest_density, latest_weather)
            priority = density_class
            reason = (
                f"Adaptive timing based on latest density {latest_density:.2f} "
                f"({density_class}) and weather {latest_weather}."
            )

        plan = SignalPlan(
            intersection_id=intersection_id,
            green_seconds=green_seconds,
            yellow_seconds=self.settings.yellow_seconds,
            red_seconds=self.settings.red_clearance_seconds,
            priority=priority,
            reason=reason,
            expires_at=datetime.now(UTC) + timedelta(minutes=horizon_minutes),
        )
        saved = self.signals.create(plan)
        self.signals.create_phases(self._create_default_phases(saved, ["N", "S", "E", "W"], green_seconds))
        logger.info(
            "Signal optimized: intersection=%s, density=%.2f, green=%ds, priority=%s",
            intersection_id,
            latest_density,
            green_seconds,
            priority,
        )
        return saved

    def optimize_for_emergency(self, emergency: EmergencyLike, horizon_minutes: int = 5) -> SignalPlan:
        green_seconds = self._emergency_green_time(emergency.severity)
        logger.warning(
            "EMERGENCY OVERRIDE: intersection=%s, type=%s, severity=%d",
            emergency.intersection_id,
            emergency.vehicle_type,
            emergency.severity,
        )
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
        saved = self.signals.create(plan)
        self.signals.create_phases(self._create_default_phases(saved, ["N", "S", "E", "W"], green_seconds))
        return saved

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[SignalPlan]:
        return self.signals.latest(intersection_id=intersection_id, limit=limit)

    def _green_time(self, density: float, weather_condition: str = "clear") -> int:
        multiplier = WEATHER_MULTIPLIERS.get(weather_condition, 1.0)
        span = self.settings.max_green_seconds - self.settings.min_green_seconds
        base = int(self.settings.min_green_seconds + (max(0.0, min(density, 1.0)) * span))
        timed = min(int(base * multiplier), self.settings.max_green_seconds)

        if dt.datetime.now(dt.UTC).month in MONSOON_MONTHS:
            timed = max(timed, 25)
        if weather_condition == "heavy_rain":
            timed = max(timed, 25)

        return timed

    def _create_default_phases(
        self,
        plan: SignalPlan,
        directions: list[str],
        total_green: int,
    ) -> list[SignalPhase]:
        """Distribute green time equally across directions."""
        green_per_phase = max(self.settings.min_green_seconds, total_green // len(directions))
        return [
            SignalPhase(
                plan_id=plan.id,
                phase_number=i + 1,
                direction=d,
                green_seconds=green_per_phase,
                yellow_seconds=self.settings.yellow_seconds,
                phase_order=i,
            )
            for i, d in enumerate(directions)
        ]

    def _emergency_green_time(self, severity: int) -> int:
        severity_ratio = (max(1, min(severity, 10)) - 1) / 9
        span = self.settings.max_green_seconds - self.settings.min_green_seconds
        return int(round(self.settings.min_green_seconds + (severity_ratio * span)))
