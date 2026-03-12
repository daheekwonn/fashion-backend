# app/services/search_trends.py
#
# Pulls Google Trends data for FW26 fashion keywords via pytrends.
# Writes results into the SearchSignal table in Railway PostgreSQL.
# Called by POST /api/trends/ingest/search
#
# pytrends has no API key — it scrapes Google Trends directly.
# Rate limits apply: we batch keywords (max 5 per request) and add
# delays between requests to avoid being blocked.
#
# Keywords are intentionally broad — we track trend CATEGORIES, not
# specific runway pieces. "leather outerwear" captures bombers, bikers,
# blazers, and motos from any show. This makes signals more durable
# and avoids false negatives when terminology varies by brand.

import asyncio
import logging
from datetime import datetime, timezone

from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models.database import SearchSignal

logger = logging.getLogger(__name__)


# ── FW26 keyword groups ────────────────────────────────────────────────────────
# Rules:
#   - Max 5 keywords per group (pytrends hard limit)
#   - Keep terms broad enough to capture the category, not one specific piece
#   - Each group is one HTTP request — related terms compare better within a group
#   - Values are relative within a group (0-100), keep groups thematically tight

FW26_KEYWORD_GROUPS: list[list[str]] = [

    # Outerwear categories (not specific pieces)
    # "leather outerwear" catches bombers, bikers, blazers, motos all at once
    # "shearling" catches coats, vests, and liners
    ["leather outerwear", "shearling coat", "oversized coat", "trench coat women", "fur coat trend"],

    # Dress silhouettes
    # "prairie dress" and "cottage dress" both capture the romantic/rustic wave
    # "column dress" and "slip dress" cover the minimal/sleek counter-signal
    ["prairie dress", "cottage dress trend", "maxi dress 2026", "column dress", "slip dress outfit"],

    # Tailoring & trousers
    ["wide leg trousers", "pleated trousers", "tailored suit women", "pinstripe trousers", "barrel leg jeans"],

    # Footwear
    ["ballet flats outfit", "mary jane heels", "kitten heel shoes", "knee high boots", "loafers outfit women"],

    # Colour signals — spike when a shade dominates a season, strong leading indicator
    ["burgundy outfit", "chocolate brown fashion", "ivory cream outfit", "forest green coat", "camel coat"],

    # Bag & accessory categories
    ["shoulder bag outfit", "oversized tote bag", "mini bag trend", "leather belt bag", "bucket bag fashion"],

    # Show-level brand searches
    # High velocity = the show broke through culturally, not just within industry
    ["Chanel Fall 2026", "Dior Fall 2026", "Gucci Fall 2026", "Chloe Fall 2026", "Bottega Veneta 2026"],

    # Material signals
    ["velvet fashion", "boucle jacket", "satin dress trend", "lace fashion 2026", "knit dress outfit"],

    # Aesthetic/mood searches (upstream signal — often leads runway by 1 season)
    ["quiet luxury fashion", "romantic fashion aesthetic", "dark academia outfit", "coastal grandmother style", "balletcore outfit"],
]

# Last 90 days captures the full FW26 show season and consumer reaction
TIMEFRAME = "today 3-m"
GEO = ""  # worldwide; swap to "US" or "GB" to narrow


# ── Main ingest function ───────────────────────────────────────────────────────

async def ingest_search_signals() -> dict:
    """
    Pull Google Trends data for all FW26 keyword groups and write
    SearchSignal rows to the database. Returns a summary dict.

    Called by: POST /api/trends/ingest/search
    """
    pt = TrendReq(
        hl="en-US",
        tz=0,
        timeout=(10, 25),
        retries=3,
        backoff_factor=1.5,
    )

    all_rows: list[dict] = []
    errors: list[str] = []

    for i, keywords in enumerate(FW26_KEYWORD_GROUPS):
        logger.info(f"Fetching group {i + 1}/{len(FW26_KEYWORD_GROUPS)}: {keywords}")
        try:
            rows = await _fetch_group(pt, keywords)
            all_rows.extend(rows)
            logger.info(f"  -> {len(rows)} rows returned")
        except ResponseError as e:
            msg = f"ResponseError on group {keywords}: {e}"
            logger.warning(msg)
            errors.append(msg)
        except Exception as e:
            msg = f"Unexpected error on group {keywords}: {e}"
            logger.error(msg, exc_info=True)
            errors.append(msg)

        # Polite delay — pytrends is rate-limited aggressively
        if i < len(FW26_KEYWORD_GROUPS) - 1:
            await asyncio.sleep(4)

    saved = 0
    if all_rows:
        saved = await _save_signals(all_rows)

    summary = {
        "status": "ok" if not errors else "partial",
        "groups_processed": len(FW26_KEYWORD_GROUPS),
        "keywords_processed": sum(len(g) for g in FW26_KEYWORD_GROUPS),
        "rows_saved": saved,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"Search ingest complete: {summary}")
    return summary


# ── Fetch one keyword group ────────────────────────────────────────────────────

async def _fetch_group(pt: TrendReq, keywords: list[str]) -> list[dict]:
    """
    Fetch interest-over-time for up to 5 keywords.
    Returns one row per keyword per date — matching the SearchSignal schema
    (keyword, date, value, geo).
    pytrends is synchronous — run in executor to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()

    def _sync_fetch():
        pt.build_payload(keywords, cat=0, timeframe=TIMEFRAME, geo=GEO, gprop="")
        return pt.interest_over_time()

    iot = await loop.run_in_executor(None, _sync_fetch)

    if iot is None or iot.empty:
        logger.warning(f"Empty response for group: {keywords}")
        return []

    rows = []
    for keyword in keywords:
        if keyword not in iot.columns:
            continue
        series = iot[keyword]
        for date, value in series.items():
            rows.append({
                "keyword": keyword,
                "date":    datetime(date.year, date.month, date.day, tzinfo=timezone.utc),
                "value":   float(value),
                "geo":     GEO,
            })

    return rows


# ── Save to database ───────────────────────────────────────────────────────────

async def _save_signals(rows: list[dict]) -> int:
    """
    Upsert rows into search_signals.
    Uses ON CONFLICT DO UPDATE so re-running ingest refreshes values
    without creating duplicates (unique constraint: keyword + date + geo).
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = pg_insert(SearchSignal).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_search_keyword_date_geo",
                set_={"value": stmt.excluded.value},
            )
            await session.execute(stmt)

    return len(rows)


# ── Score helper for trend_scorer.py ──────────────────────────────────────────

async def get_search_score_for_keyword(keyword: str) -> float:
    """
    Returns a normalised 0-100 search score for a given keyword.
    Used by trend_scorer.py for the 30% search component.

    Method:
      - Pull the last ~8 weeks of rows for this keyword
      - Current score  = average of last 2 data points  (60% weight)
      - Velocity score = % change vs the prior 6 weeks  (40% weight)
      - Blend and clamp to 0-100
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SearchSignal)
            .where(SearchSignal.keyword == keyword, SearchSignal.geo == GEO)
            .order_by(SearchSignal.date.desc())
            .limit(56)  # ~8 weeks of weekly data points
        )
        rows = result.scalars().all()

    if not rows:
        return 0.0

    values = [r.value for r in rows]  # newest first

    recent   = sum(values[:2]) / max(len(values[:2]), 1)
    baseline = sum(values[2:8]) / max(len(values[2:8]), 1)
    velocity = ((recent - baseline) / max(baseline, 1)) * 100

    current_component  = recent * 0.6
    velocity_clamped   = max(-50.0, min(100.0, velocity))
    velocity_component = ((velocity_clamped + 50) / 150) * 40

    return round(min(100.0, current_component + velocity_component), 2)


async def get_all_search_signals() -> list[dict]:
    """
    Returns the latest value per keyword — used by GET /api/trends/keywords.
    """
    async with AsyncSessionLocal() as session:
        latest_result = await session.execute(
            select(SearchSignal.date).order_by(SearchSignal.date.desc()).limit(1)
        )
        latest_date = latest_result.scalar()

        if not latest_date:
            return []

        result = await session.execute(
            select(SearchSignal)
            .where(SearchSignal.date == latest_date, SearchSignal.geo == GEO)
            .order_by(SearchSignal.value.desc())
        )
        rows = result.scalars().all()

    return [
        {
            "keyword": r.keyword,
            "value":   r.value,
            "date":    r.date.isoformat() if r.date else None,
            "geo":     r.geo,
        }
        for r in rows
    ]
