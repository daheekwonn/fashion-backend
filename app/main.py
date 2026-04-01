"""
main.py — FastAPI application entrypoint

Run locally:
    uvicorn app.main:app --reload --port 8000

API docs (auto-generated):
    http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import init_db
from app.routers import trends

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting up — initialising database...")
    await init_db()
    logger.info("Database ready.")
    # Install Playwright Chromium if not already installed
    import subprocess, sys
    logger.info("Installing Playwright Chromium...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    logger.info("Playwright ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Fashion Trend Intelligence API",
    description=(
        "Backend for the Vogue Data trend forecasting platform. "
        "Indexes runway shows, computes trend scores, and surfaces "
        "top materials, silhouettes, colors, and keywords."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(trends.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "season": settings.ACTIVE_SEASON}


# ── Root ─────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name":    "Fashion Trend Intelligence API",
        "version": "1.0.0",
        "docs":    "/docs",
    }

from app.routers.suggest_tags import router as suggest_tags_router
app.include_router(suggest_tags_router)