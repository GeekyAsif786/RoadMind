"""
Generate a realistic, internally-consistent synthetic dataset for training
RoadMind's traffic predictor.

Design goals (see chat writeup for the full reasoning):
  1. Density has a REAL, known relationship to hour/day-of-week/weather/
     road_type, so the model has genuine signal to find. Noise is added
     on top with a known standard deviation, so you can sanity-check the
     trained model's R^2 against a theoretical ceiling implied by that
     noise level.
  2. density/vehicle_count/pcu_total are computed via the app's own
     DensityService, so seed data can never drift from production math.
  3. avg_speed and pcu_total are made missing at a realistic, nonzero
     rate, so the missing-indicator features actually get exercised.
  4. Observations are frequent and span enough real days per intersection
     that the (current, future, horizon) pairing logic and walk-forward
     validation both have enough usable data after embargo purging.

Usage (from backend/, with your venv active and DATABASE_URL configured):

    python scripts/generate_training_data.py \
        --intersections 3 --days 45 --interval-minutes 8

    # Dry run to see row counts + one sample row without touching the DB:
    python scripts/generate_training_data.py --dry-run

    # Target existing intersections instead of creating new ones:
    python scripts/generate_training_data.py --reuse-existing

Generated intersections (when not using --reuse-existing) are named with
a "SIM-" prefix so they're easy to find and delete later:

    DELETE FROM traffic_observations WHERE intersection_id IN
        (SELECT id FROM intersections WHERE name LIKE 'SIM-%');
    DELETE FROM intersections WHERE name LIKE 'SIM-%';
"""

import argparse
import math
import random
import sys
import uuid
import zoneinfo
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.models import Intersection, TrafficObservation  # noqa: E402
from app.services.density_service import DensityService  # noqa: E402

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
RNG_SEED = 42  # fixed seed -> reproducible dataset, easier to debug against

# Weather multipliers mirrored from optimization_service.WEATHER_MULTIPLIERS.
# Kept as a literal copy (not imported) deliberately: this script represents
# the "ground truth" data-generating process, which is allowed to be an
# approximation of the app's logic, not a re-export of it. Only density/PCU
# math is required to be exactly the app's own code (see DensityService use
# below) because that's the part that must never drift.
WEATHER_MULTIPLIERS = {
    "clear": 1.0,
    "light_rain": 1.15,
    "heavy_rain": 1.35,
    "fog": 1.25,
    "smog": 1.10,
}
MONSOON_MONTHS = {6, 7, 8, 9}
WINTER_FOG_MONTHS = {11, 12, 1}

VEHICLE_MIX_KEYS = [
    "two_wheeler", "auto_rickshaw", "car", "taxi", "mini_bus", "bus", "truck", "cycle", "e_rickshaw",
]

SAMPLE_INTERSECTIONS = [
    # (name, lanes, road_type)
    ("SIM-MG Road x Brigade Road", 3, "urban"),
    ("SIM-NH-48 Toll Plaza", 6, "highway"),
    ("SIM-Sector 12 Service Lane", 2, "service"),
    ("SIM-Outer Ring Road Junction", 4, "urban"),
    ("SIM-Airport Expressway Ramp", 5, "highway"),
]


def diurnal_density_curve(hour: float, is_weekend: bool) -> float:
    """
    Returns a base congestion ratio in [0, 1] for a given hour of day (float,
    so 8.5 = 8:30am), before weather/noise adjustments. Modeled as two peaks
    (morning + evening commute) on a low overnight/midday floor, flattened
    on weekends.
    """
    def gaussian_bump(center: float, width: float, height: float) -> float:
        return height * math.exp(-((hour - center) ** 2) / (2 * width ** 2))

    floor = 0.08
    morning = gaussian_bump(8.5, 1.4, 0.65)
    evening = gaussian_bump(18.5, 1.6, 0.70)
    midday = gaussian_bump(13.0, 3.0, 0.20)
    base = floor + morning + evening + midday

    if is_weekend:
        base = floor + (base - floor) * 0.55  # weekend traffic is real but flatter

    return min(base, 0.97)


def pick_weather(month: int, hour: int, rng: random.Random) -> str:
    if month in MONSOON_MONTHS:
        return rng.choices(
            ["clear", "light_rain", "heavy_rain"], weights=[0.45, 0.35, 0.20],
        )[0]
    if month in WINTER_FOG_MONTHS and hour < 8:
        return rng.choices(["clear", "fog", "smog"], weights=[0.5, 0.3, 0.2])[0]
    return rng.choices(["clear", "light_rain", "smog"], weights=[0.85, 0.05, 0.10])[0]


def pick_direction(hour: float, rng: random.Random) -> str:
    """Morning skews inbound (N/E), evening skews outbound (S/W); some noise + ALL."""
    if rng.random() < 0.10:
        return "ALL"
    if 7 <= hour < 11:
        weights = {"N": 0.32, "E": 0.28, "S": 0.15, "W": 0.15, "NE": 0.05, "SW": 0.05}
    elif 17 <= hour < 21:
        weights = {"S": 0.32, "W": 0.28, "N": 0.15, "E": 0.15, "SW": 0.05, "NE": 0.05}
    else:
        weights = {"N": 0.2, "S": 0.2, "E": 0.2, "W": 0.2, "NE": 0.1, "SW": 0.1}
    dirs, probs = zip(*weights.items())
    return rng.choices(dirs, weights=probs)[0]


def vehicle_mix_for_hour(hour: float, road_type: str, rng: random.Random) -> dict[str, float]:
    """
    Proportional vehicle-class mix (sums to 1.0), shifted by time of day and
    road type. This is what turns a single density number into per-class
    counts that DensityService.calculate_pcu() can consume, exactly like a
    real PCU-calculator entry would.
    """
    is_peak = (7 <= hour < 10) or (17 <= hour < 20)
    if road_type == "highway":
        base = {"car": 0.45, "truck": 0.22, "bus": 0.12, "two_wheeler": 0.15, "taxi": 0.06}
    elif road_type == "service":
        base = {"two_wheeler": 0.55, "auto_rickshaw": 0.15, "cycle": 0.10, "car": 0.12, "e_rickshaw": 0.08}
    else:  # urban
        base = {"two_wheeler": 0.42, "car": 0.22, "auto_rickshaw": 0.12, "bus": 0.10, "taxi": 0.08, "mini_bus": 0.06}

    if is_peak:
        base["bus"] = base.get("bus", 0) * 1.6
        base["mini_bus"] = base.get("mini_bus", 0) * 1.4

    total = sum(base.values())
    mix = {k: v / total for k, v in base.items()}
    # small per-observation jitter so it's not a rigid deterministic mix
    mix = {k: max(0.0, v + rng.gauss(0, 0.015)) for k, v in mix.items()}
    total = sum(mix.values())
    return {k: v / total for k, v in mix.items()}


def free_flow_speed(road_type: str) -> float:
    return {"urban": 45.0, "highway": 70.0, "service": 25.0}.get(road_type, 40.0)


def generate_observations(
    intersection: Intersection,
    start: datetime,
    days: int,
    interval_minutes: int,
    rng: random.Random,
    density_service: DensityService,
) -> list[dict]:
    rows: list[dict] = []
    total_minutes = days * 24 * 60
    t = 0.0
    capacity_map = {"urban": 50, "highway": 80, "service": 25}
    capacity = intersection.lanes * capacity_map.get(intersection.road_type, 50)

    while t < total_minutes:
        # jittered interval: mean interval_minutes, +/- 40%, never below 2 min
        step = max(2.0, rng.gauss(interval_minutes, interval_minutes * 0.4))
        t += step
        captured_at = start + timedelta(minutes=t)
        ist_time = captured_at.astimezone(IST)
        hour = ist_time.hour + ist_time.minute / 60
        is_weekend = ist_time.weekday() >= 5

        base_density = diurnal_density_curve(hour, is_weekend)
        weather = pick_weather(ist_time.month, int(hour), rng)
        weather_mult = WEATHER_MULTIPLIERS.get(weather, 1.0)

        # Known ground-truth density before noise -- this is the number we
        # could, in principle, recover perfectly; noise below sets the
        # theoretical ceiling on achievable R^2.
        target_density = min(base_density * weather_mult, 0.98)
        noisy_density = max(0.02, min(0.99, target_density + rng.gauss(0, 0.035)))

        # ~30% of rows: manual count only, no PCU breakdown (pcu_total missing,
        # density from the plain formula). ~70%: PCU-calculator style entry.
        if rng.random() < 0.30:
            vehicle_count = max(0, round(noisy_density * capacity + rng.gauss(0, 2)))
            density = density_service.calculate(vehicle_count, intersection.lanes, intersection.road_type)
            pcu_total = None
        else:
            target_pcu = noisy_density * capacity
            mix = vehicle_mix_for_hour(hour, intersection.road_type, rng)
            class_counts = {
                k: max(0, round(target_pcu * proportion / density_service.PCU_WEIGHTS.get(k, 1.0)))
                for k, proportion in mix.items()
            }
            density, pcu_total = density_service.calculate_pcu(class_counts, intersection.lanes, intersection.road_type)
            vehicle_count = sum(class_counts.values())

        speed_noise_std = 6.0
        speed = free_flow_speed(intersection.road_type) * (1 - 0.65 * density) + rng.gauss(0, speed_noise_std)
        speed = max(2.0, speed)
        avg_speed = None if rng.random() < 0.08 else round(speed, 1)

        rows.append(
            dict(
                id=uuid.uuid4(),
                intersection_id=intersection.id,
                direction=pick_direction(hour, rng),
                vehicle_count=int(vehicle_count),
                density=round(density, 4),
                avg_speed=avg_speed,
                occupancy=None,
                weather_condition=weather,
                pcu_total=round(pcu_total, 2) if pcu_total is not None else None,
                source=rng.choices(["manual", "vision"], weights=[0.6, 0.4])[0],
                captured_at=captured_at,
                created_at=captured_at,
            )
        )
    return rows


def get_or_create_intersections(session: Session, count: int, reuse_existing: bool) -> list[Intersection]:
    if reuse_existing:
        existing = list(session.scalars(select(Intersection)).all())
        if not existing:
            raise SystemExit("--reuse-existing was set but no intersections exist in the database.")
        return existing[:count] if count else existing

    intersections = []
    for name, lanes, road_type in SAMPLE_INTERSECTIONS[:count]:
        existing = session.scalar(select(Intersection).where(Intersection.name == name))
        if existing:
            intersections.append(existing)
            continue
        intersection = Intersection(
            name=name, latitude=12.97 + random.uniform(-0.05, 0.05),
            longitude=77.59 + random.uniform(-0.05, 0.05),
            lanes=lanes, road_type=road_type, status="active",
        )
        session.add(intersection)
        intersections.append(intersection)
    session.flush()
    return intersections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--intersections", type=int, default=3, help="Number of intersections to generate/use (default: 3)")
    parser.add_argument("--days", type=int, default=45, help="Days of history per intersection (default: 45)")
    parser.add_argument("--interval-minutes", type=float, default=8.0, help="Mean minutes between observations (default: 8)")
    parser.add_argument("--reuse-existing", action="store_true", help="Use existing intersections instead of creating SIM- ones")
    parser.add_argument("--batch-size", type=int, default=2000, help="Rows per bulk-insert batch (default: 2000)")
    parser.add_argument("--dry-run", action="store_true", help="Print stats and one sample row, write nothing to the DB")
    args = parser.parse_args()

    rng = random.Random(RNG_SEED)
    settings = get_settings()
    density_service = DensityService()
    start = datetime.now(UTC) - timedelta(days=args.days)

    print(f"Target database: {settings.database_url.split('@')[-1]}")  # hide credentials
    if args.dry_run:
        fake = Intersection(id=uuid.uuid4(), name="SIM-dry-run", lanes=4, road_type="urban")
        sample = generate_observations(fake, start, days=2, interval_minutes=args.interval_minutes, rng=rng, density_service=density_service)
        print(f"Would generate ~{len(sample) * args.intersections * args.days // 2} rows total across {args.intersections} intersections.")
        print("Sample row:", sample[len(sample) // 2])
        return

    with Session(engine) as session:
        intersections = get_or_create_intersections(session, args.intersections, args.reuse_existing)
        session.commit()

        total_written = 0
        for intersection in intersections:
            rows = generate_observations(
                intersection, start, args.days, args.interval_minutes, rng, density_service,
            )
            for i in range(0, len(rows), args.batch_size):
                batch = rows[i:i + args.batch_size]
                session.execute(TrafficObservation.__table__.insert(), batch)
                session.commit()
                total_written += len(batch)
                print(f"  {intersection.name}: {total_written} rows written so far...")

        print(f"\nDone. {total_written} observations across {len(intersections)} intersections, "
              f"spanning {args.days} days back from now.")
        print("Next: POST /api/v1/predictions/train (or call PredictionService.train() directly).")


if __name__ == "__main__":
    main()