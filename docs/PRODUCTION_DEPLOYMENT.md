# Production Deployment

Services:

- PostgreSQL: primary relational store and Alembic migration target.
- Redis: cache, RQ queue, and degraded-state acceleration.
- Backend: FastAPI API server.
- Worker: RQ worker for training and heavy jobs.
- Frontend: Vite/React operator dashboard.
- Monitoring: scrape `/metrics` from the backend.

Recommended startup:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

Required production settings:

```env
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
ENABLE_AUTH=true
API_KEY=<strong-secret>
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
JOB_QUEUE_ENABLED=true
TRAFFIC_MODEL=xgboost
```

Migration workflow:

```bash
cd backend
alembic upgrade head
```

Production must not rely on SQLAlchemy `create_all`. Startup validation blocks production if `AUTO_CREATE_TABLES=true`.

Operational checks:

- `/health`
- `/health/db`
- `/health/cache`
- `/health/ml`
- `/metrics`

For multi-instance production, move rate limiting to an ingress layer and run multiple RQ workers sized to GPU/CPU capacity.
