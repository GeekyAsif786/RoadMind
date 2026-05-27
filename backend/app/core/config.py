from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Traffic Optimization System"
    environment: str = "development"
    log_level: str = Field(default="INFO")
    database_url: str = "postgresql+psycopg://traffic:traffic@localhost:5432/traffic_manager"
    auto_create_tables: bool = True
    api_key: str = Field(default="dev-insecure-key-change-me")
    enable_auth: bool = Field(default=False)
    enable_yolo: bool = False
    yolo_model_path: str = "yolov8n.pt"
    model_dir: Path = Path("./runtime_models")
    default_lane_capacity: int = 50  # ~50 PCUs per lane for urban Indian arterials (IRC standard)
    highway_lane_capacity: int = 80   # NH/expressway lanes
    service_road_capacity: int = 25   # service lanes and bylanes
    min_green_seconds: int = 15
    max_green_seconds: int = 90
    yellow_seconds: int = 4
    red_clearance_seconds: int = 3
    pedestrian_clearance_seconds: int = 7   # mandatory pedestrian phase per cycle
    enable_pedestrian_phase: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    return settings
