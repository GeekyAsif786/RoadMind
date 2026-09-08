from unittest.mock import Mock
from uuid import uuid4

from app.services.prediction_service import PredictionService


def test_latest_predictions_delegates_to_repository():
    db = Mock()
    service = PredictionService(db)

    intersection_id = uuid4()
    expected = [Mock(), Mock()]

    service.predictions.latest = Mock(return_value=expected)

    result = service.latest(
        intersection_id=intersection_id,
        limit=5,
    )

    assert result == expected
    service.predictions.latest.assert_called_once_with(
        intersection_id=intersection_id,
        limit=5,
    )