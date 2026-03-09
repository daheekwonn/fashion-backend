"""
routers/trends.py — REST endpoints for trend data

GET  /api/trends                    → top trending items
GET  /api/trends/{id}/history       → time-series for charts
GET  /api/trends/keywords           → keyword tag cloud data
GET  /api/trends/colors             → seasonal color palette
GET  /api/trends/materials          → materials breakdown
POST /api/trends/run-scoring        → trigger scoring pipeline (admin)
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import get_settings
from app.models.database import TrendItem, TrendScore, Show
from app.services.trend_scorer import run_scoring_pipeline
from app.services.search_trends import ingest_search_trends, ingest_fw26_seed_keywords
from app.services.ingestion import ingest_season

router = APIRouter(prefix="/api/trends", tags=["trends"])
settings = get_settings()


# ── Pydantic response schemas ─────────────────────────────────────────────────

class TrendItemOut(BaseModel):
    id:               int
    name:             str
    category:         str
    trend_score:      float
    trend_delta:      float
    is_rising:        bool
    runway_count:     int
    runway_show_count:int
    search_index:     float

    class Config:
        from_attributes = True


class TrendHistoryPoint(BaseModel):
    date:         str
    composite:    float
    runway_score: float
    search_score: float
    social_score: float


class ColorSwatch(BaseModel):
    hex:   str
    name:  str
    score: float
    delta: float


class MaterialBar(BaseModel):
    name:  str
    score: float
    count: int


class KeywordTag(BaseModel):
    name:     str
    score:    float
    delta:    float
    category: str
    is_rising:bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TrendItemOut])
async def get_top_trends(
    season:   str   = Query(default=None),
    category: str   = Query(default=None),
    limit:    int   = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return top trending items, sorted by composite score."""
    season = season or settings.ACTIVE_SEASON
    q = select(TrendItem).where(TrendItem.season == season)
    if category:
        q = q.where(TrendItem.category == category)
    q = q.order_by(desc(TrendItem.trend_score)).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/keywords", response_model=List[KeywordTag])
async def get_trending_keywords(
    season:   str = Query(default=None),
    limit:    int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return trending keywords with scores for the tag-cloud / keyword list."""
    season = season or settings.ACTIVE_SEASON
    result = await db.execute(
        select(TrendItem)
        .where(TrendItem.season == season)
        .order_by(desc(TrendItem.trend_score))
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        KeywordTag(
            name=i.name,
            score=i.trend_score,
            delta=i.trend_delta,
            category=i.category,
            is_rising=i.is_rising,
        )
        for i in items
    ]


@router.get("/materials", response_model=List[MaterialBar])
async def get_material_trends(
    season: str = Query(default=None),
    limit:  int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return top materials for the horizontal bar chart."""
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


@router.get("/colors", response_model=List[ColorSwatch])
async def get_color_trends(
    season: str = Query(default=None),
    limit:  int = Query(default=12, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Return trending colors for the palette grid."""
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
        ColorSwatch(
            hex=i.name if i.name.startswith("#") else "#CCCCCC",
            name=i.name,
            score=i.trend_score,
            delta=i.trend_delta,
        )
        for i in items
    ]


@router.get("/{item_id}/history", response_model=List[TrendHistoryPoint])
async def get_trend_history(
    item_id: int,
    days:    int = Query(default=90, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return daily score history for a single TrendItem (for charts)."""
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
            date=s.date.strftime("%Y-%m-%d"),
            composite=s.composite,
            runway_score=s.runway_score,
            search_score=s.search_score,
            social_score=s.social_score,
        )
        for s in snaps
    ]


# ── Admin / pipeline trigger endpoints ───────────────────────────────────────

@router.post("/run-scoring")
async def trigger_scoring(
    background_tasks: BackgroundTasks,
    season: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the trend scoring pipeline.
    Runs in the background so the HTTP response returns immediately.
    """
    season = season or settings.ACTIVE_SEASON
    background_tasks.add_task(run_scoring_pipeline, db, season)
    return {"status": "started", "season": season}


@router.post("/ingest/runway")
async def trigger_runway_ingest(
    background_tasks: BackgroundTasks,
    season: str = Query(default=None),
    tag_images: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger runway show ingestion from Tagwalk.
    Set tag_images=true to also run Google Vision (costs money).
    """
    season = season or settings.ACTIVE_SEASON
    background_tasks.add_task(
        ingest_season, db, season, settings.active_cities_list, tag_images
    )
    return {"status": "started", "season": season, "tag_images": tag_images}


@router.post("/ingest/search")
async def trigger_search_ingest(
    background_tasks: BackgroundTasks,
    season: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Google Trends ingestion for all TrendItems in a season.
    Also ingests the FW26 seed keywords.
    """
    season = season or settings.ACTIVE_SEASON

    async def _run(db, season):
        await ingest_fw26_seed_keywords(db)
        await ingest_search_trends(db, season=season)

    background_tasks.add_task(_run, db, season)
    return {"status": "started", "season": season}


# ── Shows list ────────────────────────────────────────────────────────────────

@router.get("/shows")
async def list_shows(
    season: str = Query(default=None),
    city:   str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return all indexed shows for a season."""
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
