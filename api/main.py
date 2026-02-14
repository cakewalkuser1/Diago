"""
Diago FastAPI Service
Central API for the web UI (primary). Also used as a local sidecar for Tauri
desktop and can be deployed for cloud/mobile.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from database.db_manager import DatabaseManager
from api.deps import set_db_manager, clear_db_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    settings = get_settings()

    # Setup logging
    log_level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Initialize database
    logger.info("Starting Diago API v%s", settings.app_version)
    db = DatabaseManager(settings.db_path, settings.obd2_codes_path)
    db.initialize()
    set_db_manager(db)
    logger.info("Database initialized at %s", settings.db_path)

    yield

    # Shutdown
    db.close()
    clear_db_manager()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Diago API",
        description="Automotive Audio Diagnostic Engine API",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS: set CORS_ORIGINS in production (e.g. "https://app.example.com"); empty = allow all (dev/sidecar)
    origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import routers here to avoid circular imports
    from api.routes.diagnosis import router as diagnosis_router
    from api.routes.audio import router as audio_router
    from api.routes.sessions import router as sessions_router
    from api.routes.signatures import router as signatures_router
    from api.routes.codes import router as codes_router
    from api.routes.payments import router as payments_router
    from api.routes.vehicle import router as vehicle_router
    from api.routes.tsb import router as tsb_router

    # Register route modules
    app.include_router(diagnosis_router, prefix="/api/v1/diagnosis", tags=["Diagnosis"])
    app.include_router(audio_router, prefix="/api/v1/audio", tags=["Audio"])
    app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["Sessions"])
    app.include_router(signatures_router, prefix="/api/v1/signatures", tags=["Signatures"])
    app.include_router(codes_router, prefix="/api/v1/codes", tags=["Trouble Codes"])
    app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])
    app.include_router(vehicle_router, prefix="/api/v1/vehicle", tags=["Vehicle"])
    app.include_router(tsb_router, prefix="/api/v1/tsbs", tags=["TSBs"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": settings.app_version}

    return app


# Create the default app instance (for `uvicorn api.main:app`)
app = create_app()
