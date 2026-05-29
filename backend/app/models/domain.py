import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class Intersection(Base, TimestampMixin):
    __tablename__ = "intersections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    lanes: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    road_type: Mapped[str] = mapped_column(String(20), nullable=False, default="urban")
    # Allowed values: "urban", "highway", "service"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")

    observations: Mapped[list["TrafficObservation"]] = relationship(back_populates="intersection")
    signal_plans: Mapped[list["SignalPlan"]] = relationship(back_populates="intersection")
    emergencies: Mapped[list["EmergencyEvent"]] = relationship(back_populates="intersection")


class TrafficObservation(Base, TimestampMixin):
    __tablename__ = "traffic_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL")
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    density: Mapped[float] = mapped_column(Float, nullable=False)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    occupancy: Mapped[float | None] = mapped_column(Float)
    weather_condition: Mapped[str] = mapped_column(String(20), nullable=False, default="clear")
    pcu_total: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )

    intersection: Mapped[Intersection] = relationship(back_populates="observations")


class DetectionEvent(Base, TimestampMixin):
    __tablename__ = "detection_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    density: Mapped[float] = mapped_column(Float, nullable=False)
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class SignalPlan(Base, TimestampMixin):
    __tablename__ = "signal_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE"), index=True
    )
    green_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    yellow_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    red_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(40), nullable=False, default="normal")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision_source: Mapped[str] = mapped_column(String(40), nullable=False, default="historical_observation")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    intersection: Mapped[Intersection] = relationship(back_populates="signal_plans")
    phases: Mapped[list["SignalPhase"]] = relationship(
        back_populates="plan", order_by="SignalPhase.phase_order"
    )


class SignalPhase(Base, TimestampMixin):
    __tablename__ = "signal_phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_plans.id", ondelete="CASCADE"), index=True
    )
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    green_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    yellow_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    phase_order: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped["SignalPlan"] = relationship(back_populates="phases")


class EmergencyEvent(Base, TimestampMixin):
    __tablename__ = "emergency_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE"), index=True
    )
    vehicle_type: Mapped[str] = mapped_column(String(60), nullable=False)
    direction: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    intersection: Mapped[Intersection] = relationship(back_populates="emergencies")


class EmergencyCorridor(Base, TimestampMixin):
    __tablename__ = "emergency_corridors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emergency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_events.id", ondelete="CASCADE"), index=True
    )
    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE")
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    green_offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE"), index=True
    )
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_density: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_vehicle_count: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)


class IntersectionSignalState(Base):
    __tablename__ = "intersection_signal_states"

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intersections.id", ondelete="CASCADE"), primary_key=True
    )
    last_density: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_signal_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_plans.id", ondelete="SET NULL"), nullable=True
    )
    last_detection_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_source: Mapped[str] = mapped_column(String(40), nullable=False, default="safe_fallback_plan")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class ModelEvaluation(Base, TimestampMixin):
    __tablename__ = "model_evaluations"
    __table_args__ = (UniqueConstraint("model_version", name="uq_model_evaluations_model_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_type: Mapped[str] = mapped_column(String(40), nullable=False)
    samples: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[float | None] = mapped_column(Float)
    rmse: Mapped[float | None] = mapped_column(Float)
    r2: Mapped[float | None] = mapped_column(Float)
