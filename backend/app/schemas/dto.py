from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntersectionBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    lanes: int = Field(default=4, ge=1, le=16)
    status: str = "active"


class IntersectionCreate(IntersectionBase):
    pass


class IntersectionRead(IntersectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class TrafficObservationCreate(BaseModel):
    intersection_id: UUID
    direction: str = Field(default="ALL", pattern=r"^(N|S|E|W|NE|NW|SE|SW|ALL)$")
    vehicle_count: int = Field(ge=0)
    density: float | None = Field(default=None, ge=0, le=1)
    avg_speed: float | None = Field(default=None, ge=0)
    occupancy: float | None = Field(default=None, ge=0, le=1)
    weather_condition: str = Field(default="clear", pattern=r"^(clear|light_rain|heavy_rain|fog|smog)$")
    pcu_total: float | None = Field(default=None, ge=0)
    source: str = "manual"
    captured_at: datetime | None = None


class TrafficObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intersection_id: UUID
    direction: str
    vehicle_count: int
    density: float
    avg_speed: float | None
    occupancy: float | None
    weather_condition: str
    pcu_total: float | None
    source: str
    captured_at: datetime
    created_at: datetime


class BoundingBox(BaseModel):
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionRead(BaseModel):
    id: UUID | None = None
    intersection_id: UUID | None = None
    vehicle_count: int
    density: float
    frame_width: int
    frame_height: int
    boxes: list[BoundingBox]
    emergency_detected: bool = False


class SignalPhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    phase_number: int
    direction: str
    green_seconds: int
    yellow_seconds: int
    phase_order: int
    created_at: datetime


class SignalPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intersection_id: UUID
    green_seconds: int
    yellow_seconds: int
    red_seconds: int
    priority: str
    reason: str
    expires_at: datetime | None
    created_at: datetime
    phases: list[SignalPhaseRead] = Field(default_factory=list)


class EmergencyCreate(BaseModel):
    intersection_id: UUID
    vehicle_type: str = Field(min_length=3, max_length=60)
    direction: str = Field(min_length=1, max_length=40)
    severity: int = Field(default=5, ge=1, le=10)


class EmergencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intersection_id: UUID
    vehicle_type: str
    direction: str
    severity: int
    status: str
    detected_at: datetime
    cleared_at: datetime | None
    created_at: datetime


class EmergencyCorridorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    emergency_id: UUID
    intersection_id: UUID
    sequence_order: int
    green_offset_seconds: int
    status: str
    created_at: datetime


class PredictionTrainResponse(BaseModel):
    model_version: str
    samples: int
    score: float | None


class PredictionRequest(BaseModel):
    intersection_id: UUID
    horizon_minutes: int = Field(default=15, ge=1, le=240)
    direction: str = Field(default="ALL", pattern=r"^(N|S|E|W|NE|NW|SE|SW|ALL)$")
    weather_condition: str = Field(default="clear", pattern=r"^(clear|light_rain|heavy_rain|fog|smog)$")
    pcu_total: float | None = Field(default=None, ge=0)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intersection_id: UUID
    horizon_minutes: int
    predicted_density: float
    predicted_vehicle_count: float
    model_version: str
    created_at: datetime


class OptimizationRequest(BaseModel):
    intersection_id: UUID
    horizon_minutes: int = Field(default=15, ge=1, le=240)


class DashboardSummary(BaseModel):
    intersections: int
    active_emergencies: int
    latest_density: float | None
    latest_vehicle_count: int | None
    signal_plans: list[SignalPlanRead]
    observations: list[TrafficObservationRead]
    emergencies: list[EmergencyRead]
    predictions: list[PredictionRead]
    metadata: dict[str, Any] = Field(default_factory=dict)
