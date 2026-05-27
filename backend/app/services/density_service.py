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

    def calculate(self, vehicle_count: int, lanes: int | None = None, road_type: str = "urban") -> float:
        lane_count = max(lanes or 1, 1)
        capacity_map = {
            "urban": self.settings.default_lane_capacity,
            "highway": self.settings.highway_lane_capacity,
            "service": self.settings.service_road_capacity,
        }
        capacity_per_lane = capacity_map.get(road_type, self.settings.default_lane_capacity)
        capacity = lane_count * capacity_per_lane
        return round(min(vehicle_count / capacity, 1.0), 4)

    def calculate_pcu(
        self,
        vehicle_class_counts: dict[str, int],
        lanes: int | None = None,
        road_type: str = "urban",
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
        capacity_map = {
            "urban": self.settings.default_lane_capacity,
            "highway": self.settings.highway_lane_capacity,
            "service": self.settings.service_road_capacity,
        }
        capacity_per_lane = capacity_map.get(road_type, self.settings.default_lane_capacity)
        capacity = lane_count * capacity_per_lane
        density = round(min(pcu_total / capacity, 1.0), 4)
        return density, round(pcu_total, 2)

    @staticmethod
    def classify(density: float, avg_speed: float | None = None) -> str:
        """
        Classify congestion level.
        avg_speed (km/h) can override density-based classification:
        - speed < 10 km/h always = critical regardless of density
        - speed < 20 km/h always >= high
        - speed > 50 km/h and density < 0.4 = low (free flow)
        """
        # Speed override rules (Indian urban free-flow ~50 km/h)
        if avg_speed is not None:
            if avg_speed < 10:
                return "critical"
            if avg_speed < 20 and density >= 0.3:
                return "high"
            if avg_speed > 50 and density < 0.4:
                return "low"

        # Density fallback (original logic)
        if density >= 0.8:
            return "critical"
        if density >= 0.55:
            return "high"
        if density >= 0.3:
            return "moderate"
        return "low"
