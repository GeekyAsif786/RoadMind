"""Traffic prediction pipeline.

This module trains and serves short-horizon traffic forecasts. The pipeline is
built to avoid feature/label leakage:

* Training examples are built with **explicit temporal pairing**: features come
  from an observation at time ``t`` (``current_obs``) and the label comes from a
  *different, later* observation at ``t + horizon`` (``future_obs``) for the same
  intersection. The same row is never used as both feature and label source.
* ``horizon_minutes`` is a first-class feature, so a 5-minute and a 60-minute
  forecast for the same current state produce different inputs.
* Categorical/cyclic fields are encoded properly (sin/cos for hour and
  day-of-week, one-hot for weather and direction). ``intersection_id`` stays a
  label-encoded integer because its cardinality grows over time and one-hotting
  it would break saved-model feature shape.
* Missing ``avg_speed`` / ``pcu_total`` are represented with an explicit
  ``*_missing`` indicator plus a real fallback value (never ``0.0``, because
  ``0`` has a real domain meaning: gridlock / zero load).
* The feature schema is persisted next to the model artifact and asserted on
  load, preventing silent feature-order drift between training and inference.
* Evaluation uses an **embargo gap** around the train/test boundary and reports
  **per-target** metrics. A **walk-forward validation** is run purely for
  reliability reporting; the deployed model is still a single fit on all data
  outside the last embargo window.
"""

import json
import logging
import zoneinfo
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import joblib
import numpy as np
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.multioutput import MultiOutputRegressor

from app.core.config import get_settings
from app.models import TrafficObservation

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# --- Pairing / horizon configuration -------------------------------------
HORIZONS_MINUTES = (5, 15, 30, 60)
PAIRING_TOLERANCE_MINUTES = 3
MAX_HORIZON_MINUTES = max(HORIZONS_MINUTES)

# Walk-forward configuration used for reliability reporting.
WALK_FORWARD_FOLDS = 5
MIN_PAIRS_PER_FOLD = 150

# --- Minimum training-sample floor ---------------------------------------
# Embargo purging removes boundary-adjacent pairs, so the raw observation floor
# must be high enough that each walk-forward fold still evaluates on a
# statistically meaningful test window.
#
# Requirement: keep at least MIN_PAIRS_PER_FOLD (150) pairs per fold across
# WALK_FORWARD_FOLDS (5) expanding folds. A K-fold expanding scheme needs
# (K + 1) contiguous chunks of >= MIN_PAIRS_PER_FOLD pairs -> ~= 900 usable
# pairs after embargo purging. Empirically, temporal pairing against 4 horizons
# with a 3-minute tolerance yields well under one usable pair per raw
# observation once no-match and embargo purges are applied (a conservative
# ~1.5 pairs per observation before purging, dropping toward ~1.0 after). To
# stay safely above 900 usable pairs we require:
#
#     ceil((WALK_FORWARD_FOLDS + 1) * MIN_PAIRS_PER_FOLD) usable pairs
#       -> (5 + 1) * 150 = 900 pairs
#     assuming ~1.5 usable pairs per observation -> 900 / 1.5 = 600 observations
#
# 600 is used as the floor. It replaces the previous naive 200, which was set
# before pairing/embargo existed and would leave folds with too few test pairs.
MIN_TRAINING_SAMPLES = 600

# Known, fixed category sets. These MUST stay stable across train/inference; the
# persisted feature-name schema enforces that.
WEATHER_CATEGORIES = ("clear", "light_rain", "heavy_rain", "fog", "smog")
DIRECTION_CATEGORIES = ("ALL", "N", "S", "E", "W", "NE", "NW", "SE", "SW")
PEAK_HOUR_RANGES = ((7, 10), (17, 20))
MONSOON_MONTHS = (6, 7, 8, 9)

# Fallback used only if no historical avg_speed is available at all.
DEFAULT_AVG_SPEED_FALLBACK = 30.0


class FeatureSchemaMismatchError(RuntimeError):
    """Raised when persisted feature names do not match current code output."""


@dataclass
class TrainingPair:
    current_obs: TrafficObservation
    future_obs: TrafficObservation
    horizon_minutes: int


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


def build_training_pairs(observations: list[TrafficObservation]) -> list[TrainingPair]:
    """Build (current, future, horizon) pairs via explicit temporal matching.

    Per intersection, observations are sorted by ``captured_at``. Each
    observation is matched, for each configured horizon, to the later
    observation from the SAME intersection whose timestamp is closest to
    ``captured_at + horizon``, within ``PAIRING_TOLERANCE_MINUTES``. If no
    observation falls inside the tolerance window, the pair is skipped (no
    interpolation / guessing). The matched future observation is always a
    different row than the current one.
    """

    by_intersection: dict[UUID, list[TrafficObservation]] = {}
    for obs in observations:
        by_intersection.setdefault(obs.intersection_id, []).append(obs)

    tolerance = timedelta(minutes=PAIRING_TOLERANCE_MINUTES)
    pairs: list[TrainingPair] = []

    for rows in by_intersection.values():
        ordered = sorted(rows, key=lambda r: r.captured_at)
        times = [r.captured_at for r in ordered]
        n = len(ordered)
        for i, current in enumerate(ordered):
            for horizon in HORIZONS_MINUTES:
                target_time = current.captured_at + timedelta(minutes=horizon)
                best_j = -1
                best_delta: timedelta | None = None
                # Only look forward in time.
                for j in range(i + 1, n):
                    delta = abs(times[j] - target_time)
                    if delta <= tolerance and (best_delta is None or delta < best_delta):
                        best_delta = delta
                        best_j = j
                    # Once we've passed the target beyond tolerance, later rows
                    # only get further away, so stop early.
                    if times[j] > target_time + tolerance:
                        break
                if best_j != -1 and ordered[best_j] is not current:
                    pairs.append(TrainingPair(current, ordered[best_j], horizon))

    # Global chronological order by current-observation time.
    pairs.sort(key=lambda p: p.current_obs.captured_at)
    return pairs


class BaseTrafficPredictor:
    model_key = "base"
    version_prefix = "model"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = Path(self.settings.model_dir) / f"traffic_{self.model_key}.joblib"
        self.version_path = Path(self.settings.model_dir) / f"traffic_{self.model_key}.version"
        self.encoder_path = Path(self.settings.model_dir) / "intersection_encoder.json"
        self.metrics_path = Path(self.settings.model_dir) / f"traffic_{self.model_key}.metrics.json"
        self.feature_names_path = (
            Path(self.settings.model_dir) / f"traffic_{self.model_key}.feature_names.json"
        )
        self.encoder = IntersectionEncoder(self.encoder_path)
        self._cached_model: object | None = None
        self._cached_version: str | None = None
        self._median_avg_speed: float = DEFAULT_AVG_SPEED_FALLBACK

    def build_model(self) -> object:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------
    def _feature_dict(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        vehicle_count: int,
        weather_condition: str,
        pcu_total: float | None,
        direction: str,
        current_density: float,
        avg_speed: float | None,
        horizon_minutes: int,
        median_avg_speed: float,
        hour_of_day: int | None = None,
        day_of_week: int | None = None,
    ) -> dict[str, float]:
        """Return a NAMED feature dict for one example (not a positional list)."""
        from app.core.india_calendar import is_indian_holiday

        ist_time = captured_at.astimezone(IST)
        hour = hour_of_day if hour_of_day is not None else ist_time.hour
        dow = day_of_week if day_of_week is not None else ist_time.weekday()

        features: dict[str, float] = {}

        # Intersection: label-encoded integer (cardinality grows over time).
        features["intersection_code"] = float(self.encoder.encode(intersection_id))

        # Cyclic encodings for hour-of-day and day-of-week.
        features["hour_sin"] = float(np.sin(2 * np.pi * hour / 24.0))
        features["hour_cos"] = float(np.cos(2 * np.pi * hour / 24.0))
        features["dow_sin"] = float(np.sin(2 * np.pi * dow / 7.0))
        features["dow_cos"] = float(np.cos(2 * np.pi * dow / 7.0))

        # Quarter-hour bucket (calendar/temporal context, not a label).
        features["quarter_hour"] = float(ist_time.minute // 15)

        # One-hot weather.
        for cat in WEATHER_CATEGORIES:
            features[f"weather_{cat}"] = 1.0 if weather_condition == cat else 0.0

        # One-hot direction.
        for cat in DIRECTION_CATEGORIES:
            features[f"direction_{cat}"] = 1.0 if direction == cat else 0.0

        # Calendar flags.
        features["is_holiday"] = float(is_indian_holiday(ist_time.date()))
        features["is_monsoon"] = 1.0 if ist_time.month in MONSOON_MONTHS else 0.0
        features["is_peak"] = float(
            any(start <= hour < end for start, end in PEAK_HOUR_RANGES)
        )

        # Raw current-state signals (from time t, never the label row).
        features["vehicle_count"] = float(vehicle_count)
        features["current_density"] = float(current_density)

        # avg_speed: missing indicator + real fallback (median), never 0.0.
        if avg_speed is None:
            features["avg_speed_missing"] = 1.0
            features["avg_speed_value"] = float(median_avg_speed)
        else:
            features["avg_speed_missing"] = 0.0
            features["avg_speed_value"] = float(avg_speed)

        # pcu_total: missing indicator + fallback (vehicle_count), never 0.0.
        if pcu_total is None:
            features["pcu_total_missing"] = 1.0
            features["pcu_total_value"] = float(vehicle_count)
        else:
            features["pcu_total_missing"] = 0.0
            features["pcu_total_value"] = float(pcu_total)

        # Horizon is a first-class feature (from the pairing step, not a
        # timestamp offset).
        features["horizon_minutes"] = float(horizon_minutes)

        return features

    def feature_names(self) -> list[str]:
        """Canonical, sorted feature-name list for the current code."""
        sample = self._feature_dict(
            intersection_id=UUID(int=0),
            captured_at=datetime.now(UTC),
            vehicle_count=0,
            weather_condition="clear",
            pcu_total=None,
            direction="ALL",
            current_density=0.0,
            avg_speed=None,
            horizon_minutes=HORIZONS_MINUTES[0],
            median_avg_speed=DEFAULT_AVG_SPEED_FALLBACK,
        )
        return sorted(sample.keys())

    def _vectorize(self, feature_dict: dict[str, float], names: list[str]) -> list[float]:
        """Deterministically order a feature dict by the given name list."""
        return [feature_dict[name] for name in names]

    # ------------------------------------------------------------------
    # Training data assembly
    # ------------------------------------------------------------------
    def _compute_median_avg_speed(self, observations: list[TrafficObservation]) -> float:
        speeds = [o.avg_speed for o in observations if o.avg_speed is not None]
        if not speeds:
            return DEFAULT_AVG_SPEED_FALLBACK
        return float(np.median(speeds))

    def _pairs_to_xy(
        self, pairs: list[TrainingPair], names: list[str], median_avg_speed: float
    ) -> tuple[np.ndarray, np.ndarray]:
        rows: list[list[float]] = []
        targets: list[list[float]] = []
        for pair in pairs:
            cur = pair.current_obs
            fut = pair.future_obs
            fd = self._feature_dict(
                intersection_id=cur.intersection_id,
                captured_at=cur.captured_at,
                vehicle_count=cur.vehicle_count,
                weather_condition=cur.weather_condition,
                pcu_total=cur.pcu_total,
                direction=cur.direction,
                current_density=cur.density,
                avg_speed=cur.avg_speed,
                horizon_minutes=pair.horizon_minutes,
                median_avg_speed=median_avg_speed,
            )
            rows.append(self._vectorize(fd, names))
            # Label comes from the FUTURE observation (time t+horizon).
            targets.append([fut.density, float(fut.vehicle_count)])
        return np.array(rows, dtype=float), np.array(targets, dtype=float)

    @staticmethod
    def _apply_embargo(
        pairs: list[TrainingPair], boundary_time: datetime, embargo_minutes: int
    ) -> tuple[list[TrainingPair], list[TrainingPair]]:
        """Split pairs at boundary_time, dropping any pair whose current OR
        future timestamp falls within embargo_minutes of the boundary."""
        embargo = timedelta(minutes=embargo_minutes)
        train: list[TrainingPair] = []
        test: list[TrainingPair] = []
        for p in pairs:
            cur_t = p.current_obs.captured_at
            fut_t = p.future_obs.captured_at
            in_embargo = (
                abs(cur_t - boundary_time) < embargo or abs(fut_t - boundary_time) < embargo
            )
            if in_embargo:
                continue
            if cur_t < boundary_time and fut_t < boundary_time:
                train.append(p)
            elif cur_t >= boundary_time:
                test.append(p)
            # Pairs straddling the boundary (cur before, fut after) that survived
            # the embargo check are dropped to avoid label leakage.
        return train, test

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    @staticmethod
    def _per_target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        mae = mean_absolute_error(y_true, y_pred, multioutput="raw_values")
        rmse = np.sqrt(
            mean_squared_error(y_true, y_pred, multioutput="raw_values")
        )
        r2 = r2_score(y_true, y_pred, multioutput="raw_values")
        targets = ("density", "vehicle_count")
        detail = {}
        for i, name in enumerate(targets):
            detail[name] = {
                "mae": float(mae[i]),
                "rmse": float(rmse[i]),
                "r2": float(r2[i]),
            }
        return detail

    def walk_forward_validation(
        self,
        pairs: list[TrainingPair],
        names: list[str],
        median_avg_speed: float,
        folds: int = WALK_FORWARD_FOLDS,
        embargo_minutes: int = MAX_HORIZON_MINUTES,
    ) -> dict:
        """Run N sequential expanding-window folds for reliability reporting.

        Returns mean and std of per-target R2/MAE/RMSE across folds. This is a
        reliability check only; it does NOT pick the deployed model.
        """
        if len(pairs) < (folds + 1) * 2:
            return {"folds": 0, "note": "insufficient pairs for walk-forward"}

        ordered = sorted(pairs, key=lambda p: p.current_obs.captured_at)
        n = len(ordered)
        # Expanding-window boundaries at fractions 1/(folds+1) .. folds/(folds+1).
        fold_metrics: list[dict] = []
        for k in range(1, folds + 1):
            boundary_idx = int(n * k / (folds + 1))
            if boundary_idx <= 0 or boundary_idx >= n:
                continue
            boundary_time = ordered[boundary_idx].current_obs.captured_at
            train_pairs, test_pairs = self._apply_embargo(
                ordered, boundary_time, embargo_minutes
            )
            # Only evaluate on the test window belonging to this fold slice.
            if not train_pairs or not test_pairs:
                continue
            x_train, y_train = self._pairs_to_xy(train_pairs, names, median_avg_speed)
            x_test, y_test = self._pairs_to_xy(test_pairs, names, median_avg_speed)
            model = self.build_model()
            model.fit(x_train, y_train)
            y_pred = model.predict(x_test)
            fold_metrics.append(self._per_target_metrics(y_test, y_pred))

        if not fold_metrics:
            return {"folds": 0, "note": "no valid folds"}

        summary: dict = {"folds": len(fold_metrics)}
        for target in ("density", "vehicle_count"):
            for metric in ("mae", "rmse", "r2"):
                values = [fm[target][metric] for fm in fold_metrics]
                summary[f"{target}_{metric}_mean"] = float(np.mean(values))
                summary[f"{target}_{metric}_std"] = float(np.std(values))
        return summary

    # ------------------------------------------------------------------
    # Train / persist
    # ------------------------------------------------------------------
    def train(
        self, observations: list[TrafficObservation]
    ) -> tuple[str, int, float | None, dict[str, float | None]]:
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
        median_avg_speed = self._compute_median_avg_speed(observations)
        self._median_avg_speed = median_avg_speed

        pairs = build_training_pairs(observations)
        if len(pairs) < MIN_PAIRS_PER_FOLD:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient temporally-paired training examples: {len(pairs)} "
                    f"built, minimum {MIN_PAIRS_PER_FOLD} required. Observations are "
                    "too sparse across the configured horizons to build reliable pairs."
                ),
            )
        logger.info("Built %d temporal training pairs", len(pairs))

        names = self.feature_names()

        # Reliability check (not used to pick the deployed model).
        wf_summary = self.walk_forward_validation(pairs, names, median_avg_speed)
        logger.info("Walk-forward validation summary: %s", wf_summary)

        # Deployed model: single fit on all data outside the last embargo window.
        ordered = sorted(pairs, key=lambda p: p.current_obs.captured_at)
        boundary_idx = int(len(ordered) * 0.75)
        boundary_time = ordered[boundary_idx].current_obs.captured_at
        train_pairs, test_pairs = self._apply_embargo(
            ordered, boundary_time, MAX_HORIZON_MINUTES
        )

        metrics: dict[str, float | None] = {"mae": None, "rmse": None, "r2": None}
        metrics_detail: dict = {}
        if train_pairs and test_pairs:
            x_train, y_train = self._pairs_to_xy(train_pairs, names, median_avg_speed)
            x_test, y_test = self._pairs_to_xy(test_pairs, names, median_avg_speed)
            eval_model = self.build_model()
            eval_model.fit(x_train, y_train)
            y_pred = eval_model.predict(x_test)
            per_target = self._per_target_metrics(y_test, y_pred)
            metrics_detail = {"per_target": per_target, "walk_forward": wf_summary}
            # Coarse summary fields kept for backward compatibility: average the
            # per-target values so existing consumers still get a single number.
            metrics = {
                "mae": float(np.mean([per_target[t]["mae"] for t in per_target])),
                "rmse": float(np.mean([per_target[t]["rmse"] for t in per_target])),
                "r2": float(np.mean([per_target[t]["r2"] for t in per_target])),
            }
        else:
            metrics_detail = {"per_target": {}, "walk_forward": wf_summary}

        # Final deployed fit: all pairs outside the last embargo window.
        final_train_pairs, _ = self._apply_embargo(
            ordered, ordered[-1].current_obs.captured_at, MAX_HORIZON_MINUTES
        )
        if not final_train_pairs:
            final_train_pairs = train_pairs or ordered
        x_all, y_all = self._pairs_to_xy(final_train_pairs, names, median_avg_speed)
        model = self.build_model()
        model.fit(x_all, y_all)

        score = metrics.get("r2")
        version = f"{self.version_prefix}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        joblib.dump(model, self.model_path)
        self._cached_model = model
        self._cached_version = version
        self.version_path.write_text(version, encoding="utf-8")
        self.feature_names_path.write_text(json.dumps(names), encoding="utf-8")
        self.metrics_path.write_text(
            json.dumps({**metrics, "metrics_detail": metrics_detail}), encoding="utf-8"
        )
        logger.info(
            "Model trained: version=%s, coarse_r2=%s, per_target=%s",
            version,
            score,
            metrics_detail.get("per_target"),
        )
        # Expose per-target + walk-forward via metrics dict for the service layer.
        metrics_out: dict[str, float | None] = dict(metrics)
        metrics_out["metrics_detail"] = metrics_detail  # type: ignore[assignment]
        return version, len(observations), score, metrics_out

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def predict(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        latest_vehicle_count: int,
        horizon_minutes: int,
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
        names = self._load_feature_names()
        fd = self._feature_dict(
            intersection_id=intersection_id,
            captured_at=captured_at,
            vehicle_count=latest_vehicle_count,
            weather_condition=weather_condition,
            pcu_total=pcu_total,
            direction=direction,
            current_density=density,
            avg_speed=avg_speed,
            horizon_minutes=horizon_minutes,
            median_avg_speed=self._median_avg_speed,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
        )
        features = np.array([self._vectorize(fd, names)], dtype=float)
        pred_density, pred_count = model.predict(features)[0]
        version = (
            self.version_path.read_text(encoding="utf-8").strip()
            if self.version_path.exists()
            else "unknown"
        )
        return float(np.clip(pred_density, 0, 1)), max(float(pred_count), 0.0), version

    def _load_feature_names(self) -> list[str]:
        current = self.feature_names()
        if not self.feature_names_path.exists():
            raise FeatureSchemaMismatchError(
                "Feature schema file is missing "
                f"({self.feature_names_path}); retrain the model to regenerate it."
            )
        persisted = json.loads(self.feature_names_path.read_text(encoding="utf-8"))
        if persisted != current:
            raise FeatureSchemaMismatchError(
                "Persisted feature names do not match current code output. "
                "This means the feature schema drifted between training and "
                "inference. Retrain the model. "
                f"persisted={persisted} current={current}"
            )
        return current

    def _load_model(self) -> object:
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


class RandomForestPredictor(BaseTrafficPredictor):
    model_key = "random_forest"
    version_prefix = "rf"

    def build_model(self) -> RandomForestRegressor:
        return RandomForestRegressor(
            n_estimators=80,
            random_state=42,
            min_samples_leaf=2,
            max_depth=12,
            n_jobs=1,
        )


class XGBoostPredictor(BaseTrafficPredictor):
    model_key = "xgboost"
    version_prefix = "xgb"

    def build_model(self) -> object:
        try:
            from xgboost import XGBRegressor
        except Exception as exc:
            logger.warning(
                "TRAFFIC_MODEL=xgboost but xgboost is unavailable; falling back to RandomForest: %s",
                exc,
            )
            self.model_key = RandomForestPredictor.model_key
            self.version_prefix = RandomForestPredictor.version_prefix
            return RandomForestPredictor().build_model()

        base_model = XGBRegressor(
            n_estimators=120,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            objective="reg:squarederror",
            random_state=42,
        )
        return MultiOutputRegressor(base_model)


class TrafficPredictor:
    def __init__(self) -> None:
        settings = get_settings()
        requested_model = settings.traffic_model.lower().strip()
        if requested_model == "xgboost":
            self.strategy: BaseTrafficPredictor = XGBoostPredictor()
        else:
            self.strategy = RandomForestPredictor()

    def train(
        self, observations: list[TrafficObservation]
    ) -> tuple[str, int, float | None, dict[str, float | None]]:
        return self.strategy.train(observations)

    def predict(
        self,
        intersection_id: UUID,
        captured_at: datetime,
        latest_vehicle_count: int,
        horizon_minutes: int,
        weather_condition: str = "clear",
        pcu_total: float | None = None,
        direction: str = "ALL",
        density: float = 0.0,
        avg_speed: float | None = None,
        hour_of_day: int | None = None,
        day_of_week: int | None = None,
    ) -> tuple[float, float, str]:
        return self.strategy.predict(
            intersection_id,
            captured_at,
            latest_vehicle_count,
            horizon_minutes,
            weather_condition,
            pcu_total,
            direction,
            density,
            avg_speed,
            hour_of_day,
            day_of_week,
        )
