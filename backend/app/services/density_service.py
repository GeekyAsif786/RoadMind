from app.core.config import get_settings


class DensityService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def calculate(self, vehicle_count: int, lanes: int | None = None) -> float:
        lane_count = max(lanes or 1, 1)
        capacity = lane_count * self.settings.default_lane_capacity
        return round(min(vehicle_count / capacity, 1.0), 4)

    @staticmethod
    def classify(density: float) -> str:
        if density >= 0.8:
            return "critical"
        if density >= 0.55:
            return "high"
        if density >= 0.3:
            return "moderate"
        return "low"
