"""Tests for ML feature/label leakage and evaluation methodology.

These verify the fixes in app.ml.traffic_predictor:
- No feature column trivially correlates with a target column.
- horizon_minutes actually changes predictions.
- feature_names.json schema drift raises a clear error on load.
- avg_speed=None differs from avg_speed=0.0 (missing indicator works).
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest


@pytest.fixture()
def predictor(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("TRAFFIC_MODEL", "random_forest")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.ml.traffic_predictor import RandomForestPredictor

    p = RandomForestPredictor()
    yield p
    get_settings.cache_clear()


class _Obs:
    """Lightweight stand-in for a TrafficObservation ORM row."""

    def __init__(self, intersection_id, captured_at, vehicle_count, density,
                 weather="clear", direction="ALL", avg_speed=None, pcu_total=None):
        self.intersection_id = intersection_id
        self.captured_at = captured_at
        self.vehicle_count = vehicle_count
        self.density = density
        self.weather_condition = weather
        self.direction = direction
        self.avg_speed = avg_speed
        self.pcu_total = pcu_total


def _make_multi_hour_multi_intersection(n_intersections=4, hours=24, step_minutes=5):
    """Synthetic observations across several intersections and hours.

    Each intersection has a smooth-ish daily pattern plus noise so that
    current-state features are NOT identical to the future label.
    """
    rng = np.random.default_rng(7)
    base = datetime(2026, 3, 3, 4, 0, 0, tzinfo=UTC)  # early morning UTC
    obs = []
    ids = [uuid.uuid4() for _ in range(n_intersections)]
    n_steps = int(hours * 60 / step_minutes)
    for iid in ids:
        for k in range(n_steps):
            t = base + timedelta(minutes=step_minutes * k)
            ist_hour = (t.hour + 5) % 24
            is_peak = 7 <= ist_hour < 10 or 17 <= ist_hour < 20
            level = 40 if is_peak else 15
            # count evolves over time with noise -> future != current
            count = max(1, int(level + 10 * np.sin(k / 6.0) + rng.normal(0, 6)))
            density = min(count / 200.0, 1.0)
            weather = rng.choice(["clear", "clear", "light_rain", "fog"])
            avg_speed = float(max(5.0, 60.0 - density * 45.0 + rng.normal(0, 4)))
            obs.append(_Obs(iid, t, count, density, weather=weather,
                            avg_speed=avg_speed, pcu_total=count * 1.2))
    return obs


def test_no_feature_column_leaks_target(predictor):
    from app.ml.traffic_predictor import build_training_pairs

    observations = _make_multi_hour_multi_intersection()
    pairs = build_training_pairs(observations)
    assert len(pairs) > 50, "fixture should produce many pairs"

    names = predictor.feature_names()
    median_speed = predictor._compute_median_avg_speed(observations)
    x, y = predictor._pairs_to_xy(pairs, names, median_speed)

    # For each feature column, correlation with each target column must be < 0.98.
    for col in range(x.shape[1]):
        feature = x[:, col]
        if np.std(feature) == 0:
            continue  # constant column can't correlate
        for tcol in range(y.shape[1]):
            target = y[:, tcol]
            if np.std(target) == 0:
                continue
            corr = abs(np.corrcoef(feature, target)[0, 1])
            assert corr < 0.98, (
                f"Feature '{names[col]}' correlates {corr:.3f} with target "
                f"column {tcol} — possible leakage."
            )


def test_horizon_changes_prediction(predictor):
    observations = _make_multi_hour_multi_intersection()
    predictor.train(observations)

    iid = observations[0].intersection_id
    now = datetime.now(UTC)
    kwargs = dict(
        intersection_id=iid,
        captured_at=now,
        latest_vehicle_count=30,
        weather_condition="clear",
        pcu_total=36.0,
        direction="ALL",
        density=0.15,
        avg_speed=25.0,
    )
    d5, c5, _ = predictor.predict(horizon_minutes=5, **kwargs)
    d60, c60, _ = predictor.predict(horizon_minutes=60, **kwargs)

    assert (d5, c5) != (d60, c60), (
        "5-minute and 60-minute forecasts for the same current state should differ"
    )


def test_feature_schema_drift_raises(predictor):
    observations = _make_multi_hour_multi_intersection()
    predictor.train(observations)

    # Corrupt the persisted feature names to simulate drift.
    persisted = json.loads(predictor.feature_names_path.read_text())
    persisted.append("bogus_feature_that_should_not_exist")
    predictor.feature_names_path.write_text(json.dumps(persisted))

    from app.ml.traffic_predictor import FeatureSchemaMismatchError

    with pytest.raises(FeatureSchemaMismatchError):
        predictor.predict(
            intersection_id=observations[0].intersection_id,
            captured_at=datetime.now(UTC),
            latest_vehicle_count=30,
            horizon_minutes=15,
        )


def test_missing_avg_speed_differs_from_zero(predictor):
    observations = _make_multi_hour_multi_intersection()
    predictor.train(observations)

    iid = observations[0].intersection_id
    now = datetime.now(UTC)
    kwargs = dict(
        intersection_id=iid,
        captured_at=now,
        latest_vehicle_count=30,
        horizon_minutes=15,
        weather_condition="clear",
        pcu_total=36.0,
        direction="ALL",
        density=0.15,
    )
    d_none, c_none, _ = predictor.predict(avg_speed=None, **kwargs)
    d_zero, c_zero, _ = predictor.predict(avg_speed=0.0, **kwargs)

    assert (d_none, c_none) != (d_zero, c_zero), (
        "avg_speed=None (unknown) must not produce the same prediction as "
        "avg_speed=0.0 (gridlock) — the missing indicator must matter"
    )


def test_pairs_never_share_current_and_future_row(predictor):
    from app.ml.traffic_predictor import build_training_pairs

    observations = _make_multi_hour_multi_intersection()
    pairs = build_training_pairs(observations)
    for p in pairs:
        assert p.current_obs is not p.future_obs
        assert p.future_obs.captured_at > p.current_obs.captured_at
        assert p.current_obs.intersection_id == p.future_obs.intersection_id
