# ML Pipeline

RoadMind keeps RandomForest as the default predictor and adds a strategy wrapper for future models.

Key concepts:

- `BaseTrafficPredictor`: shared training, feature engineering, persistence, and prediction contract.
- `RandomForestPredictor`: default production-safe model.
- `XGBoostPredictor`: optional strategy selected with `TRAFFIC_MODEL=xgboost`; it automatically falls back to RandomForest if `xgboost` is not installed.
- Training sample floor: training still requires at least 200 observations.
- Evaluation metrics: MAE, RMSE, and R2 are written to `runtime_models` and persisted in `model_evaluations`.

Configuration:

```env
TRAFFIC_MODEL=random_forest
```

or:

```env
TRAFFIC_MODEL=xgboost
```
