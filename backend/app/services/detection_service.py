from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.core.metrics import Timer, get_metrics
from app.models import DetectionEvent
from app.repositories.detection_repository import DetectionRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.signal_state_repository import SignalStateRepository
from app.schemas import DetectionRead, TrafficObservationCreate
from app.services.density_service import DensityService
from app.services.traffic_service import TrafficService
from app.vision.yolo_detector import YOLOVehicleDetector


class DetectionService:
    def __init__(self, db: Session):
        self.db = db
        self.intersections = IntersectionRepository(db)
        self.detections = DetectionRepository(db)
        self.signal_states = SignalStateRepository(db)
        self.traffic = TrafficService(db)
        self.density = DensityService()
        self.detector = YOLOVehicleDetector()

    def detect(
        self,
        image_bytes: bytes,
        intersection_id: UUID | None = None,
        persist_observation: bool = True,
    ) -> DetectionRead:
        timer = Timer()
        intersection = None
        if intersection_id:
            intersection = self.intersections.get(intersection_id)
            if not intersection:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")

        try:
            result = self.detector.detect(image_bytes)
        except ValueError as exc:
            get_metrics().record_yolo_failure()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        density = self.density.calculate(
            result.vehicle_count,
            intersection.lanes if intersection else None,
            road_type=intersection.road_type if intersection else "urban",
        )
        event = DetectionEvent(
            intersection_id=intersection_id,
            vehicle_count=result.vehicle_count,
            density=density,
            frame_width=result.frame_width,
            frame_height=result.frame_height,
            metadata_json={
                "boxes": [box.model_dump() for box in result.boxes],
                "emergency_detected": result.emergency_detected,
                "persist_observation": persist_observation,
            },
        )
        saved = self.detections.create(event)

        if intersection_id and persist_observation:
            self.traffic.create_observation(
                TrafficObservationCreate(
                    intersection_id=intersection_id,
                    vehicle_count=result.vehicle_count,
                    density=density,
                    source="vision",
                )
            )
            self.signal_states.upsert(
                intersection_id=intersection_id,
                last_density=density,
                last_vehicle_count=result.vehicle_count,
                decision_source="live_detection",
                last_detection_timestamp=saved.created_at,
            )
            get_cache().set_json(
                f"signal_state:{intersection_id}",
                {
                    "last_density": density,
                    "last_vehicle_count": result.vehicle_count,
                    "last_detection_timestamp": saved.created_at.isoformat(),
                    "decision_source": "live_detection",
                },
            )

        get_metrics().observe_detection(timer.elapsed())
        return DetectionRead(
            id=saved.id,
            intersection_id=intersection_id,
            vehicle_count=result.vehicle_count,
            density=density,
            frame_width=result.frame_width,
            frame_height=result.frame_height,
            boxes=result.boxes,
            emergency_detected=result.emergency_detected,
        )
