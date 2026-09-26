"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.config import router as config_router
from app.api.v1.health import register_ready_check
from app.api.v1.health import router as health_router
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging


def _data_dir_check() -> dict:
    """Readiness check: data directory is writable."""
    settings = get_settings()
    p = Path(settings.data_dir)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    test_file = p / ".write_test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        return {"status": "ok"}
    except OSError as e:
        return {"status": "error", "detail": str(e)}


def create_app() -> FastAPI:
    settings = get_settings()

    # Setup logging first
    setup_logging(settings.log_level)

    app = FastAPI(
        title="TTE PDF API",
        version="1.0.0",
        openapi_url="/api/openapi.json" if settings.api_docs_enabled else None,
        docs_url="/api/docs" if settings.api_docs_enabled else None,
        redoc_url=None,
    )

    # Error handlers
    register_error_handlers(app)

    # Middleware
    from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.hsts)
    app.add_middleware(RequestIDMiddleware)

    # Routers
    app.include_router(health_router, prefix="/api/v1/health")
    app.include_router(config_router, prefix="/api/v1")

    # Readiness checks
    register_ready_check("data_dir", _data_dir_check)

    # Static files (frontend build output)
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
