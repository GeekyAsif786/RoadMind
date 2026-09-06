from uuid import UUID
from app.core.auth import require_authenticated_user

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth import require_authenticated_user
from app.schemas import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get(
    "/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(require_authenticated_user)],
)
def dashboard_summary(intersection_id: UUID | None = None, db: Session = Depends(get_db)):
    return DashboardService(db).summary(intersection_id=intersection_id)
