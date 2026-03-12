"""
models/database.py — SQLAlchemy ORM models
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


class Show(Base):
    __tablename__ = "shows"

    id          = Column(Integer, primary_key=True, index=True)
    brand       = Column(String(120), nullable=False)
    season      = Column(String(10),  nullable=False)
    city        = Column(String(60),  nullable=False)
    show_date   = Column(DateTime(timezone=True), nullable=True)
    total_looks = Column(Integer, default=0)
    source_url  = Column(String(500), nullable=True)
    indexed_at  = Column(DateTime(timezone=True), default=utcnow)

    looks = relationship("Look", back_populates="show", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("brand", "season", name="uq_show_brand_season"),
        Index("ix_shows_season_city", "season", "city"),
    )


class Look(Base):
    __tablename__ = "looks"

    id           = Column(Integer, primary_key=True, index=True)
    show_id      = Column(Integer, ForeignKey("shows.id"), nullable=False, index=True)
    look_number  = Column(Integer, nullable=True)
    image_url    = Column(String(500), nullable=True)
    materials    = Column(JSON, default=list)
    silhouettes  = Column(JSON, default=list)
    colors       = Column(JSON, default=list)
    color_names  = Column(JSON, default=list)
    accessories  = Column(JSON, default=list)
    patterns     = Column(JSON, default=list)
    categories   = Column(JSON, default=list)
    sub_item_tags = Column(JSON, default=list)
    vision_raw   = Column(JSON, default=dict)
    tagged_at    = Column(DateTime(timezone=True), nullable=True)

    show = relationship("Show", back_populates="looks")

    __table_args__ = (
        Index("ix_looks_show_id", "show_id"),
    )


class TrendItem(Base):
    __tablename__ = "trend_items"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String(120), nullable=False, unique=True)
    category           = Column(String(60),  nullable=False)
    season             = Column(String(10),  nullable=False, default="FW26")
    search_keyword     = Column(String(120), nullable=True)
    runway_count       = Column(Integer, default=0)
    runway_show_count  = Column(Integer, default=0)
    runway_score       = Column(Float, default=0.0)
    search_score       = Column(Float, default=0.0)
    social_score       = Column(Float, default=0.0)
    trend_score        = Column(Float, default=0.0)
    trend_score_prev   = Column(Float, default=0.0)
    trend_delta        = Column(Float, default=0.0)
    is_rising          = Column(Boolean, default=False)
    last_scored_at     = Column(DateTime(timezone=True), nullable=True)
    created_at         = Column(DateTime(timezone=True), default=utcnow)

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


class TrendSubItem(Base):
    __tablename__ = "trend_sub_items"

    id             = Column(Integer, primary_key=True, index=True)
    parent_id      = Column(Integer, ForeignKey("trend_items.id"), nullable=False, index=True)
    name           = Column(String(120), nullable=False)
    season         = Column(String(10), nullable=False, default="FW26")
    runway_count   = Column(Integer, default=0)
    runway_shows   = Column(JSON, default=list)
    search_keyword = Column(String(120), nullable=True)
    search_score   = Column(Float, default=0.0)
    rank           = Column(Integer, default=0)
    source         = Column(String(20), default="manual")
    verified       = Column(Boolean, default=False)
    notes          = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=utcnow)
    updated_at     = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    parent = relationship("TrendItem", back_populates="sub_items")

    __table_args__ = (
        UniqueConstraint("parent_id", "name", "season", name="uq_subitem_parent_name_season"),
        Index("ix_sub_items_parent_id", "parent_id"),
        Index("ix_sub_items_rank", "parent_id", "rank"),
    )


class TrendScore(Base):
    __tablename__ = "trend_scores"

    id             = Column(Integer, primary_key=True, index=True)
    item_id        = Column(Integer, ForeignKey("trend_items.id"), nullable=False, index=True)
    date           = Column(DateTime(timezone=True), nullable=False)
    runway_score   = Column(Float, default=0.0)
    search_score   = Column(Float, default=0.0)
    social_score   = Column(Float, default=0.0)
    composite      = Column(Float, default=0.0)

    item = relationship("TrendItem", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("item_id", "date", name="uq_score_item_date"),
        Index("ix_trend_scores_item_date", "item_id", "date"),
    )


class SearchSignal(Base):
    __tablename__ = "search_signals"

    id       = Column(Integer, primary_key=True, index=True)
    keyword  = Column(String(120), nullable=False, index=True)
    date     = Column(DateTime(timezone=True), nullable=False)
    value    = Column(Float, default=0.0)
    geo      = Column(String(10), default="")

    __table_args__ = (
        UniqueConstraint("keyword", "date", "geo", name="uq_search_keyword_date_geo"),
    )
