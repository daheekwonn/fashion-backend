"""
routers/trends.py — REST endpoints for trend data

GET  /api/trends/leaderboard        → top TrendItems by composite score (homepage)
GET  /api/trends/all                → all TrendItems with sub-item breakdowns (/trends page)
GET  /api/trends/{id}/breakdown     → single TrendItem + ranked sub-items
GET  /api/trends/{id}/history       → time-series score history for charts
GET  /api/trends/keywords           → raw search signals (tag cloud / keyword list)
GET  /api/trends/colors             → trending colors
GET  /api/trends/materials          → trending materials
GET  /api/trends/shows              → indexed runway shows
POST /api/trends/run-scoring        → trigger scoring pipeline
POST /api/trends/ingest/search      → trigger Google Trends ingestion
POST /api/trends/ingest/runway      → trigger runway ingestion (future: Roboflow)
POST /api/trends/ingest/vogue       → scrape Vogue Runway page, seed looks + Vision tag
POST /api/trends/seed/shows         → seed FW26 runway Show rows
POST /api/trends/seed/looks         → manually seed Look rows + Vision tag them
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.config import get_settings
from app.models.database import TrendItem, TrendSubItem, TrendScore, Show
from app.services.trend_scorer import (
    run_scoring_pipeline,
    get_leaderboard,
    get_trend_detail,
    get_all_trends_with_breakdown,
)
from app.services.search_trends import ingest_search_signals

router = APIRouter(prefix="/api/trends", tags=["trends"])
settings = get_settings()


# ── Pydantic response schemas ─────────────────────────────────────────────────

class SubItemOut(BaseModel):
    rank:         int
    name:         str
    runway_count: int
    runway_shows: List[str]
    search_score: float
    source:       str
    verified:     bool
    notes:        Optional[str]


class TrendItemOut(BaseModel):
    id:               int
    rank:             int
    name:             str
    category:         str
    season:           str
    trend_score:      float
    runway_score:     float
    search_score:     float
    social_score:     float
    runway_count:     int
    runway_show_count:int
    trend_delta:      float
    is_rising:        bool
    last_scored_at:   Optional[str]


class TrendDetailOut(BaseModel):
    id:               int
    name:             str
    category:         str
    season:           str
    trend_score:      float
    runway_score:     float
    search_score:     float
    social_score:     float
    runway_count:     int
    runway_show_count:int
    trend_delta:      float
    is_rising:        bool
    breakdown:        List[SubItemOut]


class TrendWithBreakdownOut(BaseModel):
    id:           int
    rank:         int
    name:         str
    category:     str
    trend_score:  float
    trend_delta:  float
    is_rising:    bool
    runway_count: int
    search_score: float
    breakdown:    List[SubItemOut]


class TrendHistoryPoint(BaseModel):
    date:         str
    composite:    float
    runway_score: float
    search_score: float
    social_score: float


class KeywordSignal(BaseModel):
    keyword: str
    value:   float
    date:    Optional[str]
    geo:     str


class ColorSwatch(BaseModel):
    name:  str
    score: float
    delta: float


class MaterialBar(BaseModel):
    name:  str
    score: float
    count: int


# ── Leaderboard — homepage ────────────────────────────────────────────────────

@router.get("/leaderboard", response_model=List[TrendItemOut])
async def get_trend_leaderboard(
    season: str = Query(default=None),
    limit:  int = Query(default=10, le=50),
):
    """
    Top TrendItems by composite score — broad categories for the homepage leaderboard.
    Does NOT include sub-item breakdowns (use /all or /{id}/breakdown for that).
    """
    season = season or settings.ACTIVE_SEASON
    return await get_leaderboard(season=season, limit=limit)


# ── All trends with breakdowns — /trends page ─────────────────────────────────

@router.get("/all", response_model=List[TrendWithBreakdownOut])
async def get_all_trends(
    season: str = Query(default=None),
):
    """
    All TrendItems with their ranked sub-item breakdowns.
    Used by the /trends dashboard page — the data-heavy view.
    """
    season = season or settings.ACTIVE_SEASON
    return await get_all_trends_with_breakdown(season=season)


# ── Single trend detail + breakdown ───────────────────────────────────────────

@router.get("/{item_id}/breakdown", response_model=TrendDetailOut)
async def get_breakdown(item_id: int):
    """
    Single TrendItem with full sub-item breakdown.
    e.g. "Leather Outerwear" → Biker Jacket #1, Blazer #2, Moto Coat #3.
    """
    detail = await get_trend_detail(item_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Trend item not found.")
    return detail


# ── Score history — time-series charts ───────────────────────────────────────

@router.get("/{item_id}/history", response_model=List[TrendHistoryPoint])
async def get_trend_history(
    item_id: int,
    days:    int = Query(default=90, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Daily score history for a single TrendItem — for Recharts time-series."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(TrendScore)
        .where(TrendScore.item_id == item_id)
        .where(TrendScore.date >= cutoff)
        .order_by(TrendScore.date)
    )
    snaps = result.scalars().all()
    if not snaps:
        raise HTTPException(status_code=404, detail="No history found for this item.")
    return [
        TrendHistoryPoint(
            date         = s.date.strftime("%Y-%m-%d"),
            composite    = s.composite,
            runway_score = s.runway_score,
            search_score = s.search_score,
            social_score = s.social_score,
        )
        for s in snaps
    ]


# ── Keywords — raw search signals ─────────────────────────────────────────────

@router.get("/keywords", response_model=List[KeywordSignal])
async def get_trending_keywords(
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Latest search signal value per keyword — for the tag cloud / keyword list.
    Returns the most recent date's values, sorted by search interest.
    """
    from app.services.search_trends import get_all_search_signals
    return await get_all_search_signals()


# ── Materials ─────────────────────────────────────────────────────────────────

@router.get("/materials", response_model=List[MaterialBar])
async def get_material_trends(
    season: str = Query(default=None),
    limit:  int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Top material TrendItems for the horizontal bar chart."""
    season = season or settings.ACTIVE_SEASON
    result = await db.execute(
        select(TrendItem)
        .where(TrendItem.season == season)
        .where(TrendItem.category == "material")
        .order_by(desc(TrendItem.trend_score))
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        MaterialBar(name=i.name, score=i.trend_score, count=i.runway_count)
        for i in items
    ]


# ── Colors ────────────────────────────────────────────────────────────────────

@router.get("/colors", response_model=List[ColorSwatch])
async def get_color_trends(
    season: str = Query(default=None),
    limit:  int = Query(default=12, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Trending color TrendItems for the palette grid."""
    season = season or settings.ACTIVE_SEASON
    result = await db.execute(
        select(TrendItem)
        .where(TrendItem.season == season)
        .where(TrendItem.category == "color")
        .order_by(desc(TrendItem.trend_score))
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        ColorSwatch(name=i.name, score=i.trend_score, delta=i.trend_delta)
        for i in items
    ]


# ── Shows ─────────────────────────────────────────────────────────────────────

@router.get("/shows")
async def list_shows(
    season: str = Query(default=None),
    city:   str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """All indexed runway shows for a season."""
    season = season or settings.ACTIVE_SEASON
    q = select(Show).where(Show.season == season)
    if city:
        q = q.where(Show.city == city)
    q = q.order_by(Show.brand)
    result = await db.execute(q)
    shows = result.scalars().all()
    return [
        {
            "id":          s.id,
            "brand":       s.brand,
            "city":        s.city,
            "season":      s.season,
            "total_looks": s.total_looks,
            "show_date":   s.show_date.isoformat() if s.show_date else None,
        }
        for s in shows
    ]


# ── Admin / pipeline triggers ─────────────────────────────────────────────────

@router.post("/run-scoring")
async def trigger_scoring(background_tasks: BackgroundTasks):
    """
    Trigger the trend scoring pipeline.
    Scores all TrendItems and re-ranks all TrendSubItems.
    Runs in the background — returns immediately.
    """
    background_tasks.add_task(run_scoring_pipeline)
    return {"status": "started", "message": "Scoring pipeline running in background."}


@router.post("/ingest/search")
async def trigger_search_ingest(background_tasks: BackgroundTasks):
    """
    Trigger Google Trends ingestion for all FW26 keyword groups.
    Populates the SearchSignal table. Takes ~2-3 min due to rate limit delays.
    Runs in the background — returns immediately.
    """
    background_tasks.add_task(ingest_search_signals)
    return {"status": "started", "message": "Search ingest running in background. Check logs for progress."}


@router.post("/ingest/runway")
async def trigger_runway_ingest(background_tasks: BackgroundTasks):
    """
    Placeholder for runway ingestion — will trigger Roboflow image tagging pipeline.
    Not yet implemented.
    """
    return {
        "status": "not_implemented",
        "message": "Runway ingestion via Roboflow is pending. Sub-items can be seeded manually via /seed/subitems.",
    }


# ── Seed endpoints (one-time setup) ───────────────────────────────────────────

@router.post("/seed/items")
async def seed_trend_items(db: AsyncSession = Depends(get_db)):
    """
    One-time seed: creates all FW26 TrendItem parent categories.
    Safe to re-run — skips items that already exist.
    """
    from app.services.seed import seed_fw26_items
    result = await seed_fw26_items(db)
    return result


@router.post("/seed/subitems")
async def seed_trend_subitems(db: AsyncSession = Depends(get_db)):
    """
    One-time seed: creates known FW26 TrendSubItems under each parent category.
    Safe to re-run — skips sub-items that already exist.
    """
    from app.services.seed import seed_fw26_subitems
    result = await seed_fw26_subitems(db)
    return result


@router.post("/seed/shows")
async def seed_shows(db: AsyncSession = Depends(get_db)):
    """
    One-time seed: creates FW26 Show rows for all major designers/cities.
    Safe to re-run — skips shows that already exist.
    """
    from app.services.seed import seed_fw26_shows
    result = await seed_fw26_shows(db)
    return result


class SeedLooksBody(BaseModel):
    show_slug:  str
    image_urls: List[str]


@router.post("/seed/looks")
async def seed_looks(body: SeedLooksBody, db: AsyncSession = Depends(get_db)):
    """
    Manually seed Look rows for an existing show and run Vision tagging.

    Body:
        show_slug:  lowercased brand name, hyphens for spaces (e.g. "the-row")
        image_urls: list of image URLs to create as Look rows
    """
    from app.services.manual_seed_looks import seed_looks_for_show
    try:
        result = await seed_looks_for_show(db, body.show_slug, body.image_urls)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


class IngestVogueBody(BaseModel):
    show_slug: str
    vogue_url: str


@router.post("/ingest/vogue")
async def ingest_vogue(body: IngestVogueBody, db: AsyncSession = Depends(get_db)):
    """
    Scrape a Vogue Runway show page for look images, seed them as Look rows,
    and run Vision tagging on each.

    Body:
        show_slug: lowercased brand name, hyphens for spaces (e.g. "gucci", "the-row")
        vogue_url: full Vogue Runway URL
                   (e.g. https://www.vogue.com/fashion-shows/fall-2026-ready-to-wear/gucci)
    """
    from app.services.vogue_scraper import scrape_vogue_runway
    from app.services.manual_seed_looks import seed_looks_for_show

    try:
        image_urls = await scrape_vogue_runway(body.vogue_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to scrape Vogue page: {e}")

    if not image_urls:
        raise HTTPException(status_code=404, detail="No look images found on the Vogue page.")

    try:
        result = await seed_looks_for_show(db, body.show_slug, image_urls)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    result["vogue_url"] = body.vogue_url
    result["images_scraped"] = len(image_urls)
    return result
