# RoadMind Database Optimization

Date: 2026-05-30

## Goal

Phase 2 adds production-oriented PostgreSQL indexes and health checks without changing API contracts or table semantics. The optimization targets current repository query shapes and dashboard polling paths.

## Query Patterns Reviewed

| Repository | Query shape | Optimization |
| --- | --- | --- |
| `TrafficRepository.latest()` | Optional `intersection_id`, ordered by `captured_at DESC` | Existing intersection/time index plus global captured-at and direction/time indexes |
| `TrafficRepository.history()` | Ordered by `captured_at ASC`, optional since filter | Global captured-at index |
| `SignalRepository.latest()` | Optional `intersection_id`, ordered by `created_at DESC` | Existing `ix_signal_plans_intersection_created` bootstrap index |
| `PredictionRepository.latest()` | Optional `intersection_id`, ordered by `created_at DESC` | New prediction intersection/time index |
| `EmergencyRepository.active()` | `status='active'`, optional `intersection_id`, ordered by severity | Existing active emergency index |
| `EmergencyRepository.latest()` | Optional `intersection_id`, ordered by `detected_at DESC` | New emergency intersection/detected index |
| `EmergencyRepository.get_corridors()` | Filter by `emergency_id`, ordered by sequence | Existing emergency/sequence index |
| Future detection freshness | Filter by `intersection_id`, ordered by detection creation time | New detection intersection/time index |

## Added Indexes

Migration: `backend/alembic/versions/20260530_0004_add_production_indexes.py`

```sql
CREATE INDEX IF NOT EXISTS ix_traffic_observations_captured_at
    ON traffic_observations(captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_traffic_observations_intersection_direction_time
    ON traffic_observations(intersection_id, direction, captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_detection_events_intersection_created
    ON detection_events(intersection_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_predictions_intersection_created
    ON predictions(intersection_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_emergency_events_intersection_detected
    ON emergency_events(intersection_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS ix_emergency_corridors_intersection_status
    ON emergency_corridors(intersection_id, status);
```

The same indexes were added to `db/init/001_schema.sql` so fresh Docker databases and migrated databases stay aligned.

## Existing Useful Indexes

The bootstrap schema already includes:

- `ix_traffic_intersection_time` on `traffic_observations(intersection_id, captured_at DESC)`
- `ix_signal_plans_intersection_created` on `signal_plans(intersection_id, created_at DESC)`
- `ix_signal_phases_plan` on `signal_phases(plan_id, phase_order)`
- `ix_emergency_events_active` on `emergency_events(intersection_id, status, severity DESC)`
- `ix_corridors_emergency` on `emergency_corridors(emergency_id, sequence_order)`

## Health Checks

Added:

```text
GET /api/v1/health/db
```

The endpoint executes `SELECT 1` and checks whether the `alembic_version` table has a version row. This is intentionally lightweight and safe for load balancers or deployment smoke checks.

Response example:

```json
{
  "status": "ok",
  "migrations": "present",
  "alembic_version": "20260530_0004"
}
```

If the database responds but Alembic metadata is absent, `status` remains `ok` and `migrations` is reported as `missing`. Production startup enforcement is handled separately in Phase 3.

## Migration Validation

Operational validation after deploy:

```bash
cd backend
alembic upgrade head
alembic current
```

Runtime validation:

```bash
curl http://localhost:8000/api/v1/health/db
```

Expected production behavior after Phase 3:

- Production must run with `AUTO_CREATE_TABLES=false`.
- Production startup must fail if Alembic metadata is missing.
- Development may still use auto table creation for local convenience.
