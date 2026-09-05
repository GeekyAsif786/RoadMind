# ML Pipeline

RoadMind forecasts short-horizon traffic density and vehicle count. The pipeline
is built to avoid feature/label leakage and to report trustworthy metrics.

## Model selection

- `BaseTrafficPredictor`: shared feature engineering, pairing, training,
  persistence, and inference contract.
- `XGBoostPredictor`: first-priority model selected with `TRAFFIC_MODEL=xgboost`.
- `RandomForestPredictor`: fallback when XGBoost is unavailable or selected
  explicitly with `TRAFFIC_MODEL=random_forest`.

There is no separate "best" model class; "best" is the strategy policy — try
XGBoost first, fall back to RandomForest.

```env
TRAFFIC_MODEL=xgboost      # or random_forest
```

## Temporal pairing (no same-row leakage)

Training examples are built with **explicit temporal pairing** instead of using
one observation row as both feature source and label source:

- Per intersection, observations are sorted by `captured_at`.
- Each observation (`current_obs`, time `t`) is matched — for each horizon in
  `{5, 15, 30, 60}` minutes — to a **later** observation from the **same
  intersection** whose timestamp is closest to `t + horizon`, within a ~3-minute
  tolerance window.
- If no observation falls inside the tolerance window, the pair is skipped. No
  interpolation or guessing.
- Output: `(current_obs, future_obs, horizon_minutes)` tuples where features come
  from `current_obs` and the label (`density`, `vehicle_count`) comes from
  `future_obs`. The two are never the same row.

`horizon_minutes` is a first-class feature, so a 5-minute and a 60-minute
forecast for the same current state produce **different** inputs and predictions.

## Feature engineering

Features are produced as a **named dict** and then vectorized against a
persisted, sorted schema (`<model_key>.feature_names.json`). On model load, the
current code's feature names are asserted equal to the persisted list; a mismatch
raises `FeatureSchemaMismatchError` to prevent silent feature-order drift between
training and inference.

- **Hour-of-day / day-of-week**: sin/cos cyclic encoding (not raw integers).
- **Weather / direction**: one-hot over fixed, known category sets.
- **Intersection**: label-encoded integer (its cardinality grows over time, so
  one-hotting it would break saved-model feature shape).
- **avg_speed / pcu_total**: split into a `*_missing` indicator (1.0/0.0) plus a
  value column that imputes with a real fallback (median historical `avg_speed`;
  `vehicle_count` for missing `pcu_total`) — never `0.0`, because `0` has real
  domain meaning (0 km/h = gridlock).
- **current_density**: kept, but always sourced from `current_obs` (time `t`),
  never from the label row.
- **horizon_minutes**: taken from the pairing step.

## Embargo gap

Evaluation replaces the old single 75/25 chronological split with an **embargo
gap**. After sorting pairs by `current_obs.captured_at` and choosing the
train/test boundary, any pair whose `current_obs` **or** `future_obs` timestamp
falls within `embargo_minutes` (default: max horizon = 60) of the boundary on
either side is dropped. This prevents test-set future values from having been
used as training labels for boundary-adjacent pairs.

## Walk-forward validation (reliability) vs deployed model

- `walk_forward_validation()` runs N sequential **expanding-window** folds
  (embargoed test window each fold) and reports **mean ± std** of per-target
  R²/MAE/RMSE. This is a **reliability check only** — it is logged and returned
  from `train()` but does **not** pick the deployed model.
- The **deployed model** is a single fit on all available pairs outside the last
  embargo window.

## Per-target metrics

Metrics are computed **per target** with
`multioutput="raw_values"` so density (range `[0, 1]`) and vehicle_count
(tens-to-hundreds) do not get mixed into one number where the larger-scale
target dominates.

- Per-target and walk-forward summaries are stored in the nullable
  `model_evaluations.metrics_detail` JSON column.
- The coarse `mae` / `rmse` / `r2` columns are retained as summary fields (the
  mean of the per-target values) for backward compatibility with existing
  API/UI consumers.

## Training-sample floor

Embargo purging reduces the number of usable pairs, so the raw-observation floor
was raised from the old naive `200` to **`600`**. Rationale: keeping at least
~150 usable pairs per fold across 5 walk-forward folds needs roughly
`(5 + 1) * 150 = 900` usable pairs after purging; at ~1.5 usable pairs per
observation that is ~600 observations. See `MIN_TRAINING_SAMPLES` in
`app/ml/traffic_predictor.py`.

## Before/after the leakage fix

On synthetic multi-hour, multi-intersection data, the old same-row pipeline
reported an inflated R² near `1.0` (the model trivially learned `f(x) ≈ x` for
the density column that appeared on both sides). The fixed pipeline reports a
realistic R² (~0.5–0.6 on that fixture). The drop is the leak closing, not a
regression. See `backend/tests/accuracy_report.py` for the before/after
harness and `backend/tests/test_ml_leakage.py` for the leakage guards.
