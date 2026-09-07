from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.schemas import (
    DeviceCredentialCreate,
    DeviceCredentialCreateResponse,
    DeviceCredentialRead,
)
from app.services.device_credential_service import DeviceCredentialService

router = APIRouter()


@router.post(
    "",
    response_model=DeviceCredentialCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_device_credential(
    payload: DeviceCredentialCreate,
    db: Session = Depends(get_db),
):
    device, credential = DeviceCredentialService().create(
        db=db,
        name=payload.name,
        scopes=payload.scopes,
        intersection_id=payload.intersection_id,
    )

    return DeviceCredentialCreateResponse(
        device=DeviceCredentialRead.model_validate(device),
        credential=f"{device.credential_id}.{credential}",
    )