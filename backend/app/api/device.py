from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_device_scope
from app.db.session import get_db
from app.models.domain import DeviceCredential
from app.schemas import PredictionRead, SignalStateRead
from app.services.prediction_service import PredictionService
from app.services.signal_state_service import SignalStateService

router = APIRouter()

require_prediction_read = require_device_scope("prediction:read")


@router.get(
    "/predictions/latest",
    response_model=list[PredictionRead],
)
def get_latest_device_predictions(
    device: DeviceCredential = Depends(require_prediction_read),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return PredictionService(db).latest(
        intersection_id=device.intersection_id,
        limit=10,
    )

@router.get(
    "/signals/state",
    response_model=SignalStateRead,
)
def get_device_signal_state(
    device: DeviceCredential = Depends(
        require_device_scope("signal:state:read")
    ),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return SignalStateService(db).get(device.intersection_id)