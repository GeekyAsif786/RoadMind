"""Before/after accuracy comparison for the traffic prediction model.

This harness quantifies the effect of closing the feature/label leak.

* "BEFORE" reproduces the OLD methodology: the same observation row is used as
  both feature source and label source (density/vehicle_count appear on both
  sides), with a single chronological 75/25 split and NO embargo. This is the
  leaky pipeline; its R2 is optimistically inflated.
* "AFTER" uses the CURRENT pipeline: temporal pairing (features at t, label at
  t+horizon), horizon as a feature, embargo gap, per-target metrics.

Run directly:  python tests/accuracy_report.py
It is intentionally a standalone script (not a pytest test) so CI's pytest run
does not train a heavy model; leakage guarantees are covered by
tests/test_ml_leakage.py.
"""

import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp_dir = tempfile.mkdtemp()


class _MockSettings:
    model_dir = Path(_tmp_dir)
    traffic_model = "random_forest"


with patch("app.core.config.get_settings", return_value=_MockSettings()):
    from app.ml.traffic_predictor import (
        RandomForestPredictor,
        build_training_pairs,
    )


class _Obs:
    def __init__(self, iid, t, count, density, weather, avg_speed, pcu):
        self.intersection_id = iid
        self.captured_at = t
        self.vehicle_count = count
        self.density = density
        self.direction = "ALL"
        self.weather_condition = weather
        self.avg_speed = avg_speed
        self.pcu_total = pcu


def generate_observations(n_intersections=4, hours=24, step_minutes=5, seed=42):
    rng = np.random.default_rng(seed)
    base = datetime(2026, 1, 1, 4, 0, 0, tzinfo=UTC)
    obs = []
    for _ in range(n_intersections):
        iid = uuid.uuid4()
        n_steps = int(hours * 60 / step_minutes)
        for k in range(n_steps):
            t = base + timedelta(minutes=step_minutes * k)
            ist_hour = (t.hour + 5) % 24
            is_peak = 7 <= ist_hour < 10 or 17 <= ist_hour < 20
            level = 40 if is_peak else 15
            count = max(1, int(level + 10 * np.sin(k / 6.0) + rng.normal(0, 6)))
            density = min(count / 200.0, 1.0)
            weather = rng.choice(["clear", "clear", "light_rain", "fog"])
            avg_speed = float(max(5.0, 60.0 - density * 45.0 + rng.normal(0, 4)))
            obs.append(_Obs(iid, t, count, density, weather, avg_speed, count * 1.2))
    return obs


def _predictor():
    p = RandomForestPredictor()
    p.settings = _MockSettings()
    md = _MockSettings.model_dir
    p.model_path = md / "traffic_random_forest.joblib"
    p.version_path = md / "traffic_random_forest.version"
    p.encoder_path = md / "intersection_encoder.json"
    p.metrics_path = md / "traffic_random_forest.metrics.json"
    p.feature_names_path = md / "traffic_random_forest.feature_names.json"
    from app.ml.traffic_predictor import IntersectionEncoder

    p.encoder = IntersectionEncoder(p.encoder_path)
    return p


def before_r2(observations):
    """Reproduce the OLD leaky pipeline: same-row features and labels."""
    ordered = sorted(observations, key=lambda o: o.captured_at)
    # Old positional feature list included density, pcu_total, vehicle_count.
    feats = []
    for o in ordered:
        feats.append([
            o.vehicle_count,
            o.density,          # <-- leak: also part of the label
            o.pcu_total or 0.0,
            o.avg_speed or 0.0,
        ])
    x = np.array(feats, dtype=float)
    y = np.array([[o.density, o.vehicle_count] for o in ordered], dtype=float)
    split = int(len(x) * 0.75)
    model = RandomForestRegressor(n_estimators=80, random_state=42, max_depth=12,
                                  min_samples_leaf=2, n_jobs=1)
    model.fit(x[:split], y[:split])
    pred = model.predict(x[split:])
    return r2_score(y[split:], pred, multioutput="raw_values")


def after_metrics(observations):
    p = _predictor()
    version, samples, score, metrics = p.train(observations)
    detail = metrics["metrics_detail"]["per_target"]
    return score, detail, metrics["metrics_detail"]["walk_forward"]


def main():
    observations = generate_observations()
    print("\n" + "=" * 64)
    print("  Traffic Model — Before/After Leakage Fix (R2 comparison)")
    print("=" * 64)
    print(f"  Observations: {len(observations)}")

    b = before_r2(observations)
    print("\n  BEFORE (leaky same-row features/labels, no embargo):")
    print(f"    density R2:        {b[0]:.4f}")
    print(f"    vehicle_count R2:  {b[1]:.4f}")

    score, detail, wf = after_metrics(observations)
    print("\n  AFTER (temporal pairing + horizon feature + embargo):")
    print(f"    density R2:        {detail['density']['r2']:.4f}  "
          f"(MAE {detail['density']['mae']:.4f})")
    print(f"    vehicle_count R2:  {detail['vehicle_count']['r2']:.4f}  "
          f"(MAE {detail['vehicle_count']['mae']:.4f})")
    print(f"    coarse (avg) R2:   {score:.4f}")
    print("\n  Walk-forward reliability (mean±std across folds):")
    if wf.get("folds"):
        print(f"    folds: {wf['folds']}")
        print(f"    density R2:       {wf['density_r2_mean']:.4f} ± {wf['density_r2_std']:.4f}")
        print(f"    vehicle_count R2: {wf['vehicle_count_r2_mean']:.4f} ± "
              f"{wf['vehicle_count_r2_std']:.4f}")
    else:
        print(f"    {wf}")
    print("=" * 64)
    print("  Expect AFTER density R2 to drop vs BEFORE — that drop is the")
    print("  leak closing, not a regression.\n")


if __name__ == "__main__":
    main()
