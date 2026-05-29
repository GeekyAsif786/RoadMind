from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import DetectionQueueStatus, DetectionRead
from app.services.detection_queue_service import detection_queue
from app.services.detection_service import DetectionService

router = APIRouter()


@router.post("/image", response_model=DetectionRead, dependencies=[Depends(require_api_key)])
async def detect_from_image(
    file: UploadFile = File(...),
    intersection_id: UUID | None = None,
    persist_observation: bool = True,
    content_length: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only image uploads are supported")
    if content_length is not None and content_length > settings.upload_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Uploaded image is too large")
    image_bytes = await file.read()
    if len(image_bytes) > settings.upload_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Uploaded image is too large")
    return DetectionService(db).detect(
        image_bytes,
        intersection_id=intersection_id,
        persist_observation=persist_observation,
    )


@router.get("/queue/status", response_model=DetectionQueueStatus)
def detection_queue_status():
    return detection_queue.status()
