from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_INSECURE_API_KEY = "dev-insecure-key-change-me"


class Settings(BaseSettings):
    app_name: str = "Smart Traffic Optimization System"
    environment: str = "development"
    log_level: str = Field(default="INFO")
    database_url: str = "postgresql+psycopg://traffic:traffic@localhost:5432/traffic_manager"
    auto_create_tables: bool = True
    api_key: str = Field(default=DEFAULT_INSECURE_API_KEY)
    enable_auth: bool = Field(default=False)
    redis_url: str = ""
    cache_enabled: bool = False
    cache_ttl_seconds: int = 30
    job_queue_enabled: bool = False
    session_ttl_seconds: int = 28800
    session_cookie_name: str = "roadmind_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    traffic_model: str = "xgboost"
    detection_freshness_seconds: int = 10
    detection_worker_count: int = 2
    detection_batch_size: int = 4
    upload_max_bytes: int = 10 * 1024 * 1024
    rate_limit_per_minute: int = 120
    metrics_enabled: bool = True
    enable_yolo: bool = False
    yolo_model_path: str = "yolov8n.pt"
    yolo_device: str = "cpu"
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
    # Fail fast rather than silently booting an insecure production instance:
    # docker-compose.prod.yml enables auth but does not override API_KEY, so it
    # would otherwise inherit the base compose file's dev default.
    if (
        settings.environment.lower() == "production"
        and settings.api_key == DEFAULT_INSECURE_API_KEY
    ):
        raise RuntimeError(
            "Refusing to start in production with the default development API key. "
            "Set a real API_KEY via .env or a secret before deploying "
            "(ENVIRONMENT=production is set but API_KEY is still "
            f"'{DEFAULT_INSECURE_API_KEY}')."
        )
    return settings
