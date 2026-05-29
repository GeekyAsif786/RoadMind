# RoadMind Production Audit

Date: 2026-05-30

## Scope

This audit covers the current RoadMind codebase before Phase 2-4 hardening work:

- `backend/app/api`
- `backend/app/services`
- `backend/app/repositories`
- `backend/app/models`
- `backend/app/ml`
- `backend/app/vision`
- `backend/app/core`
- `frontend/src`
- `db/init`, `db/seeds`, and Alembic migrations

No code changes were made as part of this phase.

## Architecture Summary

RoadMind uses a conventional FastAPI service boundary:

```text
API route -> Service -> Repository -> SQLAlchemy ORM -> PostgreSQL
```

The frontend is a Vite React operations dashboard that calls REST endpoints under `/api/v1`. The backend stores intersections, traffic observations, detection events, signal plans, signal phases, predictions, emergency events, and emergency corridors. Vision is synchronous per request. Prediction is synchronous RandomForest training/inference using persisted joblib artifacts.

## High Priority Findings

### 1. Production startup can create tables automatically

`backend/app/main.py` calls `Base.metadata.create_all(bind=engine)` whenever `auto_create_tables` is true. This is convenient for local development but unsafe in production because schema drift can occur outside Alembic and operators may not notice missing migrations.

Recommendation: keep `auto_create_tables=true` for development only, enforce `auto_create_tables=false` in production, and validate Alembic state at startup.

### 2. Synchronous model training blocks API workers

`PredictionService.train()` calls `TrafficPredictor.train()` directly in the request path. RandomForest training can block a Uvicorn worker as data grows.

Recommendation: defer full background job architecture to Phase 5, but document the current operational risk.

### 3. Synchronous image detection blocks API workers

`DetectionService.detect()` decodes images and runs OpenCV or YOLO in the request path. YOLO inference is CPU/GPU heavy and can block traffic API capacity.

Recommendation: defer queue/worker design to Phase 7, but cap upload sizes and add queueing later.

### 4. Redis/cache layer is absent

Dashboard summary repeatedly queries latest observations, signal plans, emergencies, predictions, and intersection counts. This is acceptable locally but unnecessary under operator dashboard polling.

Recommendation: add cache-aside Redis support with graceful fallback and short TTLs for latest state.

### 5. Some read paths need composite indexes

Several repositories query by `intersection_id` and sort by timestamp or status. SQL bootstrap has some indexes, but ORM/Alembic coverage is incomplete for predictions, detections, emergency corridors, and active emergency lookups.

Recommendation: add idempotent Alembic indexes aligned to repository query shapes.

## Scalability Issues

- Dashboard polling fans out to five repository calls for every refresh.
- `TrafficRepository.history()` loads all observations for model training; large datasets will require pagination/windowing or worker processing.
- Detection and prediction share the API process instead of worker isolation.
- `IntersectionEncoder` writes a JSON file from model code and is not process-safe under concurrent training.
- The frontend dashboard refreshes every 15 seconds and does not use conditional requests or server-side aggregation caching.

## Performance Bottlenecks

- `DashboardService.summary()` performs multiple latest queries and an active emergency query per request.
- `EmergencyRepository.active()` sorts by severity and filters by status, which benefits from a composite status/intersection/severity index.
- `PredictionRepository.latest()` sorts by `created_at`; this needs an intersection/timestamp index for dashboard use.
- `DetectionRepository` has no read methods today, but future latest detection/freshness logic needs an intersection/timestamp index.
- Signal phase creation currently commits separately after plan creation; this is safe but not atomic across plan and phases.

## Security Issues

- Auth is disabled by default through `ENABLE_AUTH=false`, including in Docker development settings.
- CORS allows local dev origins only, but production CORS policy must be explicit.
- Image upload endpoints accept multipart files without explicit file size enforcement.
- API key comparison is plain equality and lacks rotation/audit behavior.
- No request-rate limiting exists for uploads or mutation endpoints.

## Code Smells

- `create_all()` startup behavior blurs development and production schema management.
- Services sometimes commit through repositories and sometimes directly through `self.db`, e.g. emergency corridor creation.
- `EmergencyService.create_corridor()` creates corridor rows and also triggers optimization, mixing persistence and orchestration in a single loop.
- ML training raises `HTTPException` from the ML module, coupling model code to FastAPI.
- `TrafficPredictor` feature ordering is implicit and not versioned with the model artifact.

## N+1 Query Risks

- `SignalPlan.phases` is returned in `SignalPlanRead`; depending on SQLAlchemy loader behavior and response serialization, dashboard summary can trigger one query per plan for phases.
- Emergency corridors validate each intersection one by one in `EmergencyService.create_corridor()`.
- Dashboard summary currently performs predictable fan-out queries; not N+1 for simple latest lists, but phase serialization can become N+1.

Recommendation: use `selectinload()` for signal phases in latest-plan queries and batch intersection validation when corridor scale grows.

## Blocking I/O Issues

- OpenCV/YOLO runs in request flow.
- RandomForest training runs in request flow.
- `joblib.dump()` and model artifact reads/writes run in request flow.
- `IntersectionEncoder` writes JSON mapping synchronously while building features.

## Missing Indexes

Recommended additional indexes:

- `traffic_observations(intersection_id, direction, captured_at DESC)` for directional volume windows.
- `traffic_observations(captured_at DESC)` for global history/latest operations.
- `signal_plans(intersection_id, created_at DESC)` for latest plans.
- `predictions(intersection_id, created_at DESC)` for latest predictions.
- `detection_events(intersection_id, created_at DESC)` for future detection freshness.
- `emergency_events(status, intersection_id, severity DESC)` for active-emergency lookup.
- `emergency_events(intersection_id, detected_at DESC)` for latest emergency feed.
- `emergency_corridors(emergency_id, sequence_order)` for corridor retrieval.
- `emergency_corridors(intersection_id, status)` for active corridor inspection.

## Race Conditions And Thread Safety

- Concurrent training can overwrite the same model artifact and encoder JSON files.
- Multiple emergency events for the same intersection are partially serialized by clearing active events before insert, but no database lock or unique active constraint prevents concurrent creates.
- `flush_emergency_corridor()` creates downstream plans after primary plan creation; partial success can leave a mixed corridor state if later inserts fail.
- Cache invalidation will need to be explicit after writes once Redis is introduced.

## Frontend Findings

- The dashboard depends on periodic polling and does not distinguish stale cached data from live data.
- Operator feedback now exists for actions, but no global request-id or trace correlation is surfaced.
- The PCU calculator improves manual workflow but derived PCU values are only applied when the operator clicks a target action.

## Phase 2-4 Recommendations

1. Add idempotent Alembic indexes for current read paths.
2. Add database health endpoints that execute a trivial query.
3. Enforce Alembic-managed schema in production startup.
4. Add Redis cache-aside helpers with short TTLs and no hard dependency on Redis availability.
5. Cache latest dashboard-oriented state and invalidate after writes.

## Deferred To Phases 5-12

- Background jobs for training/detection/analytics.
- Pluggable model architecture.
- Detection queue and real-time fallback hierarchy.
- Prometheus metrics.
- Security headers, upload limits, and rate limiting.
- Emergency corridor conflict handling.
- Performance benchmark suite.
- Production deployment profile.
