import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from app.api import health
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import Timer, get_metrics
from app.core.security import security_headers, validate_rate_limit
from app.core.startup import prepare_database
from app.db.session import engine

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    prepare_database(engine, settings)

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def production_hardening_middleware(request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        try:
            validate_rate_limit(request)
        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", "Request rejected")
            return JSONResponse({"detail": detail}, status_code=status_code, headers={"X-Request-ID": request_id})
        timer = Timer()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        for header, value in security_headers().items():
            if header not in response.headers:
                response.headers[header] = value
        get_metrics().observe_api(request.method, request.url.path, timer.elapsed())
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=get_metrics().render(), media_type="text/plain; version=0.0.4")

    app.include_router(health.router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
