# ML Pipeline

RoadMind uses XGBoost as the preferred predictor and keeps RandomForest as the guaranteed fallback.

Key concepts:

- `BaseTrafficPredictor`: shared training, feature engineering, persistence, and prediction contract.
- `XGBoostPredictor`: first-priority model selected with `TRAFFIC_MODEL=xgboost`.
- `RandomForestPredictor`: fallback model when XGBoost is unavailable or selected explicitly.
- Training sample floor: training still requires at least 200 observations.
- Evaluation metrics: MAE, RMSE, and R2 are written to `runtime_models` and persisted in `model_evaluations`.

Configuration:

```env
TRAFFIC_MODEL=xgboost
```

To force RandomForest:

```env
TRAFFIC_MODEL=random_forest
```

There is no separate `BestTraffic` model class. The "best traffic model" behavior is the strategy selection policy: try XGBoost first, then fall back to RandomForest.
