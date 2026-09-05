from fastapi import APIRouter

from app.api import (
    auth,
    dashboard,
    detections,
    emergencies,
    health,
    intersections,
    jobs,
    predictions,
    signals,
    traffic,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(intersections.router, prefix="/intersections", tags=["intersections"])
api_router.include_router(traffic.router, prefix="/traffic", tags=["traffic"])
api_router.include_router(detections.router, prefix="/detections", tags=["detections"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(emergencies.router, prefix="/emergencies", tags=["emergencies"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
