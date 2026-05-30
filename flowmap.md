# RoadMind Flow Map

This document maps the main program flow and event architecture from the operator dashboard down to storage, cache, queues, workers, ML, vision, and signal optimization.

## 1. Top-Level Runtime

```text
Operator Browser
  |
  v
Frontend: React/Vite dashboard
  |
  | REST calls under /api/v1
  v
Backend: FastAPI
  |
  +--> PostgreSQL: durable source of truth
  +--> Redis: cache and RQ queue backend
  +--> RQ Worker: background jobs
  +--> ML artifacts: persisted model files
```

Main containers:

```text
frontend
backend
worker
postgres
redis
pgadmin
```

The backend remains the orchestration point. PostgreSQL owns durable state. Redis improves speed and supports job dispatch, but the app is designed to continue in degraded mode if Redis is unavailable.

## 2. Backend Request Flow

```text
HTTP Request
  |
  v
FastAPI app middleware
  |
  +--> rate limit check
  +--> request id header
  +--> security headers
  +--> API latency metric
  |
  v
API router
  |
  v
Route module
  |
  v
Service layer
  |
  +--> Repository layer
  |     |
  |     v
  |   PostgreSQL
  |
  +--> Cache layer
  |     |
  |     v
  |   Redis
  |
  +--> ML / Optimization / Vision logic
```

Important files:

```text
backend/app/main.py
backend/app/api/
backend/app/services/
backend/app/repositories/
backend/app/models/domain.py
backend/app/core/cache.py
backend/app/core/jobs.py
backend/app/core/metrics.py
```

## 3. Cache-Aside Flow

Read path:

```text
API request
  |
  v
Check Redis key
  |
  +--> cache hit: return cached JSON
  |
  +--> cache miss
        |
        v
      Query PostgreSQL
        |
        v
      Serialize response
        |
        v
      Store in Redis with TTL
        |
        v
      Return response
```

Write path:

```text
Mutation request
  |
  v
Write PostgreSQL
  |
  v
Invalidate affected Redis key prefixes
  |
  v
Return durable result
```

Common key prefixes:

```text
dashboard:summary:...
traffic:latest:...
signal_plans:latest:...
emergencies:active:...
emergency_corridors:...
intersections:list
intersections:<id>
signal_state:<intersection_id>
```

Redis is an acceleration layer, not the source of truth.

## 4. Background Job Flow

Training is asynchronous so API requests do not block while the model trains.

```text
Frontend Train button
  |
  v
POST /api/v1/predictions/train
  |
  v
Backend enqueues train_traffic_model_task
  |
  v
Redis RQ queue: roadmind
  |
  v
worker container
  |
  v
PredictionService.train()
  |
  +--> load traffic history from PostgreSQL
  +--> require at least 200 samples
  +--> train configured predictor
  +--> persist model artifact
  +--> persist model evaluation metrics
  |
  v
Job result stored
  |
  v
Frontend polls GET /api/v1/jobs/{job_id}
  |
  v
Toast shows success only after job status is finished
```

If Redis/RQ is unavailable, `JobQueue` falls back to a local in-process executor. That fallback keeps development usable, but production should run the dedicated worker service.

## 5. ML Model Selection Flow

```text
PredictionService
  |
  v
TrafficPredictor
  |
  v
Read TRAFFIC_MODEL
  |
  +--> xgboost
  |     |
  |     v
  |   Try XGBoostPredictor
  |     |
  |     +--> available: train/predict with XGBoost
  |     |
  |     +--> unavailable or native load failure
  |           |
  |           v
  |         fall back to RandomForestPredictor
  |
  +--> random_forest
        |
        v
      Use RandomForestPredictor directly
```

Current default:

```text
TRAFFIC_MODEL=xgboost
```

Model version prefixes:

```text
xgb-...  XGBoost was used
rf-...   RandomForest was used or fallback occurred
```

## 6. Prediction Flow

```text
Frontend Prediction form
  |
  v
POST /api/v1/predictions
  |
  v
PredictionService.predict()
  |
  +--> load intersection
  +--> load latest observation
  +--> build model features
  +--> load trained model artifact
  +--> predict density and vehicle count
  +--> store Prediction row
  +--> invalidate dashboard/prediction cache
  |
  v
Return prediction to frontend
```

Prediction inputs include:

```text
intersection_id
horizon_minutes
direction
weather_condition
pcu_total
hour_of_day
day_of_week
```

## 7. Traffic Observation Flow

```text
Frontend Traffic Log form
  |
  v
POST /api/v1/traffic/observations
  |
  v
TrafficService.create_observation()
  |
  +--> validate intersection exists
  +--> calculate density if not provided
  +--> store TrafficObservation
  +--> update last-known signal state
  +--> invalidate traffic/dashboard cache
  |
  v
Return saved observation
```

The observation table is the main historical input for training, prediction fallback, dashboard summaries, and optimizer decisions.

## 8. Vision Detection Flow

Synchronous image upload path:

```text
Frontend image upload
  |
  v
POST /api/v1/detections/image
  |
  v
DetectionService.detect()
  |
  +--> validate file size and image type
  +--> run YOLO if enabled and available
  +--> otherwise use OpenCV fallback
  +--> calculate density
  +--> store DetectionEvent
  +--> optionally create TrafficObservation
  +--> update last-known signal state
  |
  v
Return detection result
```

Detection queue architecture:

```text
Camera / frame source
  |
  v
DetectionQueueService
  |
  v
Detection workers
  |
  v
DetectionService
  |
  v
Signal engine reads latest valid state
```

Signal generation does not wait for YOLO. If detection is stale, queued, failed, or unavailable, the optimizer moves down the fallback hierarchy.

## 9. Signal Optimization Flow

```text
Frontend Optimize button
  |
  v
POST /api/v1/signals/optimize
  |
  v
SignalOptimizationService.optimize()
  |
  +--> load intersection
  +--> check active emergencies
  |
  +--> if emergency exists:
  |       use emergency override
  |
  +--> otherwise select signal decision source:
          1. live_detection
          2. prediction
          3. historical_observation
          4. safe_fallback_plan
  |
  +--> calculate green time
  +--> split phases by directional volume when available
  +--> append pedestrian clearance phase
  +--> save SignalPlan and SignalPhase rows
  +--> update last-known signal state
  +--> invalidate signal/dashboard cache
  |
  v
Return signal plan to frontend
```

Decision source visibility:

```text
SignalPlan.decision_source
Dashboard metadata.signal_decision_source
Frontend Signal Control badge
```

## 10. Emergency Corridor Flow

```text
Frontend creates emergency
  |
  v
POST /api/v1/emergencies
  |
  v
EmergencyService.create()
  |
  +--> clear existing active emergency at intersection
  +--> store EmergencyEvent
  +--> create emergency signal plan
  |
  v
Return emergency event
```

Green corridor path:

```text
Frontend submits corridor intersections
  |
  v
POST /api/v1/emergencies/{id}/corridor
  |
  v
EmergencyService.create_corridor()
  |
  +--> validate emergency exists
  +--> validate intersections exist
  +--> estimate offset by average speed
  +--> mark conflict if higher-priority emergency overlaps
  +--> store EmergencyCorridor rows
  +--> create downstream emergency signal plans
  |
  v
Return corridor legs
```

Priority order:

```text
ambulance
fire
disaster response
police
vip
```

## 11. Health And Metrics Flow

Health endpoints:

```text
/health
/health/db
/health/cache
/health/ml
```

Metrics endpoint:

```text
/metrics
```

Tracked categories:

```text
API latency
prediction latency
detection latency
cache hits and misses
detection queue depth
signal fallback activations
YOLO failures
detection freshness
```

## 12. Startup And Migration Flow

```text
Backend container starts
  |
  v
alembic upgrade head
  |
  v
FastAPI create_app()
  |
  v
prepare_database()
  |
  +--> development with AUTO_CREATE_TABLES=true:
  |       create tables for local convenience
  |
  +--> production:
          require AUTO_CREATE_TABLES=false
          require migrations to be current
```

Production should use Alembic as the schema authority.

## 13. Failure And Degraded Mode Map

```text
Redis unavailable
  -> cache disabled
  -> local job executor fallback
  -> API keeps working

RQ worker unavailable
  -> queued jobs do not complete until worker returns
  -> API remains available

XGBoost unavailable
  -> RandomForest fallback

YOLO unavailable
  -> OpenCV fallback for detection
  -> optimizer can use prediction/history/static fallback

No trained ML model
  -> optimizer skips prediction if none exists
  -> uses latest historical observation
  -> otherwise safe fallback plan

No traffic observations
  -> optimizer creates safe fallback timing
```

## 14. End-To-End Operator Scenario

```text
1. Operator opens frontend.
2. Frontend loads dashboard summary.
3. Backend checks Redis cache.
4. On cache miss, backend reads PostgreSQL and stores response in Redis.
5. Operator creates or selects an intersection.
6. Operator logs traffic observations or uploads a frame.
7. Backend stores observations and updates last-known state.
8. Operator trains ML model.
9. Backend queues job in Redis.
10. Worker trains XGBoost first, or RandomForest fallback.
11. Operator requests prediction.
12. Backend stores prediction.
13. Operator optimizes signal.
14. Optimizer chooses live detection, prediction, history, or safe fallback.
15. Backend stores signal plan and phases.
16. Frontend shows green timing, phase split, pedestrian phase, and decision source.
```
