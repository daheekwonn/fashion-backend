"""
services/trend_scorer.py
────────────────────────
The core scoring engine.  Given raw signals (runway look counts,
Google Trends search index, social velocity), it produces a single
composite TrendScore (0–100) for each TrendItem.

Scoring formula
───────────────
  composite = w_runway * runway_score
            + w_search * search_score
            + w_social * social_score

Each sub-score is first computed in its natural unit, then
normalised to 0–100 using a configurable strategy:
  • runway_score  — frequency across looks, normalised by season max
  • search_score  — direct from Google Trends (already 0–100)
  • social_score  — hashtag velocity, log-normalised

Trend delta (momentum)
──────────────────────
  delta = (today - yesterday) / yesterday * 100   (% change)
  is_rising = delta > RISING_THRESHOLD
"""
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import TrendItem, TrendScore, Look, Show, SearchSignal

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Constants ────────────────────────────────────────────────────────────────
RISING_THRESHOLD = 5.0       # % delta to be flagged as "rising"
MIN_LOOK_COUNT   = 2         # ignore items seen in fewer than N looks
SCORE_FLOOR      = 0.0
SCORE_CEIL       = 100.0


# ─────────────────────────────────────────────────────────────────────────────
#  Normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_linear(value: float, max_val: float) -> float:
    """Scale value to 0–100 linearly against a known maximum."""
    if max_val == 0:
        return 0.0
    return min(SCORE_CEIL, max(SCORE_FLOOR, (value / max_val) * 100))


def _normalise_log(value: float, scale: float = 1000.0) -> float:
    """Log-normalise a raw count/velocity to 0–100."""
    if value <= 0:
        return 0.0
    return min(SCORE_CEIL, (math.log1p(value) / math.log1p(scale)) * 100)


def _clamp(value: float) -> float:
    return min(SCORE_CEIL, max(SCORE_FLOOR, value))


# ─────────────────────────────────────────────────────────────────────────────
#  Runway signal aggregation
# ─────────────────────────────────────────────────────────────────────────────

async def aggregate_runway_signals(
    db: AsyncSession,
    season: str,
) -> Dict[str, Dict]:
    """
    Count how many looks (and distinct shows) each tagged item
    appears in for the given season.

    Returns:
        {
          "linen":      {"look_count": 42, "show_count": 8},
          "gorpcore":   {"look_count": 17, "show_count": 5},
          ...
        }
    """
    # Fetch all looks for this season
    result = await db.execute(
        select(Look)
        .join(Show, Look.show_id == Show.id)
        .where(Show.season == season)
    )
    looks: List[Look] = result.scalars().all()

    aggregates: Dict[str, Dict] = {}

    def _record(name: str, show_id: int):
        name = name.lower().strip()
        if not name:
            return
        if name not in aggregates:
            aggregates[name] = {"look_count": 0, "show_ids": set()}
        aggregates[name]["look_count"] += 1
        aggregates[name]["show_ids"].add(show_id)

    for look in looks:
        for field in ["materials", "silhouettes", "colors", "color_names",
                      "accessories", "patterns"]:
            tags = getattr(look, field) or []
            for tag in tags:
                _record(tag, look.show_id)

    # Convert sets to counts
    for name, data in aggregates.items():
        data["show_count"] = len(data.pop("show_ids"))

    return aggregates


# ─────────────────────────────────────────────────────────────────────────────
#  Search signal aggregation
# ─────────────────────────────────────────────────────────────────────────────

async def get_search_index(
    db: AsyncSession,
    keyword: str,
    days: int = 7,
) -> float:
    """
    Returns the average Google Trends value for the last N days.
    Value is already 0–100.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(func.avg(SearchSignal.value))
        .where(SearchSignal.keyword == keyword.lower())
        .where(SearchSignal.date >= cutoff)
    )
    avg = result.scalar()
    return float(avg) if avg is not None else 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Social signal (placeholder — wire to Instagram / TikTok API)
# ─────────────────────────────────────────────────────────────────────────────

async def get_social_velocity(keyword: str) -> float:
    """
    Returns a 0–100 social velocity score.

    PRODUCTION: Replace the stub below with a call to:
      - Instagram Graph API  (/ig_hashtag_search → media_count delta)
      - TikTok Research API  (hashtag view count growth)

    For now, returns a deterministic stub so the scorer still runs.
    """
    # TODO: implement real API calls
    # Example structure:
    #
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(
    #         "https://graph.instagram.com/ig_hashtag_search",
    #         params={"q": keyword, "access_token": IG_TOKEN}
    #     )
    #     hashtag_id = resp.json()["data"][0]["id"]
    #     media = await client.get(
    #         f"https://graph.instagram.com/{hashtag_id}",
    #         params={"fields": "media_count", "access_token": IG_TOKEN}
    #     )
    #     media_count = media.json()["media_count"]
    #     return _normalise_log(media_count)

    return 0.0   # stub


# ─────────────────────────────────────────────────────────────────────────────
#  Composite scorer
# ─────────────────────────────────────────────────────────────────────────────

def compute_composite_score(
    runway_score: float,
    search_score: float,
    social_score: float,
    weights: Optional[Tuple[float, float, float]] = None,
) -> float:
    """
    Weighted average of the three sub-scores.

    weights: (w_runway, w_search, w_social) — default from settings.
    """
    if weights is None:
        w_r = settings.WEIGHT_RUNWAY
        w_s = settings.WEIGHT_SEARCH
        w_so = settings.WEIGHT_SOCIAL
    else:
        w_r, w_s, w_so = weights

    # Normalise weights in case they don't sum to 1
    total_w = w_r + w_s + w_so
    if total_w == 0:
        return 0.0
    w_r, w_s, w_so = w_r / total_w, w_s / total_w, w_so / total_w

    composite = (
        w_r  * _clamp(runway_score)  +
        w_s  * _clamp(search_score)  +
        w_so * _clamp(social_score)
    )
    return round(_clamp(composite), 2)


def compute_trend_delta(current: float, previous: float) -> float:
    """Percentage change from previous to current score."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Full scoring pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def run_scoring_pipeline(db: AsyncSession, season: str) -> Dict:
    """
    Main entry point — runs the complete scoring cycle for a season:

    1. Aggregate runway tag counts from indexed looks
    2. Pull search index from stored SearchSignals
    3. Get social velocity for each item
    4. Compute & persist composite TrendScores
    5. Update TrendItem.trend_score, trend_delta, is_rising

    Returns a summary dict suitable for the /api/trends/run-scoring endpoint.
    """
    logger.info(f"[Scorer] Starting pipeline for season={season}")
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Step 1: Runway aggregation ───────────────────────────────────────────
    runway_data = await aggregate_runway_signals(db, season)
    if not runway_data:
        logger.warning("[Scorer] No runway data found — index some shows first.")
        return {"status": "no_data", "scored": 0}

    max_look_count = max((v["look_count"] for v in runway_data.values()), default=1)
    logger.info(f"[Scorer] {len(runway_data)} distinct items found, max_looks={max_look_count}")

    scored_count = 0
    results = []

    # ── Step 2–5: Score each item ────────────────────────────────────────────
    for item_name, runway in runway_data.items():
        if runway["look_count"] < MIN_LOOK_COUNT:
            continue

        # Fetch or create TrendItem
        result = await db.execute(
            select(TrendItem).where(
                TrendItem.name == item_name,
                TrendItem.season == season,
            )
        )
        item: Optional[TrendItem] = result.scalar_one_or_none()
        if item is None:
            item = TrendItem(name=item_name, category="material", season=season)
            db.add(item)
            await db.flush()

        # Sub-scores
        runway_score = _normalise_linear(runway["look_count"], max_look_count)
        search_score = await get_search_index(db, item_name)
        social_score = await get_social_velocity(item_name)

        composite = compute_composite_score(runway_score, search_score, social_score)

        # Delta vs yesterday
        prev_score = item.trend_score or 0.0
        delta = compute_trend_delta(composite, prev_score)

        # Update TrendItem
        item.runway_count      = runway["look_count"]
        item.runway_show_count = runway["show_count"]
        item.search_index      = search_score
        item.social_velocity   = social_score
        item.trend_score_prev  = prev_score
        item.trend_score       = composite
        item.trend_delta       = delta
        item.is_rising         = delta > RISING_THRESHOLD
        item.last_scored_at    = today

        # Persist daily snapshot
        existing = await db.execute(
            select(TrendScore).where(
                TrendScore.item_id == item.id,
                TrendScore.date == today,
            )
        )
        snap: Optional[TrendScore] = existing.scalar_one_or_none()
        if snap is None:
            snap = TrendScore(item_id=item.id, date=today)
            db.add(snap)

        snap.runway_score = runway_score
        snap.search_score = search_score
        snap.social_score = social_score
        snap.composite    = composite

        scored_count += 1
        results.append({
            "name":         item_name,
            "composite":    composite,
            "runway_score": round(runway_score, 1),
            "search_score": round(search_score, 1),
            "social_score": round(social_score, 1),
            "delta":        delta,
            "is_rising":    delta > RISING_THRESHOLD,
        })

    await db.commit()

    # Sort by composite descending for the summary
    results.sort(key=lambda x: x["composite"], reverse=True)
    logger.info(f"[Scorer] Pipeline complete — scored {scored_count} items.")

    return {
        "status":     "ok",
        "season":     season,
        "scored":     scored_count,
        "scored_at":  today.isoformat(),
        "top_10":     results[:10],
    }
