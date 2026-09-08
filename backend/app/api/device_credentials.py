from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.auth import require_admin
from app.db.session import get_db
from app.schemas import (
    DeviceCredentialCreate,
    DeviceCredentialCreateResponse,
    DeviceCredentialRead,
)
from uuid import UUID
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
    try:
        device, credential = DeviceCredentialService().create(
                db=db,
                name=payload.name,
                scopes=payload.scopes,
                intersection_id=payload.intersection_id,
            )
    except ValueError as exc:
        if str(exc) == "Intersection not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device credential name already exists",
        ) from exc

    return DeviceCredentialCreateResponse(
        device=DeviceCredentialRead.model_validate(device),
        credential=f"{device.credential_id}.{credential}",
    )

@router.patch(
    "/{device_id}/revoke",
    response_model=DeviceCredentialRead,
    dependencies=[Depends(require_admin)],
)
def revoke_device_credential(
    device_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return DeviceCredentialService().revoke(
            db=db,
            device_id=device_id,
        )
    except ValueError as exc:
        if str(exc) == "Device credential not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.get(
    "",
    response_model=list[DeviceCredentialRead],
    dependencies=[Depends(require_admin)],
)
def list_device_credentials(
    db: Session = Depends(get_db),
):
    return DeviceCredentialService().list(db)