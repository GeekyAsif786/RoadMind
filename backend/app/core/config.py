from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_INSECURE_API_KEY = "dev-insecure-key-change-me"


class Settings(BaseSettings):
    app_name: str = "Smart Traffic Optimization System"
    environment: str = "development"
    log_level: str = Field(default="INFO")

    database_url: str = (
        "postgresql+psycopg://traffic:traffic@localhost:5432/traffic_manager"
    )

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

    # ~50 PCUs per lane for urban Indian arterials
    default_lane_capacity: int = 50

    # NH/expressway lanes
    highway_lane_capacity: int = 80

    # Service lanes and bylanes
    service_road_capacity: int = 25

    min_green_seconds: int = 15
    max_green_seconds: int = 90
    yellow_seconds: int = 4
    red_clearance_seconds: int = 3

    # Mandatory pedestrian phase per cycle
    pedestrian_clearance_seconds: int = 7
    enable_pedestrian_phase: bool = True

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


def _validate_production_settings(settings: Settings) -> None:
    """
    Fail fast when production is configured with development defaults
    or explicitly unsafe settings.
    """

    # 1. Never allow the development API key in production.
    if settings.api_key == DEFAULT_INSECURE_API_KEY:
        raise RuntimeError(
            "Refusing to start in production with the default "
            "development API key. Set a real API_KEY before deployment."
        )

    # 2. Authentication must be enabled in production.
    if not settings.enable_auth:
        raise RuntimeError(
            "Refusing to start in production with ENABLE_AUTH=false. "
            "Enable authentication before deployment."
        )

    # 3. Production schema changes must use Alembic.
    if settings.auto_create_tables:
        raise RuntimeError(
            "Refusing to start in production with "
            "AUTO_CREATE_TABLES=true. Use Alembic migrations instead."
        )

    # 4. Session cookies must be protected by HTTPS.
    if not settings.session_cookie_secure:
        raise RuntimeError(
            "Refusing to start in production with "
            "SESSION_COOKIE_SECURE=false. "
            "Production session cookies must use Secure."
        )

    # 5. Validate CORS configuration.
    origins = settings.cors_origin_list

    if "*" in origins:
        raise RuntimeError(
            "Refusing to start in production with wildcard CORS."
        )

    insecure_origins = [
        origin
        for origin in origins
        if not origin.lower().startswith("https://")
    ]

    if insecure_origins:
        raise RuntimeError(
            "Refusing to start in production with non-HTTPS CORS "
            f"origins: {', '.join(insecure_origins)}"
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    settings.model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if settings.environment.lower() == "production":
        _validate_production_settings(settings)

    return settings