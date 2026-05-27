# RoadMind Traffic Management System

RoadMind is a local-first traffic management and signal-optimization system for Indian road conditions. It combines a FastAPI backend, PostgreSQL persistence, a React operations dashboard, OpenCV-based traffic-frame processing, optional YOLOv8 detection, and a RandomForest prediction pipeline.

The project models intersections, traffic observations, vehicle density, passenger car unit totals, adaptive signal plans, emergency priority, green corridors, and short-horizon congestion forecasts. It is designed as an engineering scaffold: the dashboard and APIs simulate traffic-management workflows, while the backend keeps domain logic isolated and testable.

## What RoadMind Does

- Tracks intersections with lane count and road type: urban arterial, highway/expressway, or service road.
- Logs manual and image-derived traffic observations with direction, weather, speed, count, and optional PCU totals.
- Calculates density using Indian-road capacity assumptions instead of a fixed low vehicle threshold.
- Optimizes signal green time using density, weather, active emergencies, directional volume, peak hours, and night traffic rules.
- Adds pedestrian clearance phases to signal plans.
- Supports emergency priority and corridor green-wave planning across downstream intersections.
- Trains a RandomForestRegressor for traffic density and vehicle-count forecasting after enough observations are available.
- Provides a React dashboard for operations, frame upload, prediction, signal optimization, emergency handling, and a floating PCU calculator.

## Architecture

```text
backend/app
  api/              FastAPI route handlers and HTTP boundary validation
  services/         Business logic for traffic, density, prediction, signals, detection, and emergencies
  repositories/     SQLAlchemy persistence access for PostgreSQL
  models/           SQLAlchemy ORM domain models
  schemas/          Pydantic request/response DTOs
  vision/           OpenCV local detector with optional YOLOv8 support
  ml/               RandomForestRegressor training and inference
  core/             Settings, auth, logging, and India-specific calendar helpers
frontend/src        React operations dashboard
db/init             PostgreSQL bootstrap schema
db/seeds            Demo data for local development
```

The backend follows `Controller -> Service -> Repository`. Controllers validate HTTP inputs, services make traffic-management decisions, and repositories isolate database access.

## Key Concepts

- **Intersection**: A physical junction with coordinates, lane count, operating status, and road type.
- **Road type**: Capacity category used for density calculation: `urban`, `highway`, or `service`.
- **Traffic observation**: A timestamped record of traffic count, direction, density, speed, weather, PCU, and source.
- **Density**: Congestion ratio from traffic volume divided by lane capacity, capped at `1.0`.
- **PCU**: Passenger Car Unit, a normalized vehicle-load measure that weights buses, trucks, two-wheelers, and other vehicle types differently.
- **Average speed**: Optional km/h signal that can override density classification when traffic is clearly stalled or free-flowing.
- **Direction**: Movement bucket such as `N`, `S`, `E`, `W`, diagonals, or `ALL`.
- **Signal plan**: A saved timing recommendation with green, yellow, red, priority, reason, expiry, and phases.
- **Signal phase**: A per-direction slice of a signal plan, including pedestrian clearance when enabled.
- **Pedestrian phase**: Mandatory all-red pedestrian clearance phase appended to each cycle.
- **Emergency event**: Active priority request for ambulance, fire, or police movement through an intersection.
- **Emergency corridor**: Ordered set of intersections used to create a green-wave for an emergency vehicle.
- **Green-wave**: Offset signal activation across multiple intersections so an emergency route stays open.
- **Weather multiplier**: Adjustment that extends green time during rain, fog, or smog.
- **Peak hours**: IST morning and evening bands that add green-time bias for Indian commute patterns.
- **Prediction model**: RandomForestRegressor trained from historical observations to forecast density and vehicle count.
- **PCU calculator**: Draggable floating dashboard tool that converts vehicle-type quantities into total PCU.

## Backend Behavior

### Density

RoadMind uses configurable lane capacities:

```text
urban road:   50 PCUs per lane
highway:      80 PCUs per lane
service road: 25 PCUs per lane
```

Density is calculated as:

```text
density = min(volume / (lanes * road_type_capacity), 1.0)
```

If average speed is available, classification also considers flow quality:

- `< 10 km/h` is always `critical`.
- `< 20 km/h` with moderate density is at least `high`.
- `> 50 km/h` with low density is `low`.

### Signal Optimization

The optimizer:

1. Loads the selected intersection.
2. Checks active emergency priority first.
3. Reads recent observations for density, speed, weather, and directional volumes.
4. Calculates green seconds between configured min/max bounds.
5. Applies weather, monsoon, peak-hour, and night-time adjustments.
6. Splits vehicle phases by directional volume when recent directional data exists.
7. Appends a pedestrian clearance phase when enabled.
8. Saves the plan and phases to PostgreSQL.

If an active emergency exists, emergency priority overrides normal adaptive timing. If a corridor has been defined, RoadMind also creates downstream green-wave plans using corridor offsets.

### Prediction

The ML pipeline trains on historical traffic observations. Features include intersection, IST hour, day of week, quarter-hour bucket, PCU/effective count, weather, Indian holiday flag, monsoon flag, direction, raw count, density, average speed, and peak-hour flag.

Training requires at least `200` observations. This avoids fitting RandomForest on a tiny noisy sample.

## Run With Docker

```bash
docker compose up --build
```

Open:

- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

The default Docker setup is tuned for local development: no PyTorch, no CUDA packages, and no YOLO model download. Detection uses a lightweight OpenCV candidate detector unless YOLO is explicitly enabled.

## Optional YOLOv8

Use this only when you want the heavier detector:

```bash
cd backend
pip install -r requirements-vision.txt
ENABLE_YOLO=true uvicorn app.main:app --reload
```

For Docker:

```bash
docker compose build --build-arg INSTALL_YOLO=true backend
docker compose up
```

Leave `ENABLE_YOLO=false` for normal lightweight local development.

## Local Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

For local PostgreSQL, set `DATABASE_URL` in `backend/.env`.

## Local Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the backend is not running at `http://localhost:8000/api/v1`.

## Core API Examples

Create an intersection:

```bash
curl -X POST http://localhost:8000/api/v1/intersections \
  -H "Content-Type: application/json" \
  -d '{"name":"North Gate","latitude":28.61,"longitude":77.20,"lanes":4,"road_type":"urban"}'
```

Log a manual observation:

```bash
curl -X POST http://localhost:8000/api/v1/traffic/observations \
  -H "Content-Type: application/json" \
  -d '{"intersection_id":"<uuid>","direction":"N","vehicle_count":42,"avg_speed":18,"weather_condition":"clear","source":"manual"}'
```

Run signal optimization:

```bash
curl -X POST http://localhost:8000/api/v1/signals/optimize \
  -H "Content-Type: application/json" \
  -d '{"intersection_id":"<uuid>","horizon_minutes":15}'
```

Upload a frame for detection:

```bash
curl -X POST "http://localhost:8000/api/v1/detections/image?intersection_id=<uuid>&persist_observation=false" \
  -F "file=@traffic-frame.jpg"
```

Train the prediction model:

```bash
curl -X POST http://localhost:8000/api/v1/predictions/train
```

Create a prediction:

```bash
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{"intersection_id":"<uuid>","horizon_minutes":30,"direction":"ALL","weather_condition":"clear"}'
```

## Dashboard Workflow

1. Create or select an intersection.
2. Log observations manually or upload frames for detection review.
3. Use the floating PCU calculator to compute PCU totals from vehicle mix.
4. Train the prediction model once at least 200 observations exist.
5. Generate predictions for the selected intersection.
6. Run signal optimization to create a new signal timing plan.
7. Add emergency priority or create a green corridor when needed.

## Data And Migrations

- `db/init/001_schema.sql` bootstraps PostgreSQL for Docker/local database setup.
- `db/seeds/demo_data.sql` contains demo records for local development.
- `backend/alembic/versions` contains migrations for schema evolution.

When changing ORM models, keep the SQL bootstrap and Alembic migrations in sync.

## Verification Commands

Backend syntax check:

```bash
cd backend
python -m py_compile app/core/config.py app/services/density_service.py app/services/optimization_service.py app/services/traffic_service.py app/models/domain.py app/schemas/dto.py
```

Frontend build check:

```bash
npm --prefix frontend run build
```

Run tests when dependencies are installed:

```bash
cd backend
pytest
```
