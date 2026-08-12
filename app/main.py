"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import get_settings
from app.database import init_db
from app.routes import dashboard, books, chunks, prompt_lab, settings as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("Starting Sefaria Daily AI")
    init_db()
    # Start scheduler
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as exc:
        logger.warning("Scheduler could not start: %s", exc)
    yield
    logger.info("Shutting down Sefaria Daily AI")
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app_settings = get_settings()

app = FastAPI(
    title=app_settings.app_title,
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(dashboard.router)
app.include_router(books.router, prefix="/books")
app.include_router(chunks.router, prefix="/chunks")
app.include_router(prompt_lab.router, prefix="/prompt-lab")
app.include_router(settings_router.router, prefix="/settings")
