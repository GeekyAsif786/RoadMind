from unittest.mock import patch
from uuid import uuid4
from unittest.mock import Mock

from app.api.predictions import get_latest_predictions
from app.models import Prediction


def test_get_latest_predictions_returns_latest_predictions():
    intersection_id = uuid4()

    predictions = [
        Prediction(
            intersection_id=intersection_id,
            horizon_minutes=15,
            predicted_density=42.5,
            predicted_vehicle_count=120,
            model_version="xgboost-test",
        )
    ]

    db = Mock()

    with patch("app.api.predictions.PredictionService") as service_class:
        service_class.return_value.latest.return_value = predictions

        result = get_latest_predictions(
            intersection_id=intersection_id,
            limit=10,
            db=db,
        )

    assert result == predictions
    service_class.assert_called_once_with(db)
    service_class.return_value.latest.assert_called_once_with(
        intersection_id=intersection_id,
        limit=10,
    )