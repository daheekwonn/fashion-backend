from app.services.news_trends import get_news_signal
from app.services.reddit_trends import get_reddit_signal
# app/services/trend_scorer.py
#
# Computes composite trend scores for TrendItems (broad categories)
# and ranks TrendSubItems (specific pieces) within each category.
#
# Formula:
#   TrendItem composite = 0.5 * runway_score + 0.3 * search_score + 0.2 * social_score
#
# Runway score is derived by counting actual Look rows whose Vision tags
# match each TrendItem's keyword list.
#
# Called by: POST /api/trends/run-scoring

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.database import TrendItem, TrendSubItem, TrendScore, Look, SearchSignal
from app.services.search_trends import get_search_score_for_keyword

logger = logging.getLogger(__name__)

# Scoring weights — must sum to 1.0
WEIGHT_RUNWAY = 0.50
WEIGHT_SEARCH = 0.30
WEIGHT_SOCIAL = 0.20


# ── Keyword mapping: TrendItem name → Vision tag keywords ─────────────────────
# These keywords are matched against Look.materials, Look.silhouettes,
# Look.color_names to count how many looks belong to each trend.

TREND_KEYWORDS = {
    "Leather Outerwear": ["leather", "biker jacket", "leather jacket", "leather coat", "leather blazer"],
    "Shearling":         ["shearling", "sheepskin", "sherpa", "fur", "fluffy"],
    "Oversized Coat":    ["overcoat", "coat", "outerwear", "oversized"],
    "Trench Coat":       ["trench", "raincoat", "trenchcoat"],
    "Prairie Silhouette":["prairie", "tiered", "ruffle", "floral", "cottagecore", "boho"],
    "Column Dress":      ["column dress", "slip dress", "minimal dress", "tube dress"],
    "Slip Dress":        ["slip", "satin dress", "bias cut"],
    "Wide-Leg Tailoring":["wide leg", "palazzo", "flared trousers", "wide trousers"],
    "Pleated Trousers":  ["pleated", "pleated trousers", "pleat"],
    "Power Suiting":     ["suit", "blazer", "pantsuit", "power suit", "suiting"],
    "Ballet Flats":      ["ballet flat", "ballerina", "pointed flat", "ballet shoe"],
    "Mary Janes":        ["mary jane", "mary-jane", "strap heel"],
    "Kitten Heels":      ["kitten heel", "low heel", "block heel"],
    "Knee-High Boots":   ["knee-high boot", "tall boot", "over the knee", "riding boot"],
    "Velvet":            ["velvet"],
    "Boucle":            ["boucle", "bouclé", "tweed", "textured wool"],
    "Satin":             ["satin", "silk", "lustrous", "shiny fabric"],
    "Lace":              ["lace", "lace trim", "lacework"],
    "Burgundy":          ["burgundy", "wine red", "bordeaux"],
    "Chocolate Brown":   ["chocolate brown", "dark brown", "mocha brown"],
    "Ivory & Cream":     ["ivory", "cream", "off-white", "ecru"],
    "Forest Green":      ["forest green", "dark green", "emerald green"],
    "Camel":             ["camel"],
}


# ── Count looks per trend from Vision tags ────────────────────────────────────

async def _count_looks_per_trend(session) -> dict:
    """
    Count Look rows whose Vision tags (materials, silhouettes, color_names)
    match each TrendItem's keywords. Returns dict of:
        { trend_name: { "count": int, "show_count": int } }
    """
    result = await session.execute(select(Look))
    looks = result.scalars().all()

    counts = {name: {"count": 0, "shows": set()} for name in TREND_KEYWORDS}

    for look in looks:
        # Build a single lowercased string of all tags for this look
        all_tags = []
        if look.materials:
            all_tags.extend([t.lower() for t in look.materials])
        if look.silhouettes:
            all_tags.extend([t.lower() for t in look.silhouettes])
        if look.color_names:
            all_tags.extend([t.lower() for t in look.color_names])

        tags_str = " ".join(all_tags)
        if not tags_str.strip():
            continue

        for trend_name, keywords in TREND_KEYWORDS.items():
            if any(kw.lower() in tags_str for kw in keywords):
                counts[trend_name]["count"] += 1
                counts[trend_name]["shows"].add(look.show_id)

    return {
        k: {"count": v["count"], "show_count": len(v["shows"])}
        for k, v in counts.items()
    }


# ── Main scoring function ──────────────────────────────────────────────────────

async def run_scoring_pipeline() -> dict:
    """
    Score all TrendItems and re-rank all TrendSubItems.
    Writes updated scores back to the database and saves a TrendScore snapshot.

    Called by: POST /api/trends/run-scoring
    """
    async with AsyncSessionLocal() as session:
        # Count looks per trend from Vision tags
        logger.info("Counting looks per trend from Vision tags...")
        look_counts = await _count_looks_per_trend(session)
        logger.info(f"Look counts: { {k: v['count'] for k, v in look_counts.items() if v['count'] > 0} }")

        result = await session.execute(
            select(TrendItem).options(selectinload(TrendItem.sub_items))
        )
        items: list[TrendItem] = result.scalars().all()

    # Inject Vision-derived runway counts before scoring
    for item in items:
        if item.name in look_counts:
            lc = look_counts[item.name]
            if lc["count"] > 0:
                item.runway_count = lc["count"]
                item.runway_show_count = lc["show_count"]
                logger.info(f"  {item.name}: {lc['count']} looks across {lc['show_count']} shows")

    scored = 0
    errors = []

    for item in items:
        try:
            await _score_item(item)
            scored += 1
        except Exception as e:
            msg = f"Error scoring {item.name}: {e}"
            logger.error(msg, exc_info=True)
            errors.append(msg)

    return {
        "status": "ok" if not errors else "partial",
        "items_scored": scored,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Score a single TrendItem ───────────────────────────────────────────────────

async def _score_item(item: TrendItem) -> None:
    """
    Compute and save the composite score for one TrendItem.
    Also re-ranks its sub-items by runway_count.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrendItem)
            .where(TrendItem.id == item.id)
            .options(selectinload(TrendItem.sub_items))
        )
        db_item: TrendItem = result.scalars().first()
        if not db_item:
            return

        # Use the runway_count injected by run_scoring_pipeline()
        # (already updated on the item object before this function is called)
        total_runway = item.runway_count or db_item.runway_count or 0
        total_shows  = item.runway_show_count or db_item.runway_show_count or 0

        # Sync injected counts to db_item
        db_item.runway_count      = total_runway
        db_item.runway_show_count = total_shows

        # ── 1. Runway score (0-100) ───────────────────────────────────────────
        # 60+ looks across 8+ shows = score of 100
        look_score = min(100.0, (total_runway / 200) * 100)
        show_score = min(100.0, (total_shows  / 30) * 100)
        runway_score = round((look_score * 0.6) + (show_score * 0.4), 2)

        # ── 2. Search score (0-100) ───────────────────────────────────────────
        keyword = db_item.search_keyword or db_item.name.lower()
        search_score = await get_search_score_for_keyword(keyword)

        # ── 3. Social score (0-100) ───────────────────────────────────────────
        social_score = db_item.social_score or 0.0

        # ── 4. Composite ─────────────────────────────────────────────────────
        composite = round(
            (runway_score  * WEIGHT_RUNWAY) +
            (search_score  * WEIGHT_SEARCH) +
            (social_score  * WEIGHT_SOCIAL),
            2
        )

        # ── 5. Delta ─────────────────────────────────────────────────────────
        prev_score               = db_item.trend_score or 0.0
        db_item.trend_score_prev = prev_score
        db_item.trend_delta      = round(composite - prev_score, 2)
        db_item.is_rising        = composite > prev_score

        # ── 6. Write scores back ──────────────────────────────────────────────
        db_item.runway_score   = runway_score
        db_item.search_score   = search_score
        db_item.trend_score    = composite
        db_item.last_scored_at = datetime.now(timezone.utc)

        # ── 7. Snapshot for time-series chart ────────────────────────────────
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(TrendScore).values(
            item_id      = db_item.id,
            date         = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
            runway_score = runway_score,
            search_score = search_score,
            social_score = social_score,
            composite    = composite,
        ).on_conflict_do_update(
            constraint="uq_score_item_date",
            set_={
                "runway_score": runway_score,
                "search_score": search_score,
                "social_score": social_score,
                "composite":    composite,
            }
        )
        await session.execute(stmt)

        # ── 8. Re-rank sub-items by runway_count ─────────────────────────────
        if db_item.sub_items:
            sorted_subs = sorted(db_item.sub_items, key=lambda s: s.runway_count, reverse=True)
            for rank, sub in enumerate(sorted_subs, start=1):
                sub.rank = rank
                if sub.search_keyword:
                    sub.search_score = await get_search_score_for_keyword(sub.search_keyword)

        await session.commit()
        logger.info(
            f"Scored {db_item.name}: runway={runway_score} "
            f"search={search_score} social={social_score} "
            f"composite={composite} delta={db_item.trend_delta:+.2f}"
        )


# ── API response helpers ───────────────────────────────────────────────────────

async def get_leaderboard(season: str = "FW26", limit: int = 10) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrendItem)
            .where(TrendItem.season == season)
            .order_by(TrendItem.trend_score.desc())
            .limit(limit)
        )
        items = result.scalars().all()

    return [
        {
            "id":                item.id,
            "rank":              i + 1,
            "name":              item.name,
            "category":          item.category,
            "season":            item.season,
            "trend_score":       item.trend_score,
            "runway_score":      item.runway_score,
            "search_score":      item.search_score,
            "social_score":      item.social_score,
            "runway_count":      item.runway_count,
            "runway_show_count": item.runway_show_count,
            "trend_delta":       item.trend_delta,
            "is_rising":         item.is_rising,
            "last_scored_at":    item.last_scored_at.isoformat() if item.last_scored_at else None,
        }
        for i, item in enumerate(items)
    ]


async def get_trend_detail(item_id: int) -> dict | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrendItem)
            .where(TrendItem.id == item_id)
            .options(selectinload(TrendItem.sub_items))
        )
        item: TrendItem = result.scalars().first()

    if not item:
        return None

    verified_subs = [s for s in item.sub_items if s.verified]
    subs_to_show  = verified_subs if verified_subs else item.sub_items

    return {
        "id":                item.id,
        "name":              item.name,
        "category":          item.category,
        "season":            item.season,
        "trend_score":       item.trend_score,
        "runway_score":      item.runway_score,
        "search_score":      item.search_score,
        "social_score":      item.social_score,
        "runway_count":      item.runway_count,
        "runway_show_count": item.runway_show_count,
        "trend_delta":       item.trend_delta,
        "is_rising":         item.is_rising,
        "breakdown": [
            {
                "rank":         sub.rank,
                "name":         sub.name,
                "runway_count": sub.runway_count,
                "runway_shows": sub.runway_shows or [],
                "search_score": sub.search_score,
                "source":       sub.source,
                "verified":     sub.verified,
                "notes":        sub.notes,
            }
            for sub in sorted(subs_to_show, key=lambda s: s.rank)
        ],
    }


async def get_all_trends_with_breakdown(season: str = "FW26") -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrendItem)
            .where(TrendItem.season == season)
            .options(selectinload(TrendItem.sub_items))
            .order_by(TrendItem.trend_score.desc())
        )
        items = result.scalars().all()

    return [
        {
            "id":           item.id,
            "rank":         i + 1,
            "name":         item.name,
            "category":     item.category,
            "trend_score":  item.trend_score,
            "trend_delta":  item.trend_delta,
            "is_rising":    item.is_rising,
            "runway_count": item.runway_count,
            "search_score": item.search_score,
            "breakdown": [
                {
                    "rank":         sub.rank,
                    "name":         sub.name,
                    "runway_count": sub.runway_count,
                    "runway_shows": sub.runway_shows or [],
                    "verified":     sub.verified,
                    "source":       sub.source,
                }
                for sub in sorted(item.sub_items, key=lambda s: s.rank)
                if sub.verified or not any(s.verified for s in item.sub_items)
            ],
        }
        for i, item in enumerate(items)
    ]
