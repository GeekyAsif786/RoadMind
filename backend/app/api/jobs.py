from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.jobs import get_job_queue
from app.schemas import JobStatusRead

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusRead, dependencies=[Depends(require_api_key)])
def get_job_status(job_id: str):
    return get_job_queue().status(job_id)
