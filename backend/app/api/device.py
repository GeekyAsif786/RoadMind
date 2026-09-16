from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.auth import require_device_scope
from app.db.session import get_db
from app.models.domain import DeviceCredential
from app.schemas import (
    PredictionRead,
    SignalControllerStateCreate,
    SignalControllerStateRead,
    SignalControlCommand,
    SignalControlCommandRead,
    SignalStateRead,
)
from app.services.prediction_service import PredictionService
from app.services.signal_controller_state_service import (
    SignalControllerStateService,
)
from app.services.signal_control_service import SignalControlService
from app.services.signal_control_ack_service import SignalControlAckService
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
@router.post(
    "/heartbeat",
    response_model=SignalControllerStateRead,
    status_code=status.HTTP_200_OK,
)
def device_heartbeat(
    payload: SignalControllerStateCreate,
    device: DeviceCredential = Depends(
        require_device_scope("signal:state:write")
    ),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return SignalControllerStateService(db).update(
        intersection_id=device.intersection_id,
        payload=payload,
    )
@router.post(
    "/signals/state",
    response_model=SignalControllerStateRead,
    status_code=status.HTTP_201_CREATED,
)
def report_device_signal_state(
    payload: SignalControllerStateCreate,
    device: DeviceCredential = Depends(
        require_device_scope("signal:state:write")
    ),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )
    return SignalControllerStateService(db).update(
        intersection_id=device.intersection_id,
        payload=payload,
    )

@router.post(
    "/signals/control",
    response_model=SignalControlCommandRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device_signal_control(
    payload: SignalControlCommand,
    device: DeviceCredential = Depends(
        require_device_scope("signal:control")
    ),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return SignalControlService(db).create_command(
        device_id=device.id,
        intersection_id=device.intersection_id,
        payload=payload,
    )

@router.post(
    "/signals/control/{command_id}/acknowledge",
    response_model=SignalControlCommandRead,
)
def acknowledge_device_signal_control(
    command_id: UUID,
    device: DeviceCredential = Depends(
        require_device_scope("signal:control")
    ),
    db: Session = Depends(get_db),
):
    return SignalControlAckService(db).acknowledge(
        command_id=command_id,
        device_id=device.id,
    )

@router.post(
    "/signals/control/{command_id}/execution",
    response_model=SignalControllerStateRead,
    status_code=status.HTTP_200_OK,
)
def report_device_signal_control_execution(
    command_id: UUID,
    payload: SignalControllerStateCreate,
    device: DeviceCredential = Depends(
        require_device_scope("signal:control")
    ),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return SignalControllerStateService(db).report_command_execution(
        command_id=command_id,
        device_id=device.id,
        intersection_id=device.intersection_id,
        payload=payload,
    )

@router.get(
    "/signals/control/pending",
    response_model=list[SignalControlCommandRead],
)
def get_pending_device_signal_controls(
    device: DeviceCredential = Depends(require_device_scope("signal:control")),
    db: Session = Depends(get_db),
):
    if device.intersection_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not bound to an intersection",
        )

    return SignalControlService(db).pending_commands(
        device_id=device.id,
        limit=10,
    )