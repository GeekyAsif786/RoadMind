import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from app.core.config import Settings
from app.db.base import Base

logger = logging.getLogger(__name__)


def prepare_database(engine: Engine, settings: Settings) -> None:
    """
    Keep local development ergonomic while making production schema management Alembic-only.
    Production must never rely on SQLAlchemy create_all because it bypasses migration review.
    """
    is_production = settings.environment.lower() == "production"
    if is_production and settings.auto_create_tables:
        raise RuntimeError("AUTO_CREATE_TABLES must be false in production; run Alembic migrations instead.")

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        logger.warning("AUTO_CREATE_TABLES is enabled; this mode is intended for development only.")
        return

    migration_status = get_migration_status(engine)
    if is_production and migration_status["status"] != "current":
        raise RuntimeError(
            "Database migrations are not current: "
            f"database={migration_status['database_revision'] or 'missing'}, "
            f"head={migration_status['head_revision'] or 'unknown'}."
        )

    if migration_status["status"] != "current":
        logger.warning(
            "Database migrations are not current: database=%s, head=%s",
            migration_status["database_revision"] or "missing",
            migration_status["head_revision"] or "unknown",
        )


def get_migration_status(engine: Engine) -> dict[str, str]:
    head_revision = _get_alembic_head_revision()
    database_revision = _get_database_revision(engine)
    status = "current" if database_revision and database_revision == head_revision else "out_of_date"
    return {
        "status": status,
        "database_revision": database_revision or "",
        "head_revision": head_revision or "",
    }


def _get_database_revision(engine: Engine) -> str | None:
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        return None
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()


def _get_alembic_head_revision() -> str | None:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
    return ScriptDirectory.from_config(alembic_config).get_current_head()
