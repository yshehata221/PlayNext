from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .limiter import limiter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, backfill_usernames, engine, ensure_columns
from .routers import auth, browse, friends, games, library, recommendations, stats, steam, wishlist
from .services.media import MEDIA_DIR

def prepare_database() -> None:
    """
    Schema is managed by Alembic (`alembic upgrade head`). For convenience -
    a fresh clone, a test run, a container with no entrypoint hook - we create
    anything missing and stamp it, so the app boots either way. ensure_columns
    stays as a safety net for databases created before migrations existed.
    """
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    Base.metadata.create_all(bind=engine)
    ensure_columns()
    try:
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.stamp(cfg, "head")
    except Exception:  # a missing alembic.ini shouldn't stop the app starting
        pass
    backfill_usernames()


prepare_database()

app = FastAPI(
    title="PlayNext API",
    description="Cross-platform game library, backlog tracking and a content-based recommender.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline hardening for a publicly reachable API."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, browse, friends, games, library, recommendations, stats, steam, wishlist):
    app.include_router(r.router)

MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


SCANNER = Path(__file__).resolve().parents[2] / "scanner" / "playnext_scan.py"


@app.get("/scanner/playnext_scan.py", tags=["meta"], include_in_schema=False)
def download_scanner():
    """Let the web app hand out the local scanner without a separate host."""
    return FileResponse(SCANNER, media_type="text/x-python", filename="playnext_scan.py")


@app.get("/config", tags=["meta"])
def config():
    """
    Which optional integrations this deployment has keys for. The UI uses this
    to hide or explain features rather than offering a button that can't work.
    """
    from .config import settings

    return {
        "steam_import": bool(settings.steam_api_key),
        "igdb_catalogue": bool(settings.igdb_client_id and settings.igdb_client_secret),
        "email": settings.mail_mode == "smtp" and bool(settings.smtp_host),
        "require_email_verification": settings.require_email_verification,
        "demo_login": settings.enable_demo_login,
    }


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}
