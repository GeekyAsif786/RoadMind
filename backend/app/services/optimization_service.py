import datetime as dt
import logging
import zoneinfo
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmergencyCorridor, EmergencyEvent, SignalPhase, SignalPlan
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.traffic_repository import TrafficRepository
from app.services.density_service import DensityService

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

MONSOON_MONTHS = {6, 7, 8, 9}
WEATHER_MULTIPLIERS: dict[str, float] = {
    "clear": 1.0,
    "light_rain": 1.15,
    "heavy_rain": 1.35,
    "fog": 1.25,
    "smog": 1.10,
}
PEAK_HOURS = {
    "morning": (7, 10),
    "evening": (17, 20),
}
PEAK_GREEN_BONUS = 15
OFFPEAK_GREEN_REDUCTION = 10
NIGHT_HOURS = (23, 5)
SIGNAL_DIRECTION_ALIASES: dict[str, str] = {
    "n": "N",
    "north": "N",
    "northbound": "N",
    "s": "S",
    "south": "S",
    "southbound": "S",
    "e": "E",
    "east": "E",
    "eastbound": "E",
    "w": "W",
    "west": "W",
    "westbound": "W",
    "ne": "NE",
    "north-east": "NE",
    "north east": "NE",
    "northeast": "NE",
    "northeastbound": "NE",
    "nw": "NW",
    "north-west": "NW",
    "north west": "NW",
    "northwest": "NW",
    "northwestbound": "NW",
    "se": "SE",
    "south-east": "SE",
    "south east": "SE",
    "southeast": "SE",
    "southeastbound": "SE",
    "sw": "SW",
    "south-west": "SW",
    "south west": "SW",
    "southwest": "SW",
    "southwestbound": "SW",
    "all": "ALL",
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
        recent_obs = self.traffic.latest(intersection_id, limit=20)
        latest = recent_obs[:1]
        latest_density = latest[0].density if latest else 0.0
        latest_speed = latest[0].avg_speed if latest else None
        latest_weather = latest[0].weather_condition if latest else "clear"
        directional_volumes: dict[str, float] | None = None
        if recent_obs:
            dir_counts: dict[str, float] = {}
            for obs in recent_obs:
                if obs.direction != "ALL":
                    dir_counts[obs.direction] = dir_counts.get(obs.direction, 0) + obs.vehicle_count
            if dir_counts:
                total = sum(dir_counts.values())
                directional_volumes = {d: v / total for d, v in dir_counts.items()}

        if active_emergencies:
            strongest = active_emergencies[0]
            return self.optimize_for_emergency(strongest, horizon_minutes=horizon_minutes)
        else:
            density_class = self.density_service.classify(latest_density, avg_speed=latest_speed)
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
        self.signals.create_phases(
            self._create_default_phases(saved, ["N", "S", "E", "W"], green_seconds, directional_volumes)
        )
        if self.settings.enable_pedestrian_phase:
            ped_order = len(["N", "S", "E", "W"])
            self.signals.create_phases([self._create_pedestrian_phase(saved, ped_order)])
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
        if self.settings.enable_pedestrian_phase:
            ped_order = len(["N", "S", "E", "W"])
            self.signals.create_phases([self._create_pedestrian_phase(saved, ped_order)])

        if hasattr(emergency, "id"):
            self.flush_emergency_corridor(emergency)

        return saved

    def flush_emergency_corridor(self, emergency: EmergencyEvent) -> list[SignalPlan]:
        """
        Pre-green all intersections along the emergency corridor using time offsets.
        Each intersection gets a signal plan that activates green_offset_seconds after
        the first intersection's plan, creating a rolling green wave for the vehicle.
        """
        corridors = self.emergencies.get_corridors(emergency.id)
        if not corridors:
            logger.info("No corridor defined for emergency %s, single-intersection override only.", emergency.id)
            return []

        plans: list[SignalPlan] = []
        base_green = self._emergency_green_time(emergency.severity)

        for corridor in corridors:
            intersection = self.intersections.get(corridor.intersection_id)
            if not intersection:
                continue

            offset_seconds = corridor.green_offset_seconds
            expires_after_minutes = max(2, (base_green + self.settings.yellow_seconds) // 60 + 1)

            plan = SignalPlan(
                intersection_id=corridor.intersection_id,
                green_seconds=base_green,
                yellow_seconds=self.settings.yellow_seconds,
                red_seconds=self.settings.red_clearance_seconds,
                priority="emergency",
                reason=(
                    f"Corridor green-wave for emergency {emergency.id} "
                    f"(seq={corridor.sequence_order}, offset={offset_seconds}s). "
                    f"Vehicle: {emergency.vehicle_type} from {emergency.direction}."
                ),
                expires_at=datetime.now(UTC) + timedelta(
                    seconds=offset_seconds,
                    minutes=expires_after_minutes,
                ),
            )
            saved = self.signals.create(plan)
            signal_direction = self._normalize_signal_direction(emergency.direction)
            self.signals.create_phases(
                self._create_default_phases(saved, [signal_direction], base_green)
            )
            plans.append(saved)

            corridor.status = "active"
            self.emergencies.db.flush()

            logger.warning(
                "CORRIDOR GREEN-WAVE: intersection=%s, seq=%d, offset=%ds",
                corridor.intersection_id,
                corridor.sequence_order,
                offset_seconds,
            )

        return plans

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

        hour_ist = datetime.now(IST).hour
        is_morning_peak = PEAK_HOURS["morning"][0] <= hour_ist < PEAK_HOURS["morning"][1]
        is_evening_peak = PEAK_HOURS["evening"][0] <= hour_ist < PEAK_HOURS["evening"][1]
        is_night = hour_ist >= NIGHT_HOURS[0] or hour_ist < NIGHT_HOURS[1]

        if is_morning_peak or is_evening_peak:
            timed = min(timed + PEAK_GREEN_BONUS, self.settings.max_green_seconds)
        elif is_night:
            timed = max(timed - OFFPEAK_GREEN_REDUCTION, self.settings.min_green_seconds)

        return timed

    def _create_default_phases(
        self,
        plan: SignalPlan,
        directions: list[str],
        total_green: int,
        directional_volumes: dict[str, float] | None = None,
    ) -> list[SignalPhase]:
        """
        Split green time proportionally by directional volume if available.
        Falls back to equal split. Ensures no phase gets below min_green_seconds.
        directional_volumes: {"N": 0.4, "S": 0.3, "E": 0.2, "W": 0.1}  — must sum to ~1.0
        """
        n = len(directions)
        if directional_volumes and len(directional_volumes) == n:
            total_weight = sum(directional_volumes.get(d, 1.0 / n) for d in directions)
            raw_greens = {
                d: (directional_volumes.get(d, 1.0 / n) / total_weight) * total_green
                for d in directions
            }
            # Floor each phase at min_green_seconds, redistribute remainder
            floored = {d: max(self.settings.min_green_seconds, int(g)) for d, g in raw_greens.items()}
            # Trim overshoots
            overshoot = sum(floored.values()) - total_green
            if overshoot > 0:
                # Shave from highest-green phases
                for d in sorted(floored, key=lambda x: -floored[x]):
                    cut = min(overshoot, floored[d] - self.settings.min_green_seconds)
                    floored[d] -= cut
                    overshoot -= cut
                    if overshoot <= 0:
                        break
            green_per_direction = floored
        else:
            equal = max(self.settings.min_green_seconds, total_green // n)
            green_per_direction = {d: equal for d in directions}

        return [
            SignalPhase(
                plan_id=plan.id,
                phase_number=i + 1,
                direction=d,
                green_seconds=green_per_direction[d],
                yellow_seconds=self.settings.yellow_seconds,
                phase_order=i,
            )
            for i, d in enumerate(directions)
        ]

    def _create_pedestrian_phase(self, plan: SignalPlan, phase_order: int) -> SignalPhase:
        """
        Adds a mandatory all-red + pedestrian clearance phase at end of signal cycle.
        7 seconds is IRC minimum for urban intersections.
        """
        return SignalPhase(
            plan_id=plan.id,
            phase_number=phase_order + 1,
            direction="PED",
            green_seconds=self.settings.pedestrian_clearance_seconds,
            yellow_seconds=0,
            phase_order=phase_order,
        )

    def _normalize_signal_direction(self, direction: str) -> str:
        normalized = direction.strip().lower().replace("_", "-")
        signal_direction = SIGNAL_DIRECTION_ALIASES.get(normalized, "ALL")
        if signal_direction == "ALL" and normalized != "all":
            logger.warning("Unknown emergency direction %r; using ALL signal phase.", direction)
        return signal_direction

    def _emergency_green_time(self, severity: int) -> int:
        severity_ratio = (max(1, min(severity, 10)) - 1) / 9
        span = self.settings.max_green_seconds - self.settings.min_green_seconds
        return int(round(self.settings.min_green_seconds + (severity_ratio * span)))
