"""
models/database.py — SQLAlchemy ORM models

Tables:
  shows           — one row per fashion show (brand + city + season)
  looks           — individual looks from a show, with tagged attributes
  trend_items     — broad trend categories tracked as signals (e.g. "Leather Outerwear")
  trend_sub_items — specific items within a category (e.g. "Leather Biker Jacket")
                    source: "vision" (auto-detected) or "manual" (verified in Sanity)
  trend_scores    — daily composite score snapshot per trend_item
  search_signals  — raw Google Trends data (keyword → date → value)
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

    id          = Column(Integer, primary_key=True, index=True)
    brand       = Column(String(120), nullable=False)
    season      = Column(String(10),  nullable=False)   # e.g. "FW26"
    city        = Column(String(60),  nullable=False)   # e.g. "Paris"
    show_date   = Column(DateTime, nullable=True)
    total_looks = Column(Integer, default=0)
    source_url  = Column(String(500), nullable=True)
    indexed_at  = Column(DateTime, default=utcnow)

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

    # Structured tags (populated by Roboflow/Vision or manual entry)
    materials    = Column(JSON, default=list)   # ["leather", "shearling"]
    silhouettes  = Column(JSON, default=list)   # ["oversized", "biker"]
    colors       = Column(JSON, default=list)   # ["#2B1B12", "cognac"]
    color_names  = Column(JSON, default=list)   # ["Dark Cognac", "Black"]
    accessories  = Column(JSON, default=list)   # ["sculptural bag", "knee boots"]
    patterns     = Column(JSON, default=list)   # ["plaid", "floral"]
    categories   = Column(JSON, default=list)   # ["outerwear", "eveningwear"]

    # Sub-item tags — specific pieces detected/verified in this look
    # e.g. ["Leather Biker Jacket", "Wide-Leg Trousers"]
    # Populated when a Look is linked to TrendSubItems
    sub_item_tags = Column(JSON, default=list)

    vision_raw   = Column(JSON, default=dict)
    tagged_at    = Column(DateTime, nullable=True)

    show = relationship("Show", back_populates="looks")

    __table_args__ = (
        Index("ix_looks_show_id", "show_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
class TrendItem(Base):
    """
    A broad trend category — shown on the homepage leaderboard.
    Examples: "Leather Outerwear", "Prairie Silhouette", "Shearling"

    Sub-items (specific pieces) live in TrendSubItem and link back here.
    The composite score here is the aggregate signal across all sub-items
    in the category.
    """
    __tablename__ = "trend_items"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String(120), nullable=False, unique=True)
    category           = Column(String(60),  nullable=False)
    # category options: outerwear | dress | tailoring | footwear | accessory
    #                   material | color | silhouette | aesthetic
    season             = Column(String(10),  nullable=False, default="FW26")

    # Search keyword used to pull Google Trends data for this category
    # e.g. "leather outerwear" — maps to FW26_KEYWORD_GROUPS in search_trends.py
    search_keyword     = Column(String(120), nullable=True)

    # Aggregate runway counts across all sub-items
    runway_count       = Column(Integer, default=0)   # total looks featuring any sub-item
    runway_show_count  = Column(Integer, default=0)   # distinct shows featuring any sub-item

    # Score components (0-100 each)
    runway_score       = Column(Float, default=0.0)   # 50% weight
    search_score       = Column(Float, default=0.0)   # 30% weight
    social_score       = Column(Float, default=0.0)   # 20% weight

    # Composite trend score and history
    trend_score        = Column(Float, default=0.0)
    trend_score_prev   = Column(Float, default=0.0)
    trend_delta        = Column(Float, default=0.0)   # score change %
    is_rising          = Column(Boolean, default=False)

    last_scored_at     = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=utcnow)

    # Relationships
    sub_items = relationship(
        "TrendSubItem", back_populates="parent", cascade="all, delete-orphan",
        order_by="TrendSubItem.runway_count.desc()"
    )
    scores = relationship(
        "TrendScore", back_populates="item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_trend_items_category_season", "category", "season"),
        Index("ix_trend_items_score", "trend_score"),
    )

    def __repr__(self):
        return f"<TrendItem {self.name} ({self.category}) score={self.trend_score:.1f}>"


# ─────────────────────────────────────────────────────────────────────────────
class TrendSubItem(Base):
    """
    A specific piece within a trend category — shown on the /trends detail page.

    Examples under "Leather Outerwear":
      - Leather Biker Jacket   (runway_count=34, rank=1)
      - Leather Blazer         (runway_count=28, rank=2)
      - Leather Moto Coat      (runway_count=19, rank=3)

    Source:
      - "vision"  — auto-detected by Roboflow / Google Vision
      - "manual"  — entered manually (e.g. via Sanity or admin)

    Verified:
      - False = auto-detected, not yet reviewed
      - True  = confirmed correct by a human
    """
    __tablename__ = "trend_sub_items"

    id             = Column(Integer, primary_key=True, index=True)
    parent_id      = Column(Integer, ForeignKey("trend_items.id"), nullable=False, index=True)

    name           = Column(String(120), nullable=False)
    # e.g. "Leather Biker Jacket", "Leather Blazer", "Leather Moto Coat"

    season         = Column(String(10), nullable=False, default="FW26")

    # Runway signal — how many times this specific piece appeared
    runway_count   = Column(Integer, default=0)    # total looks
    runway_shows   = Column(JSON,    default=list) # list of show brands that featured it
                                                   # e.g. ["Gucci", "Saint Laurent", "Acne"]

    # Search signal — specific keyword for this sub-item (optional)
    # If set, overrides the parent search_keyword for finer-grained data
    search_keyword = Column(String(120), nullable=True)
    search_score   = Column(Float, default=0.0)    # 0-100

    # Rank within parent category (1 = most prominent)
    rank           = Column(Integer, default=0)

    # Source tracking
    source         = Column(String(20), default="manual")
    # "vision"  = auto-detected by Roboflow/Vision API
    # "manual"  = entered manually

    verified       = Column(Boolean, default=False)
    # False = auto-detected, pending review
    # True  = confirmed by a human

    notes          = Column(Text, nullable=True)   # optional editorial note

    created_at     = Column(DateTime, default=utcnow)
    updated_at     = Column(DateTime, default=utcnow, onupdate=utcnow)

    parent = relationship("TrendItem", back_populates="sub_items")

    __table_args__ = (
        UniqueConstraint("parent_id", "name", "season", name="uq_subitem_parent_name_season"),
        Index("ix_sub_items_parent_id", "parent_id"),
        Index("ix_sub_items_rank", "parent_id", "rank"),
    )

    def __repr__(self):
        return f"<TrendSubItem {self.name} (parent_id={self.parent_id}) rank={self.rank}>"


# ─────────────────────────────────────────────────────────────────────────────
class TrendScore(Base):
    """
    Daily snapshot of a TrendItem's composite score.
    Used to build time-series charts on the /trends page.
    """
    __tablename__ = "trend_scores"

    id             = Column(Integer, primary_key=True, index=True)
    item_id        = Column(Integer, ForeignKey("trend_items.id"), nullable=False, index=True)
    date           = Column(DateTime, nullable=False)

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
    Populated by the pytrends ingestion job in search_trends.py.
    One row per keyword per date per geo.
    """
    __tablename__ = "search_signals"

    id       = Column(Integer, primary_key=True, index=True)
    keyword  = Column(String(120), nullable=False, index=True)
    date     = Column(DateTime,    nullable=False)
    value    = Column(Float,       default=0.0)   # 0-100 relative search interest
    geo      = Column(String(10),  default="")    # "" = worldwide, "US", "GB" etc.

    __table_args__ = (
        UniqueConstraint("keyword", "date", "geo", name="uq_search_keyword_date_geo"),
    )
