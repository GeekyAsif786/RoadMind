"""
Development-only sample data.

Alembic owns the schema; this module only inserts rows into tables that
migrations have already created. It never creates, alters, or drops schema,
and it refuses to run outside an explicitly allowed development environment.

Usage (inside the backend container, after ``alembic upgrade head``):

    python -m app.db.seed
"""

import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import String, column, exists, func, select, values
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.domain import Intersection

logger = logging.getLogger(__name__)

# Environments where sample data may be inserted. This is an allowlist:
# production, staging, and any unrecognised value are all refused.
SEED_ALLOWED_ENVIRONMENTS = frozenset({"development", "local"})

# Mirrors the sample row previously inserted by db/init/001_schema.sql.
DEV_INTERSECTIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "Central Avenue Junction",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "lanes": 4,
    },
)


def ensure_seed_allowed(settings: Settings) -> None:
    environment = settings.environment.strip().lower()
    if environment not in SEED_ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "Refusing to insert development seed data in "
            f"ENVIRONMENT={settings.environment!r}. Allowed: "
            f"{', '.join(sorted(SEED_ALLOWED_ENVIRONMENTS))}."
        )


def _names_already_present(db: Session, names: list[str]) -> set[str]:
    """Return the seed names that match an existing intersection, ignoring case."""
    candidates = values(column("name", String), name="seed_candidates").data(
        [(name,) for name in names]
    )
    statement = select(candidates.c.name).where(
        exists().where(func.lower(Intersection.name) == func.lower(candidates.c.name))
    )
    return set(db.scalars(statement))


def seed_development_data(
    db: Session,
    settings: Settings,
    intersections: Iterable[dict[str, Any]] = DEV_INTERSECTIONS,
) -> int:
    """
    Insert sample intersections that do not already exist.

    Idempotent: a seed row is skipped when an intersection with the same name
    already exists, compared case-insensitively. Exact-name races are also
    caught by ``ON CONFLICT DO NOTHING`` on the unique ``intersections.name``.
    Existing rows are never updated, so their ids and every row referencing
    them are preserved.

    Returns the number of intersections inserted.
    """
    ensure_seed_allowed(settings)

    rows = list(intersections)
    if not rows:
        return 0

    present = _names_already_present(db, [row["name"] for row in rows])
    rows = [row for row in rows if row["name"] not in present]
    if not rows:
        db.commit()
        return 0

    statement = (
        insert(Intersection)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[Intersection.name])
        .returning(Intersection.id)
    )
    inserted = len(db.execute(statement).all())
    db.commit()
    return inserted


def main() -> None:
    from app.core.config import get_settings
    from app.core.startup import get_migration_status
    from app.db.session import SessionLocal, engine

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    ensure_seed_allowed(settings)

    migration_status = get_migration_status(engine)
    if migration_status["status"] != "current":
        raise RuntimeError(
            "Refusing to seed: database migrations are not current "
            f"(database={migration_status['database_revision'] or 'missing'}, "
            f"head={migration_status['head_revision'] or 'unknown'}). "
            "Run 'alembic upgrade head' first."
        )

    db = SessionLocal()
    try:
        inserted = seed_development_data(db, settings)
    finally:
        db.close()

    logger.info("Development seed complete: %d intersection(s) inserted.", inserted)


if __name__ == "__main__":
    main()
