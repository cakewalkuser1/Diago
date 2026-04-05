"""
Diago FastAPI Service
Central API for the web UI (primary). Also used as a local sidecar for Tauri
desktop and can be deployed for cloud/mobile.
"""

import asyncio
import html
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from database.db_manager import DatabaseManager
from api.deps import get_db_manager, set_db_manager, clear_db_manager
from api.ollama_startup import ensure_ollama_running

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

    # Start Ollama in background if not running (so DiagBot works without user setup)
    asyncio.create_task(ensure_ollama_running())

    yield

    # Shutdown
    db.close()
    clear_db_manager()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Autopilot API",
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
    from api.routes.chat import router as chat_router
    from api.routes.repairs import router as repairs_router
    from api.routes.analytics import router as analytics_router
    from api.routes.repair_guides import router as repair_guides_router
    from api.routes.dispatch import router as dispatch_router
    from api.routes.geocode import router as geocode_router
    from api.routes.mechanic_profile import router as mechanic_profile_router
    from api.routes.ws_tracking import router as ws_tracking_router
    from api.routes.reviews import router as reviews_router
    from api.routes.notifications import router as notifications_router
    from api.routes.maintenance import router as maintenance_router

    # Register route modules
    app.include_router(diagnosis_router, prefix="/api/v1/diagnosis", tags=["Diagnosis"])
    app.include_router(audio_router, prefix="/api/v1/audio", tags=["Audio"])
    app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["Sessions"])
    app.include_router(signatures_router, prefix="/api/v1/signatures", tags=["Signatures"])
    app.include_router(codes_router, prefix="/api/v1/codes", tags=["Trouble Codes"])
    app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])
    app.include_router(vehicle_router, prefix="/api/v1/vehicle", tags=["Vehicle"])
    app.include_router(tsb_router, prefix="/api/v1/tsbs", tags=["TSBs"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
    app.include_router(repairs_router, prefix="/api/v1/repairs", tags=["Repairs"])
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(repair_guides_router, prefix="/api/v1/repair-guides", tags=["Repair Guides"])
    app.include_router(dispatch_router, prefix="/api/v1/dispatch", tags=["Dispatch"])
    app.include_router(geocode_router, prefix="/api/v1", tags=["Geocode"])
    app.include_router(mechanic_profile_router, prefix="/api/v1/mechanic", tags=["Mechanic Profile"])
    app.include_router(ws_tracking_router, prefix="/api/v1/tracking", tags=["Tracking"])
    app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["Reviews"])
    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
    app.include_router(maintenance_router, prefix="/api/v1/maintenance", tags=["Maintenance"])

    # Serve uploaded photos (diagnosis/chat)
    uploads_dir = settings.user_data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": settings.app_version}

    @app.get("/mechanic/job/{job_id:int}", response_class=HTMLResponse)
    async def mechanic_job_page(job_id: int):
        """Standalone HTML page for mechanic to accept/deny a job (link in SMS/email)."""
        from api.deps import get_db_manager
        db = get_db_manager()
        cursor = db.connection.execute(
            "SELECT id, part_info, status, created_at FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return HTMLResponse(_mechanic_html(job_id, error="Job not found"), status_code=404)
        if row["status"] != "mechanic_pinged":
            return HTMLResponse(_mechanic_html(job_id, error=f"Job is no longer pending (status: {html.escape(str(row['status']))})"))
        part_info = row["part_info"] or "Part repair"
        created = row["created_at"] or ""
        return _mechanic_html(job_id, part_info=part_info, created=created)

    return app


def _mechanic_html(job_id: int, part_info: str = "", created: str = "", error: str | None = None) -> str:
    """Minimal HTML for mechanic accept/deny page."""
    esc = html.escape
    if error:
        content = f"""
    <div class="card">
      <h1>Autopilot – Job #{job_id}</h1>
      <p class="msg err">{esc(error)}</p>
    </div>
    """
    else:
        content = f"""
    <div class="card">
      <h1>Autopilot – Job #{job_id}</h1>
      <p class="part">{esc(part_info)}</p>
      <p class="meta">Requested: {esc(created)}</p>
      <p class="prompt">Accept or deny this job?</p>
      <div class="actions">
        <button id="accept" class="btn accept">Accept</button>
        <button id="deny" class="btn deny">Deny</button>
      </div>
      <p id="msg" class="msg"></p>
    </div>
    <script>
      const jobId = {job_id};
      const apiUrl = window.location.origin + '/api/v1/dispatch/job/' + jobId + '/respond';
      document.getElementById('accept').onclick = () => respond(true);
      document.getElementById('deny').onclick = () => respond(false);
      async function respond(accepted) {{
        document.querySelectorAll('.btn').forEach(b => b.disabled = true);
        try {{
          const r = await fetch(apiUrl, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ accepted }})
          }});
          const data = await r.json();
          document.getElementById('msg').textContent = accepted ? 'Job accepted! The customer has been notified.' : 'Job declined.';
          document.getElementById('msg').className = 'msg ok';
        }} catch (e) {{
          document.getElementById('msg').textContent = 'Error: ' + e.message;
          document.getElementById('msg').className = 'msg err';
        }}
      }}
    </script>
    """
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Autopilot – Job #{job_id}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #1e1e2e; color: #cdd6f4; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
    .card {{ background: #313244; border-radius: 12px; padding: 1.5rem; max-width: 420px; width: 100%; }}
    h1 {{ font-size: 1.25rem; margin: 0 0 1rem; color: #89b4fa; }}
    .part {{ color: #a6e3a1; margin: 0.5rem 0; }}
    .meta {{ font-size: 0.875rem; color: #a6adc8; margin: 0.5rem 0; }}
    .prompt {{ margin: 1rem 0 0.5rem; }}
    .actions {{ display: flex; gap: 0.75rem; margin-top: 1rem; }}
    .btn {{ padding: 0.5rem 1rem; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }}
    .btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
    .accept {{ background: #a6e3a1; color: #1e1e2e; }}
    .deny {{ background: #f38ba8; color: #1e1e2e; }}
    .msg {{ margin-top: 1rem; font-size: 0.9rem; }}
    .msg.ok {{ color: #a6e3a1; }}
    .msg.err {{ color: #f38ba8; }}
  </style>
</head>
<body>
  {content}
</body>
</html>"""


# Create the default app instance (for `uvicorn api.main:app`)
app = create_app()
