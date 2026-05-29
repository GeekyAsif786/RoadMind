from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        try:
            alembic_version = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
        except SQLAlchemyError:
            alembic_version = None
        return {
            "status": "ok",
            "migrations": "present" if alembic_version else "missing",
            "alembic_version": alembic_version or "",
        }
    except SQLAlchemyError as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health/cache")
def cache_health_check() -> dict[str, str]:
    return get_cache().health()
