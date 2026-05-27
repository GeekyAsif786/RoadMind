import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

from app.core.config import get_settings
from app.models import TrafficObservation

logger = logging.getLogger(__name__)


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
        if len(observations) < 8:
            raise ValueError("At least 8 traffic observations are required to train the predictor")

        logger.info("Training model on %d observations", len(observations))
        ordered_observations = sorted(observations, key=lambda row: row.captured_at)
        features = np.array(
            [
                self._features(
                    row.intersection_id,
                    row.captured_at,
                    row.vehicle_count,
                    row.weather_condition,
                    row.pcu_total,
                    row.direction,
                )
                for row in ordered_observations
            ]
        )
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
    ) -> list[float]:
        from app.core.india_calendar import is_indian_holiday

        weather_map = {"clear": 0, "light_rain": 1, "heavy_rain": 2, "fog": 3, "smog": 4}
        weather_code = weather_map.get(weather_condition, 0)
        direction_map = {"ALL": 0, "N": 1, "S": 2, "E": 3, "W": 4, "NE": 5, "NW": 6, "SE": 7, "SW": 8}
        direction_code = direction_map.get(direction, 0)
        effective_count = pcu_total if pcu_total is not None else float(latest_vehicle_count)

        return [
            self.encoder.encode(intersection_id),
            captured_at.hour,
            captured_at.weekday(),
            captured_at.minute // 15,
            effective_count,
            weather_code,
            is_indian_holiday(captured_at.date()),
            1 if captured_at.month in (6, 7, 8, 9) else 0,
            direction_code,
        ]
