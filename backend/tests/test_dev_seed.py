from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.db import seed
from app.db.seed import DEV_INTERSECTIONS, seed_development_data
from app.db.session import SessionLocal
from app.models import Intersection, TrafficObservation


def _settings(environment: str) -> Settings:
    return Settings(environment=environment)


def _sample(name: str, **overrides) -> dict:
    row = {"name": name, "latitude": 28.6139, "longitude": 77.2090, "lanes": 4}
    row.update(overrides)
    return row


@pytest.fixture
def db():
    session = SessionLocal()
    names: list[str] = []
    try:
        yield session, names
    finally:
        session.rollback()
        if names:
            session.execute(delete(Intersection).where(Intersection.name.in_(names)))
            session.commit()
        session.close()


def _count(session, name: str) -> int:
    return session.scalar(
        select(func.count()).select_from(Intersection).where(Intersection.name == name)
    )


def test_default_seed_matches_legacy_init_sql():
    assert DEV_INTERSECTIONS == (
        {
            "name": "Central Avenue Junction",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "lanes": 4,
        },
    )


def test_seed_is_idempotent(db):
    session, names = db
    name = f"seed-test-{uuid4().hex}"
    names.append(name)
    rows = [_sample(name)]

    assert seed_development_data(session, _settings("development"), rows) == 1
    assert seed_development_data(session, _settings("development"), rows) == 0
    assert seed_development_data(session, _settings("development"), rows) == 0

    assert _count(session, name) == 1


def test_seed_preserves_existing_intersection_and_relationships(db):
    session, names = db
    name = f"seed-test-{uuid4().hex}"
    names.append(name)

    existing = Intersection(name=name, latitude=1.0, longitude=2.0, lanes=2)
    session.add(existing)
    session.flush()
    session.add(
        TrafficObservation(intersection_id=existing.id, vehicle_count=12, density=0.4)
    )
    session.commit()
    existing_id = existing.id

    inserted = seed_development_data(
        session, _settings("development"), [_sample(name, lanes=6)]
    )
    assert inserted == 0

    session.expire_all()
    row = session.scalar(select(Intersection).where(Intersection.name == name))
    assert row.id == existing_id
    assert (row.latitude, row.longitude, row.lanes) == (1.0, 2.0, 2)
    observation_count = session.scalar(
        select(func.count())
        .select_from(TrafficObservation)
        .where(TrafficObservation.intersection_id == existing_id)
    )
    assert observation_count == 1


def _count_case_insensitive(session, name: str) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Intersection)
        .where(func.lower(Intersection.name) == func.lower(name))
    )


@pytest.mark.parametrize(
    ("existing_case", "seed_case"),
    [
        (str.lower, str.upper),
        (str.upper, str.lower),
        (str.lower, str.title),
    ],
    ids=["existing-lower/seed-upper", "existing-upper/seed-lower", "existing-lower/seed-title"],
)
def test_seed_skips_existing_name_with_different_capitalization(db, existing_case, seed_case):
    session, names = db
    base = f"seed-test-{uuid4().hex} junction"
    existing_name = existing_case(base)
    seed_name = seed_case(base)
    missing_name = f"seed-test-{uuid4().hex}"
    assert existing_name != seed_name
    names.extend([existing_name, seed_name, missing_name])

    existing = Intersection(name=existing_name, latitude=1.0, longitude=2.0, lanes=2)
    session.add(existing)
    session.flush()
    session.add(
        TrafficObservation(intersection_id=existing.id, vehicle_count=7, density=0.2)
    )
    session.commit()
    existing_id = existing.id

    inserted = seed_development_data(
        session,
        _settings("development"),
        [_sample(seed_name, lanes=6), _sample(missing_name)],
    )

    assert inserted == 1
    assert _count_case_insensitive(session, base) == 1
    assert _count(session, seed_name) == 0
    assert _count(session, missing_name) == 1

    session.expire_all()
    row = session.scalar(select(Intersection).where(Intersection.id == existing_id))
    assert row.name == existing_name
    assert (row.latitude, row.longitude, row.lanes) == (1.0, 2.0, 2)
    observation_count = session.scalar(
        select(func.count())
        .select_from(TrafficObservation)
        .where(TrafficObservation.intersection_id == existing_id)
    )
    assert observation_count == 1


def test_seed_inserts_only_missing_rows(db):
    session, names = db
    present = f"seed-test-{uuid4().hex}"
    missing = f"seed-test-{uuid4().hex}"
    names.extend([present, missing])

    seed_development_data(session, _settings("development"), [_sample(present)])
    inserted = seed_development_data(
        session, _settings("development"), [_sample(present), _sample(missing)]
    )

    assert inserted == 1
    assert _count(session, present) == 1
    assert _count(session, missing) == 1


@pytest.mark.parametrize("environment", ["production", "Production", " PRODUCTION ", "staging", ""])
def test_seed_refused_outside_development(environment):
    session = MagicMock()

    with pytest.raises(RuntimeError, match="Refusing to insert development seed data"):
        seed_development_data(session, _settings(environment), [_sample("never-inserted")])

    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_seed_refused_in_production_leaves_database_unchanged(db):
    session, names = db
    name = f"seed-test-{uuid4().hex}"
    names.append(name)

    with pytest.raises(RuntimeError):
        seed_development_data(session, _settings("production"), [_sample(name)])

    assert _count(session, name) == 0


@pytest.mark.parametrize("environment", ["development", "local", "DEVELOPMENT"])
def test_seed_allowed_in_development_environments(environment):
    seed.ensure_seed_allowed(_settings(environment))


def test_main_refuses_production_before_touching_database(monkeypatch):
    import app.core.config as config
    import app.core.startup as startup

    monkeypatch.setattr(config, "get_settings", lambda: _settings("production"))
    migration_status = MagicMock()
    monkeypatch.setattr(startup, "get_migration_status", migration_status)

    with pytest.raises(RuntimeError, match="Refusing to insert development seed data"):
        seed.main()

    migration_status.assert_not_called()


def test_main_refuses_when_migrations_not_current(monkeypatch):
    import app.core.config as config
    import app.core.startup as startup

    monkeypatch.setattr(config, "get_settings", lambda: _settings("development"))
    monkeypatch.setattr(
        startup,
        "get_migration_status",
        lambda engine: {
            "status": "out_of_date",
            "database_revision": "",
            "head_revision": "e5c1e605dfd1",
        },
    )
    seeder = MagicMock()
    monkeypatch.setattr(seed, "seed_development_data", seeder)

    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        seed.main()

    seeder.assert_not_called()
