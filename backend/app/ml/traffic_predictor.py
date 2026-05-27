from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.models import TrafficObservation


class TrafficPredictor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = Path(self.settings.model_dir) / "traffic_random_forest.joblib"
        self.version_path = Path(self.settings.model_dir) / "traffic_random_forest.version"

    def train(self, observations: list[TrafficObservation]) -> tuple[str, int, float | None]:
        if len(observations) < 8:
            raise ValueError("At least 8 traffic observations are required to train the predictor")

        features = np.array([self._features(row.intersection_id, row.captured_at, row.vehicle_count) for row in observations])
        targets = np.array([[row.density, row.vehicle_count] for row in observations])

        model = RandomForestRegressor(
            n_estimators=80,
            random_state=42,
            min_samples_leaf=2,
            max_depth=12,
            n_jobs=1,
        )
        score: float | None = None
        if len(observations) >= 12:
            x_train, x_test, y_train, y_test = train_test_split(features, targets, test_size=0.25, random_state=42)
            model.fit(x_train, y_train)
            score = float(r2_score(y_test, model.predict(x_test)))
        else:
            model.fit(features, targets)

        version = f"rf-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        joblib.dump(model, self.model_path)
        self.version_path.write_text(version, encoding="utf-8")
        return version, len(observations), score

    def predict(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        latest_vehicle_count: int,
    ) -> tuple[float, float, str]:
        if not self.model_path.exists():
            raise ValueError("Prediction model has not been trained")
        model = joblib.load(self.model_path)
        features = np.array([self._features(intersection_id, captured_at, latest_vehicle_count)])
        density, vehicle_count = model.predict(features)[0]
        version = self.version_path.read_text(encoding="utf-8").strip() if self.version_path.exists() else "unknown"
        return float(np.clip(density, 0, 1)), max(float(vehicle_count), 0.0), version

    @staticmethod
    def _features(intersection_id: UUID, captured_at: datetime, latest_vehicle_count: int) -> list[float]:
        intersection_bucket = int(intersection_id.int % 1000)
        return [
            intersection_bucket,
            captured_at.hour,
            captured_at.weekday(),
            captured_at.minute // 15,
            latest_vehicle_count,
        ]
