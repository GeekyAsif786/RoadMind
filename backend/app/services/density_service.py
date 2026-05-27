from app.core.config import get_settings


class DensityService:
    PCU_WEIGHTS: dict[str, float] = {
        "two_wheeler": 0.5,
        "auto_rickshaw": 0.8,
        "car": 1.0,
        "taxi": 1.0,
        "mini_bus": 2.0,
        "bus": 3.0,
        "truck": 3.5,
        "tractor": 4.0,
        "cattle": 1.5,
        "cycle": 0.3,
        "e_rickshaw": 0.6,
        "unknown": 1.0,
    }

    def __init__(self) -> None:
        self.settings = get_settings()

    def calculate(self, vehicle_count: int, lanes: int | None = None) -> float:
        lane_count = max(lanes or 1, 1)
        capacity = lane_count * self.settings.default_lane_capacity
        return round(min(vehicle_count / capacity, 1.0), 4)

    def calculate_pcu(
        self,
        vehicle_class_counts: dict[str, int],
        lanes: int | None = None,
    ) -> tuple[float, float]:
        """
        Returns (density, pcu_total).
        vehicle_class_counts: {"two_wheeler": 45, "car": 12, "bus": 2}
        """
        lane_count = max(lanes or 1, 1)
        pcu_total = sum(
            self.PCU_WEIGHTS.get(vtype, 1.0) * count
            for vtype, count in vehicle_class_counts.items()
        )
        capacity = lane_count * self.settings.default_lane_capacity
        density = round(min(pcu_total / capacity, 1.0), 4)
        return density, round(pcu_total, 2)

    @staticmethod
    def classify(density: float) -> str:
        if density >= 0.8:
            return "critical"
        if density >= 0.55:
            return "high"
        if density >= 0.3:
            return "moderate"
        return "low"
