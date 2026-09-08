from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.api.device import get_latest_device_predictions
from app.models.domain import DeviceCredential


def test_device_prediction_read_uses_device_intersection():
    intersection_id = uuid4()

    device = Mock(spec=DeviceCredential)
    device.intersection_id = intersection_id

    db = Mock()
    predictions = [Mock(), Mock()]

    with patch("app.api.device.PredictionService") as service_class:
        service_class.return_value.latest.return_value = predictions

        result = get_latest_device_predictions(
            device=device,
            db=db,
        )

    assert result == predictions
    service_class.assert_called_once_with(db)
    service_class.return_value.latest.assert_called_once_with(
        intersection_id=intersection_id,
        limit=10,
    )

def test_device_prediction_read_rejects_unbound_device():
    device = Mock(spec=DeviceCredential)
    device.intersection_id = None

    db = Mock()

    with pytest.raises(HTTPException) as exc:
        get_latest_device_predictions(
            device=device,
            db=db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Device is not bound to an intersection"