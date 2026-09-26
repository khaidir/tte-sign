"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.config import router as config_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import register_ready_check
from app.api.v1.health import router as health_router
from app.config import get_settings
from app.core.audit import AuditLogger
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.services.janitor import Janitor
from app.services.storage import FileStorage
from app.services.worker_pool import WorkerPool

logger = logging.getLogger("tte")


# ------------------------------------------------------------------
# Application state (global singletons)
# ------------------------------------------------------------------


class AppState:
    """Holds application-wide service instances."""

    def __init__(self) -> None:
        self.pool: WorkerPool
        self.storage: FileStorage
        self.audit: AuditLogger
        self.janitor: Janitor
        self._janitor_task: asyncio.Task[None] | None = None


app_state = AppState()


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:  # noqa: ARG001
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # --- startup ---
    # Worker pool
    app_state.pool = WorkerPool(
        max_workers=settings.pdf_workers,
        memory_mb=settings.worker_memory_mb,
    )
    app_state.pool.start()
    register_ready_check("worker_pool", lambda: {"status": "ok" if app_state.pool.is_ready else "error"})  # noqa: E501

    # Storage
    app_state.storage = FileStorage(data_dir=settings.data_dir)

    # Audit
    app_state.audit = AuditLogger()

    # Janitor
    app_state.janitor = Janitor(
        storage=app_state.storage,
        audit=app_state.audit,
        interval=60.0,
    )
    app_state._janitor_task = asyncio.create_task(app_state.janitor.run())

    logger.info("Application started")

    yield

    # --- shutdown ---
    if app_state._janitor_task is not None:
        app_state.janitor.stop()
        app_state._janitor_task.cancel()
        try:
            await app_state._janitor_task
        except asyncio.CancelledError:
            pass

    await app_state.pool.stop()
    logger.info("Application stopped")


# ------------------------------------------------------------------
# Readiness checks
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


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
        lifespan=lifespan,
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
    app.include_router(documents_router, prefix="/api/v1")

    # Readiness checks
    register_ready_check("data_dir", _data_dir_check)

    # Static files (frontend build output)
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
