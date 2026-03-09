"""
services/scheduler.py
─────────────────────
Celery beat tasks for daily automated pipeline runs.

Celery is used for:
  1. Daily search trend ingestion (Google Trends → DB)
  2. Daily trend scoring run
  3. Weekly full runway re-index

Start workers locally:
  # Terminal 1 — Redis (broker)
  redis-server

  # Terminal 2 — Celery worker
  celery -A app.services.scheduler worker --loglevel=info

  # Terminal 3 — Celery beat (cron scheduler)
  celery -A app.services.scheduler beat --loglevel=info
"""
import asyncio
import logging
from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "fashion_trends",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        # ── Every day at 6 AM UTC: pull Google Trends ────────────────────────
        "daily-search-ingest": {
            "task":     "app.services.scheduler.task_ingest_search_trends",
            "schedule": crontab(hour=6, minute=0),
        },
        # ── Every day at 7 AM UTC: run scoring pipeline ──────────────────────
        "daily-scoring": {
            "task":     "app.services.scheduler.task_run_scoring",
            "schedule": crontab(hour=7, minute=0),
        },
        # ── Every Monday at 4 AM UTC: re-index runway shows ──────────────────
        "weekly-runway-ingest": {
            "task":     "app.services.scheduler.task_ingest_runway",
            "schedule": crontab(hour=4, minute=0, day_of_week="monday"),
        },
    },
)


# ── Helper to run async functions from Celery (sync context) ─────────────────
def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.services.scheduler.task_ingest_search_trends", bind=True, max_retries=3)
def task_ingest_search_trends(self):
    """Daily: Pull Google Trends for all tracked keywords."""
    from app.db.session import AsyncSessionLocal
    from app.services.search_trends import ingest_search_trends

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await ingest_search_trends(db, season=settings.ACTIVE_SEASON)
            logger.info(f"[Scheduler] Search ingest: {result}")
            return result

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[Scheduler] Search ingest failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * 30)  # retry in 30min


@celery_app.task(name="app.services.scheduler.task_run_scoring", bind=True, max_retries=2)
def task_run_scoring(self):
    """Daily: Recompute all trend scores."""
    from app.db.session import AsyncSessionLocal
    from app.services.trend_scorer import run_scoring_pipeline

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await run_scoring_pipeline(db, settings.ACTIVE_SEASON)
            logger.info(f"[Scheduler] Scoring: {result}")
            return result

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[Scheduler] Scoring failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * 10)


@celery_app.task(name="app.services.scheduler.task_ingest_runway", bind=True, max_retries=2)
def task_ingest_runway(self):
    """Weekly: Re-index runway shows from Tagwalk."""
    from app.db.session import AsyncSessionLocal
    from app.services.ingestion import ingest_season

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await ingest_season(
                db,
                season=settings.ACTIVE_SEASON,
                cities=settings.active_cities_list,
                tag_images=True,
            )
            logger.info(f"[Scheduler] Runway ingest: {result}")
            return result

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(f"[Scheduler] Runway ingest failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * 60)  # retry in 1hr
