from dataclasses import dataclass
from functools import cached_property

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.metrics import get_metrics
from app.schemas import BoundingBox


VEHICLE_LABELS = {"car", "truck", "bus", "motorcycle", "bicycle"}
EMERGENCY_LABEL_HINTS = {"ambulance", "fire truck", "police car", "emergency vehicle"}


@dataclass(frozen=True)
class DetectionResult:
    frame_width: int
    frame_height: int
    boxes: list[BoundingBox]
    emergency_detected: bool

    @property
    def vehicle_count(self) -> int:
        return len(self.boxes)


class YOLOVehicleDetector:
    def __init__(self) -> None:
        self.settings = get_settings()

    @cached_property
    def model(self):
        if not self.settings.enable_yolo:
            return None

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            get_metrics().record_yolo_failure()
            return None

        return YOLO(self.settings.yolo_model_path)

    def detect(self, image_bytes: bytes, confidence: float = 0.35) -> DetectionResult:
        image = self._decode(image_bytes)
        if not self.settings.enable_yolo:
            return self._detect_with_opencv(image)

        frame_height, frame_width = image.shape[:2]
        if self.model is None:
            return self._detect_with_opencv(image)

        try:
            predictions = self.model.predict(image, conf=confidence, verbose=False, device=self.settings.yolo_device)
        except Exception:
            get_metrics().record_yolo_failure()
            return self._detect_with_opencv(image)

        boxes: list[BoundingBox] = []
        emergency_detected = False

        for prediction in predictions:
            names = prediction.names
            for raw_box in prediction.boxes:
                class_id = int(raw_box.cls[0])
                label = str(names.get(class_id, class_id)).lower()
                score = float(raw_box.conf[0])
                if label not in VEHICLE_LABELS and label not in EMERGENCY_LABEL_HINTS:
                    continue
                xyxy = raw_box.xyxy[0].tolist()
                boxes.append(
                    BoundingBox(
                        label=label,
                        confidence=round(score, 4),
                        x1=round(float(xyxy[0]), 2),
                        y1=round(float(xyxy[1]), 2),
                        x2=round(float(xyxy[2]), 2),
                        y2=round(float(xyxy[3]), 2),
                    )
                )
                emergency_detected = emergency_detected or label in EMERGENCY_LABEL_HINTS

        return DetectionResult(
            frame_width=frame_width,
            frame_height=frame_height,
            boxes=boxes,
            emergency_detected=emergency_detected,
        )

    @staticmethod
    def _decode(image_bytes: bytes) -> np.ndarray:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Uploaded file is not a valid image")
        return image

    @staticmethod
    def _detect_with_opencv(image: np.ndarray) -> DetectionResult:
        frame_height, frame_width = image.shape[:2]
        resized = cv2.resize(image, (min(frame_width, 960), int(frame_height * min(frame_width, 960) / frame_width)))
        scale_x = frame_width / resized.shape[1]
        scale_y = frame_height / resized.shape[0]

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = max((resized.shape[0] * resized.shape[1]) * 0.002, 500)
        max_area = (resized.shape[0] * resized.shape[1]) * 0.18
        boxes: list[BoundingBox] = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            aspect_ratio = width / max(height, 1)
            if aspect_ratio < 0.6 or aspect_ratio > 4.5:
                continue
            boxes.append(
                BoundingBox(
                    label="vehicle_candidate",
                    confidence=0.35,
                    x1=round(float(x * scale_x), 2),
                    y1=round(float(y * scale_y), 2),
                    x2=round(float((x + width) * scale_x), 2),
                    y2=round(float((y + height) * scale_y), 2),
                )
            )

        boxes = sorted(
            boxes,
            key=lambda box: (box.x2 - box.x1) * (box.y2 - box.y1),
            reverse=True,
        )[:80]

        return DetectionResult(
            frame_width=frame_width,
            frame_height=frame_height,
            boxes=boxes,
            emergency_detected=False,
        )
