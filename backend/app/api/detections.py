from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import DetectionRead
from app.services.detection_service import DetectionService

router = APIRouter()


@router.post("/image", response_model=DetectionRead)
async def detect_from_image(
    file: UploadFile = File(...),
    intersection_id: UUID | None = None,
    persist_observation: bool = True,
    db: Session = Depends(get_db),
):
    return DetectionService(db).detect(
        await file.read(),
        intersection_id=intersection_id,
        persist_observation=persist_observation,
    )
