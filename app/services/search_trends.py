"""
services/search_trends.py
─────────────────────────
Pulls Google Trends data for fashion keywords using pytrends
and stores it in the SearchSignal table.

Limitations of pytrends:
  - Unofficial library (scrapes Google Trends)
  - Rate-limited — batch keywords in groups of 5 max
  - Returns relative values (0–100), not absolute search volumes
  - Use with backoff to avoid 429s
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from pytrends.request import TrendReq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.database import SearchSignal, TrendItem

logger = logging.getLogger(__name__)

# Pytrends timeframe options:
#   "today 3-m"  = last 90 days
#   "today 12-m" = last 12 months
#   "today 5-y"  = last 5 years
DEFAULT_TIMEFRAME = "today 3-m"
BATCH_SIZE = 5       # Google Trends max keywords per request
REQUEST_DELAY = 2.0  # seconds between batches (avoid rate limiting)


# ─────────────────────────────────────────────────────────────────────────────
#  Core pytrends fetch (sync — runs in thread pool)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_trends_sync(
    keywords: List[str],
    timeframe: str = DEFAULT_TIMEFRAME,
    geo: str = "",
) -> dict:
    """
    Synchronous pytrends call — call via asyncio.to_thread() to avoid
    blocking the async event loop.

    Returns dict: { "keyword": [(date, value), ...], ... }
    """
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    pytrends.build_payload(keywords, cat=185, timeframe=timeframe, geo=geo)
    # cat=185 = "Shopping > Apparel" — scopes results to fashion searches
    df = pytrends.interest_over_time()

    result = {}
    if df.empty:
        return result

    for kw in keywords:
        if kw not in df.columns:
            continue
        result[kw] = [
            (row.Index.to_pydatetime(), float(row[kw]))
            for row in df.itertuples()
            if row.isPartial == False  # noqa: E712 — pytrends uses 0/1
        ]

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  DB persistence
# ─────────────────────────────────────────────────────────────────────────────

async def save_search_signals(
    db: AsyncSession,
    keyword: str,
    data_points: list,
    geo: str = "",
) -> int:
    """Upsert (keyword, date, geo) rows into search_signals."""
    saved = 0
    for date, value in data_points:
        # Normalize to UTC date-only
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        date = date.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(SearchSignal).where(
                SearchSignal.keyword == keyword.lower(),
                SearchSignal.date == date,
                SearchSignal.geo == geo,
            )
        )
        signal: Optional[SearchSignal] = result.scalar_one_or_none()

        if signal is None:
            signal = SearchSignal(keyword=keyword.lower(), date=date, geo=geo)
            db.add(signal)

        signal.value = value
        saved += 1

    return saved


# ─────────────────────────────────────────────────────────────────────────────
#  Batch ingestion pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def ingest_search_trends(
    db: AsyncSession,
    keywords: Optional[List[str]] = None,
    season: Optional[str] = None,
    timeframe: str = DEFAULT_TIMEFRAME,
    geo: str = "",
) -> dict:
    """
    Main entry point.

    If keywords is None, loads them from the TrendItems table for the season.
    Fetches Google Trends data in batches of 5 and stores in SearchSignal.

    Usage:
        # From the API endpoint:
        await ingest_search_trends(db, season="FW26")

        # Or with explicit keywords:
        await ingest_search_trends(db, keywords=["linen", "gorpcore"])
    """
    # Load keywords from DB if not provided
    if keywords is None:
        if season is None:
            raise ValueError("Provide either keywords or a season.")
        result = await db.execute(
            select(TrendItem.name).where(TrendItem.season == season)
        )
        keywords = [row[0] for row in result.all()]

    if not keywords:
        logger.warning("[SearchTrends] No keywords to fetch.")
        return {"status": "no_keywords", "fetched": 0}

    logger.info(f"[SearchTrends] Fetching trends for {len(keywords)} keywords")

    total_saved = 0
    errors = []

    # Process in batches of BATCH_SIZE
    for i in range(0, len(keywords), BATCH_SIZE):
        batch = keywords[i : i + BATCH_SIZE]
        logger.debug(f"[SearchTrends] Batch {i//BATCH_SIZE + 1}: {batch}")

        try:
            data = await asyncio.to_thread(
                _fetch_trends_sync, batch, timeframe, geo
            )
        except Exception as e:
            logger.error(f"[SearchTrends] Batch failed: {e}")
            errors.append({"batch": batch, "error": str(e)})
            await asyncio.sleep(REQUEST_DELAY * 3)
            continue

        for kw, points in data.items():
            saved = await save_search_signals(db, kw, points, geo)
            total_saved += saved
            logger.debug(f"[SearchTrends] Saved {saved} points for '{kw}'")

        await db.commit()
        await asyncio.sleep(REQUEST_DELAY)  # rate limit protection

    logger.info(f"[SearchTrends] Done — {total_saved} data points saved.")
    return {
        "status":  "ok",
        "keywords": len(keywords),
        "points_saved": total_saved,
        "errors":  errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience: fetch trends for specific fashion show keywords
# ─────────────────────────────────────────────────────────────────────────────

FW26_SEED_KEYWORDS = [
    # Materials
    "linen fashion", "organza dress", "denim jacket", "leather coat",
    "velvet suit", "mesh top", "tweed jacket", "shearling coat",
    # Silhouettes / styles
    "quiet luxury", "gorpcore", "ballet core", "moto aesthetic",
    "oversized blazer", "sculptural dress", "column silhouette",
    # Colors
    "sage green fashion", "ivory outfit", "cobalt blue dress",
    # Accessories
    "sculptural bag", "knee high boots", "statement belt",
]


async def ingest_fw26_seed_keywords(db: AsyncSession) -> dict:
    """Kick off search trend ingestion for known FW26 keywords."""
    return await ingest_search_trends(
        db,
        keywords=FW26_SEED_KEYWORDS,
        timeframe="today 3-m",
        geo="",   # worldwide
    )
