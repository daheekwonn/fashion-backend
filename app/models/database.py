"""
models/database.py — SQLAlchemy ORM models

Tables:
  shows          — one row per fashion show (brand + city + season)
  looks          — individual looks from a show, with tagged attributes
  trend_items    — materials, silhouettes, colors etc. tracked as trend signals
  trend_scores   — computed daily score per trend_item
  search_signals — raw Google Trends data points (keyword → date → value)
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Boolean, Text, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
class Show(Base):
    """A single fashion show — e.g. Valentino FW26 Paris."""
    __tablename__ = "shows"

    id         = Column(Integer, primary_key=True, index=True)
    brand      = Column(String(120), nullable=False)
    season     = Column(String(10), nullable=False)   # e.g. "FW26"
    city       = Column(String(60), nullable=False)   # e.g. "Paris"
    show_date  = Column(DateTime, nullable=True)
    total_looks= Column(Integer, default=0)
    source_url = Column(String(500), nullable=True)   # Tagwalk / Vogue URL
    indexed_at = Column(DateTime, default=utcnow)

    looks = relationship("Look", back_populates="show", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("brand", "season", name="uq_show_brand_season"),
        Index("ix_shows_season_city", "season", "city"),
    )

    def __repr__(self):
        return f"<Show {self.brand} {self.season} {self.city}>"


# ─────────────────────────────────────────────────────────────────────────────
class Look(Base):
    """One outfit/look from a show, with AI-tagged attributes."""
    __tablename__ = "looks"

    id           = Column(Integer, primary_key=True, index=True)
    show_id      = Column(Integer, ForeignKey("shows.id"), nullable=False, index=True)
    look_number  = Column(Integer, nullable=True)
    image_url    = Column(String(500), nullable=True)

    # Structured tags (populated by Vision API or manual tagging)
    materials    = Column(JSON, default=list)   # ["linen", "organza"]
    silhouettes  = Column(JSON, default=list)   # ["oversized", "column"]
    colors       = Column(JSON, default=list)   # ["#F5EFE0", "sage"]
    color_names  = Column(JSON, default=list)   # ["Ivory Cream", "Sage"]
    accessories  = Column(JSON, default=list)   # ["sculptural bag", "knee boots"]
    patterns     = Column(JSON, default=list)   # ["plaid", "floral"]
    categories   = Column(JSON, default=list)   # ["outerwear", "eveningwear"]

    # Raw Vision API response (stored for re-processing)
    vision_raw   = Column(JSON, default=dict)

    tagged_at    = Column(DateTime, nullable=True)
    show         = relationship("Show", back_populates="looks")

    __table_args__ = (
        Index("ix_looks_show_id", "show_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
class TrendItem(Base):
    """
    A trackable trend signal — could be a material, silhouette,
    color, keyword, accessory, or pattern.
    """
    __tablename__ = "trend_items"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(120), nullable=False, unique=True)
    category     = Column(String(60), nullable=False)
    # category options: material | silhouette | color | keyword | accessory | pattern
    season       = Column(String(10), nullable=False, default="FW26")

    # Cached aggregate counts (refreshed by scoring job)
    runway_count       = Column(Integer, default=0)   # # looks featuring this item
    runway_show_count  = Column(Integer, default=0)   # # distinct shows
    search_index       = Column(Float, default=0.0)   # 0–100 from Google Trends
    social_velocity    = Column(Float, default=0.0)   # hashtag growth rate

    # Composite trend score (0–100), recomputed daily
    trend_score        = Column(Float, default=0.0)
    trend_score_prev   = Column(Float, default=0.0)   # yesterday's score
    trend_delta        = Column(Float, default=0.0)   # score change %

    is_rising          = Column(Boolean, default=False)
    last_scored_at     = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=utcnow)

    scores = relationship("TrendScore", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_trend_items_category_season", "category", "season"),
        Index("ix_trend_items_score", "trend_score"),
    )

    def __repr__(self):
        return f"<TrendItem {self.name} ({self.category}) score={self.trend_score:.1f}>"


# ─────────────────────────────────────────────────────────────────────────────
class TrendScore(Base):
    """
    Daily snapshot of a TrendItem's score — used to build the
    time-series charts in the frontend.
    """
    __tablename__ = "trend_scores"

    id           = Column(Integer, primary_key=True, index=True)
    item_id      = Column(Integer, ForeignKey("trend_items.id"), nullable=False, index=True)
    date         = Column(DateTime, nullable=False)

    # Component scores (each 0–100)
    runway_score   = Column(Float, default=0.0)
    search_score   = Column(Float, default=0.0)
    social_score   = Column(Float, default=0.0)
    composite      = Column(Float, default=0.0)

    item = relationship("TrendItem", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("item_id", "date", name="uq_score_item_date"),
        Index("ix_trend_scores_item_date", "item_id", "date"),
    )


# ─────────────────────────────────────────────────────────────────────────────
class SearchSignal(Base):
    """
    Raw Google Trends data for a keyword, stored per date.
    Populated by the pytrends ingestion job.
    """
    __tablename__ = "search_signals"

    id          = Column(Integer, primary_key=True, index=True)
    keyword     = Column(String(120), nullable=False, index=True)
    date        = Column(DateTime, nullable=False)
    value       = Column(Float, default=0.0)   # 0–100 relative search interest
    geo         = Column(String(10), default="")  # "" = worldwide, "US", etc.

    __table_args__ = (
        UniqueConstraint("keyword", "date", "geo", name="uq_search_keyword_date_geo"),
    )
