# Smart Traffic Optimization System

Production-oriented traffic management scaffold with FastAPI, PostgreSQL, React, OpenCV, Scikit-Learn, and optional YOLOv8.

## Architecture

```text
backend/app
  api/              FastAPI controllers
  services/         Business logic and orchestration
  repositories/     PostgreSQL persistence access
  models/           SQLAlchemy domain models
  schemas/          Pydantic request/response DTOs
  vision/           OpenCV local detector with optional YOLOv8
  ml/               RandomForestRegressor training and inference
frontend/src        React operations dashboard
db/init             PostgreSQL bootstrap schema
```

The backend follows `Controller -> Service -> Repository`. Controllers validate HTTP boundaries, services contain traffic behavior, and repositories isolate SQLAlchemy access.

## Features

- MacBook-friendly OpenCV detection from uploaded traffic frames.
- Optional YOLOv8 vehicle detection for production or stronger hardware.
- Density calculation from vehicle count, lanes, and configurable lane capacity.
- PostgreSQL schema for intersections, observations, detections, signal plans, predictions, and emergencies.
- RandomForestRegressor training and prediction pipeline.
- Adaptive signal timing with emergency vehicle override.
- REST APIs under `/api/v1`.
- React dashboard for live metrics, manual observations, detection uploads, optimization, model actions, and emergency handling.
- Docker Compose setup for PostgreSQL, FastAPI, and Vite React.

## Run With Docker

```bash
docker compose up --build
```

Open:

- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

The default Docker setup is tuned for local MacBook Air M2 development: no PyTorch, no CUDA packages, and no YOLO model download. Detection uses a lightweight OpenCV candidate detector unless you opt into YOLO.

## Optional YOLOv8

Use this only when you want the heavier production detector:

```bash
cd backend
pip install -r requirements-vision.txt
ENABLE_YOLO=true uvicorn app.main:app --reload
```

For Docker, set `ENABLE_YOLO=true` and build the backend with:

```bash
docker compose build --build-arg INSTALL_YOLO=true backend
docker compose up
```

On a MacBook Air M2, leave `ENABLE_YOLO=false` for normal local work.

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
  -d '{"name":"North Gate","latitude":28.61,"longitude":77.20,"lanes":4}'
```

Log a manual observation:

```bash
curl -X POST http://localhost:8000/api/v1/traffic/observations \
  -H "Content-Type: application/json" \
  -d '{"intersection_id":"<uuid>","vehicle_count":32,"source":"manual"}'
```

Run signal optimization:

```bash
curl -X POST http://localhost:8000/api/v1/signals/optimize \
  -H "Content-Type: application/json" \
  -d '{"intersection_id":"<uuid>","horizon_minutes":15}'
```

Upload a frame for YOLOv8 detection:

```bash
curl -X POST "http://localhost:8000/api/v1/detections/image?intersection_id=<uuid>" \
  -F "file=@traffic-frame.jpg"
```

## Prediction Flow

1. Create or import at least 8 traffic observations.
2. Train the model with `POST /api/v1/predictions/train`.
3. Create forecasts with `POST /api/v1/predictions`.

The trained RandomForest model is persisted to `MODEL_DIR` and reused across API calls.
