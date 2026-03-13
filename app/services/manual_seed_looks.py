"""
services/manual_seed_looks.py — Manually seed Look rows from a list of image URLs
and optionally run Vision tagging on each.
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Show, Look
from app.services.ingestion import tag_look_with_vision

logger = logging.getLogger(__name__)


async def seed_looks_for_show(
    db: AsyncSession,
    show_slug: str,
    image_urls: List[str],
    tag_images: bool = True,
) -> Dict[str, Any]:
    """
    Insert Look rows for an existing Show, identified by slug (lowercased brand).

    Args:
        db:          Async DB session
        show_slug:   Lowercased, hyphen-separated brand name (e.g. "valentino", "the-row")
        image_urls:  List of image URLs to create as looks
        tag_images:  Whether to run Google Vision tagging on each look

    Returns:
        Summary dict with counts and per-look results.
    """
    # Resolve slug → Show by matching lowercased brand
    slug_normalized = show_slug.lower().replace("-", " ")
    result = await db.execute(
        select(Show).where(func.lower(Show.brand) == slug_normalized)
    )
    show = result.scalar_one_or_none()
    if show is None:
        raise ValueError(f"No show found matching slug '{show_slug}'")

    # Determine starting look_number
    result = await db.execute(
        select(func.coalesce(func.max(Look.look_number), 0))
        .where(Look.show_id == show.id)
    )
    next_num = result.scalar() + 1

    created = 0
    tagged = 0
    looks_out = []

    for i, url in enumerate(image_urls):
        look_number = next_num + i

        # Skip if this exact image_url already exists for the show
        existing = await db.execute(
            select(Look).where(Look.show_id == show.id, Look.image_url == url)
        )
        if existing.scalar_one_or_none() is not None:
            looks_out.append({"look_number": look_number, "image_url": url, "status": "skipped"})
            continue

        look = Look(show_id=show.id, look_number=look_number, image_url=url)
        db.add(look)
        await db.flush()
        created += 1

        if tag_images and url:
            try:
                tags = await tag_look_with_vision(url)
                look.materials = tags["materials"]
                look.silhouettes = tags["silhouettes"]
                look.colors = tags["colors"]
                look.color_names = tags["color_names"]
                look.vision_raw = tags["raw"]
                look.tagged_at = datetime.now(timezone.utc)
                tagged += 1
                looks_out.append({"look_number": look_number, "image_url": url, "status": "tagged"})
            except Exception as e:
                logger.error(f"[SeedLooks] Vision tagging failed for {url}: {e}")
                looks_out.append({"look_number": look_number, "image_url": url, "status": "created_untagged"})
        else:
            looks_out.append({"look_number": look_number, "image_url": url, "status": "created_untagged"})

    # Update show total_looks
    result = await db.execute(
        select(func.count(Look.id)).where(Look.show_id == show.id)
    )
    show.total_looks = result.scalar()

    return {
        "show_id": show.id,
        "brand": show.brand,
        "looks_created": created,
        "looks_tagged": tagged,
        "looks": looks_out,
    }
