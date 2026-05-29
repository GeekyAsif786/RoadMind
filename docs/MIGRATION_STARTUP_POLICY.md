# RoadMind Migration Startup Policy

Date: 2026-05-30

## Goal

Phase 3 removes the production anti-pattern of letting SQLAlchemy create or mutate schema implicitly at API startup. RoadMind now keeps development convenience while requiring Alembic-managed schema in production.

## Runtime Rules

### Development

Development may keep:

```env
ENVIRONMENT=development
AUTO_CREATE_TABLES=true
```

When this mode is enabled, `Base.metadata.create_all(...)` still runs for local convenience and startup logs a warning that the mode is development-only.

### Production

Production must use:

```env
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
```

If production starts with `AUTO_CREATE_TABLES=true`, startup fails immediately.

If production starts with missing or out-of-date Alembic metadata, startup fails immediately.

## Migration Validation

RoadMind compares:

- the database revision from `alembic_version`
- the code revision head from `backend/alembic`

The app treats the database as current only when both match.

## Operator Workflow

Before starting production API processes:

```bash
cd backend
alembic upgrade head
alembic current
```

Then start the API with production settings.

## Why This Matters

`create_all()` can create tables but cannot safely express reviewed schema changes, data migrations, index changes, constraint changes, or downgrades. Alembic keeps schema changes explicit, reviewable, and repeatable across environments.
