import json
import logging
import zoneinfo
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import joblib
import numpy as np
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

from app.core.config import get_settings
from app.models import TrafficObservation

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
MIN_TRAINING_SAMPLES = 200
WEATHER_CODE_MAP = {"clear": 0, "light_rain": 1, "heavy_rain": 2, "fog": 3, "smog": 4}
PEAK_HOUR_RANGES = ((7, 10), (17, 20))


class IntersectionEncoder:
    """Maps intersection UUIDs to stable sequential integers for ML features."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._map: dict[str, int] = {}
        if path.exists():
            self._map = json.loads(path.read_text(encoding="utf-8"))

    def encode(self, intersection_id: UUID) -> int:
        key = str(intersection_id)
        if key not in self._map:
            self._map[key] = len(self._map)
            self.path.write_text(json.dumps(self._map), encoding="utf-8")
        return self._map[key]

    def size(self) -> int:
        return len(self._map)


class TrafficPredictor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = Path(self.settings.model_dir) / "traffic_random_forest.joblib"
        self.version_path = Path(self.settings.model_dir) / "traffic_random_forest.version"
        self.encoder_path = Path(self.settings.model_dir) / "intersection_encoder.json"
        self.encoder = IntersectionEncoder(self.encoder_path)
        self._cached_model: RandomForestRegressor | None = None
        self._cached_version: str | None = None

    def train(self, observations: list[TrafficObservation]) -> tuple[str, int, float | None]:
        if len(observations) < MIN_TRAINING_SAMPLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient training data: {len(observations)} samples found, "
                    f"minimum {MIN_TRAINING_SAMPLES} required. "
                    "Log more observations before training."
                ),
            )

        logger.info("Training model on %d observations", len(observations))
        ordered_observations = sorted(observations, key=lambda row: row.captured_at)
        features = self._build_features(ordered_observations)
        targets = np.array([[row.density, row.vehicle_count] for row in ordered_observations])

        model = RandomForestRegressor(
            n_estimators=80,
            random_state=42,
            min_samples_leaf=2,
            max_depth=12,
            n_jobs=1,
        )
        score: float | None = None
        if len(observations) >= 12:
            split_idx = int(len(features) * 0.75)
            x_train, x_test = features[:split_idx], features[split_idx:]
            y_train, y_test = targets[:split_idx], targets[split_idx:]
            model.fit(x_train, y_train)
            score = float(r2_score(y_test, model.predict(x_test)))
        else:
            model.fit(features, targets)

        version = f"rf-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        joblib.dump(model, self.model_path)
        self._cached_model = model
        self._cached_version = version
        self.version_path.write_text(version, encoding="utf-8")
        logger.info("Model trained: version=%s, score=%s", version, score)
        return version, len(observations), score

    def predict(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        latest_vehicle_count: int,
        weather_condition: str = "clear",
        pcu_total: float | None = None,
        direction: str = "ALL",
        density: float = 0.0,
        avg_speed: float | None = None,
        hour_of_day: int | None = None,
        day_of_week: int | None = None,
    ) -> tuple[float, float, str]:
        logger.debug("Predicting for intersection=%s at %s", intersection_id, captured_at)
        model = self._load_model()
        features = np.array(
            [
                self._features(
                    intersection_id,
                    captured_at,
                    latest_vehicle_count,
                    weather_condition,
                    pcu_total,
                    direction,
                    density,
                    avg_speed,
                    hour_of_day,
                    day_of_week,
                )
            ]
        )
        density, vehicle_count = model.predict(features)[0]
        version = self.version_path.read_text(encoding="utf-8").strip() if self.version_path.exists() else "unknown"
        return float(np.clip(density, 0, 1)), max(float(vehicle_count), 0.0), version

    def _load_model(self) -> RandomForestRegressor:
        if not self.model_path.exists():
            raise ValueError("Prediction model has not been trained")
        current_version = (
            self.version_path.read_text(encoding="utf-8").strip()
            if self.version_path.exists()
            else "unknown"
        )
        if self._cached_model is None or self._cached_version != current_version:
            self._cached_model = joblib.load(self.model_path)
            self._cached_version = current_version
        return self._cached_model

    def _features(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        latest_vehicle_count: int,
        weather_condition: str = "clear",
        pcu_total: float | None = None,
        direction: str = "ALL",
        density: float = 0.0,
        avg_speed: float | None = None,
        hour_of_day: int | None = None,
        day_of_week: int | None = None,
    ) -> list[float]:
        from app.core.india_calendar import is_indian_holiday

        ist_time = captured_at.astimezone(IST)
        hour = hour_of_day if hour_of_day is not None else ist_time.hour
        dow = day_of_week if day_of_week is not None else ist_time.weekday()
        is_peak = int(any(start <= hour < end for start, end in PEAK_HOUR_RANGES))
        weather_code = WEATHER_CODE_MAP.get(weather_condition, 0)
        direction_map = {"ALL": 0, "N": 1, "S": 2, "E": 3, "W": 4, "NE": 5, "NW": 6, "SE": 7, "SW": 8}
        direction_code = direction_map.get(direction, 0)
        effective_count = pcu_total if pcu_total is not None else float(latest_vehicle_count)

        return [
            self.encoder.encode(intersection_id),
            hour,
            dow,
            ist_time.minute // 15,
            effective_count,
            weather_code,
            is_indian_holiday(ist_time.date()),
            1 if ist_time.month in (6, 7, 8, 9) else 0,
            direction_code,
            float(latest_vehicle_count),
            density,
            pcu_total or 0.0,
            avg_speed or 0.0,
            is_peak,
        ]

    def _build_features(self, observations: list[TrafficObservation]) -> np.ndarray:
        rows = []
        for obs in observations:
            rows.append(
                self._features(
                    obs.intersection_id,
                    obs.captured_at,
                    obs.vehicle_count,
                    obs.weather_condition,
                    obs.pcu_total,
                    obs.direction,
                    obs.density,
                    obs.avg_speed,
                )
            )
        return np.array(rows, dtype=float)
