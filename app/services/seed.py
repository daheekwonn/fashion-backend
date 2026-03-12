# app/services/seed.py
#
# One-time seed script for FW26 TrendItem categories and TrendSubItems.
#
# Run via the API:
#   POST /api/trends/seed/items     — creates parent categories
#   POST /api/trends/seed/subitems  — creates specific pieces under each category
#
# Safe to re-run — skips items that already exist.

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import TrendItem, TrendSubItem

logger = logging.getLogger(__name__)


# ── FW26 parent categories ─────────────────────────────────────────────────────

FW26_ITEMS = [
    # Outerwear
    { "name": "Leather Outerwear",  "category": "outerwear",  "search_keyword": "leather outerwear" },
    { "name": "Shearling",          "category": "outerwear",  "search_keyword": "shearling coat" },
    { "name": "Oversized Coat",     "category": "outerwear",  "search_keyword": "oversized coat" },
    { "name": "Trench Coat",        "category": "outerwear",  "search_keyword": "trench coat women" },
    # Dresses & silhouettes
    { "name": "Prairie Silhouette", "category": "dress",      "search_keyword": "prairie dress" },
    { "name": "Column Dress",       "category": "dress",      "search_keyword": "column dress" },
    { "name": "Slip Dress",         "category": "dress",      "search_keyword": "slip dress outfit" },
    # Tailoring
    { "name": "Wide-Leg Tailoring", "category": "tailoring",  "search_keyword": "wide leg trousers" },
    { "name": "Pleated Trousers",   "category": "tailoring",  "search_keyword": "pleated trousers" },
    { "name": "Power Suiting",      "category": "tailoring",  "search_keyword": "tailored suit women" },
    # Footwear
    { "name": "Ballet Flats",       "category": "footwear",   "search_keyword": "ballet flats outfit" },
    { "name": "Mary Janes",         "category": "footwear",   "search_keyword": "mary jane heels" },
    { "name": "Kitten Heels",       "category": "footwear",   "search_keyword": "kitten heel shoes" },
    { "name": "Knee-High Boots",    "category": "footwear",   "search_keyword": "knee high boots" },
    # Colours
    { "name": "Burgundy",           "category": "color",      "search_keyword": "burgundy outfit" },
    { "name": "Chocolate Brown",    "category": "color",      "search_keyword": "chocolate brown fashion" },
    { "name": "Ivory & Cream",      "category": "color",      "search_keyword": "ivory cream outfit" },
    { "name": "Forest Green",       "category": "color",      "search_keyword": "forest green coat" },
    { "name": "Camel",              "category": "color",      "search_keyword": "camel coat" },
    # Materials
    { "name": "Velvet",             "category": "material",   "search_keyword": "velvet fashion" },
    { "name": "Boucle",             "category": "material",   "search_keyword": "boucle jacket" },
    { "name": "Satin",              "category": "material",   "search_keyword": "satin dress trend" },
    { "name": "Lace",               "category": "material",   "search_keyword": "lace fashion 2026" },
    # Bags
    { "name": "Shoulder Bag",       "category": "accessory",  "search_keyword": "shoulder bag outfit" },
    { "name": "Oversized Tote",     "category": "accessory",  "search_keyword": "oversized tote bag" },
    # Aesthetics
    { "name": "Quiet Luxury",       "category": "aesthetic",  "search_keyword": "quiet luxury fashion" },
    { "name": "Romantic Dressing",  "category": "aesthetic",  "search_keyword": "romantic fashion aesthetic" },
]


# ── FW26 sub-items ─────────────────────────────────────────────────────────────

FW26_SUB_ITEMS = [
    # Leather Outerwear
    { "parent": "Leather Outerwear", "name": "Leather Biker Jacket",   "runway_count": 0, "runway_shows": ["Gucci", "Saint Laurent", "Acne Studios"] },
    { "parent": "Leather Outerwear", "name": "Leather Blazer",         "runway_count": 0, "runway_shows": ["The Row", "Toteme", "Bottega Veneta"] },
    { "parent": "Leather Outerwear", "name": "Leather Moto Coat",      "runway_count": 0, "runway_shows": ["Balenciaga", "Rick Owens"] },
    { "parent": "Leather Outerwear", "name": "Leather Trench",         "runway_count": 0, "runway_shows": ["Burberry", "Max Mara"] },
    # Shearling
    { "parent": "Shearling", "name": "Shearling Coat",         "runway_count": 0, "runway_shows": ["Bottega Veneta", "Loewe", "Gucci"] },
    { "parent": "Shearling", "name": "Shearling Jacket",       "runway_count": 0, "runway_shows": ["Acne Studios", "Toteme"] },
    { "parent": "Shearling", "name": "Shearling Gilet / Vest", "runway_count": 0, "runway_shows": ["The Row", "Loro Piana"] },
    # Prairie Silhouette
    { "parent": "Prairie Silhouette", "name": "Prairie Maxi Dress", "runway_count": 0, "runway_shows": ["Chloe", "Zimmermann", "Simone Rocha"] },
    { "parent": "Prairie Silhouette", "name": "Ruffled Hem Dress",  "runway_count": 0, "runway_shows": ["Chloe", "Erdem"] },
    { "parent": "Prairie Silhouette", "name": "Tiered Skirt",       "runway_count": 0, "runway_shows": ["Zimmermann", "Ulla Johnson"] },
    { "parent": "Prairie Silhouette", "name": "Peasant Blouse",     "runway_count": 0, "runway_shows": ["Isabel Marant", "Chloe"] },
    # Column Dress
    { "parent": "Column Dress", "name": "Minimal Column Gown", "runway_count": 0, "runway_shows": ["Bottega Veneta", "Jil Sander", "The Row"] },
    { "parent": "Column Dress", "name": "Jersey Column Dress",  "runway_count": 0, "runway_shows": ["Alaïa", "Toteme"] },
    { "parent": "Column Dress", "name": "Satin Column Dress",   "runway_count": 0, "runway_shows": ["Saint Laurent", "Valentino"] },
    # Wide-Leg Tailoring
    { "parent": "Wide-Leg Tailoring", "name": "Wide-Leg Trousers", "runway_count": 0, "runway_shows": ["Gucci", "Bottega Veneta", "Loewe", "Saint Laurent"] },
    { "parent": "Wide-Leg Tailoring", "name": "Wide-Leg Suiting",  "runway_count": 0, "runway_shows": ["The Row", "Max Mara"] },
    { "parent": "Wide-Leg Tailoring", "name": "Palazzo Pants",     "runway_count": 0, "runway_shows": ["Valentino", "Etro"] },
    # Ballet Flats
    { "parent": "Ballet Flats", "name": "Pointed Ballet Flat",   "runway_count": 0, "runway_shows": ["Miu Miu", "Prada", "Chloe"] },
    { "parent": "Ballet Flats", "name": "Square-Toe Ballet Flat", "runway_count": 0, "runway_shows": ["The Row", "Toteme"] },
    { "parent": "Ballet Flats", "name": "Embellished Ballet Flat","runway_count": 0, "runway_shows": ["Valentino", "Simone Rocha"] },
    # Mary Janes
    { "parent": "Mary Janes", "name": "Platform Mary Jane",    "runway_count": 0, "runway_shows": ["Miu Miu", "Prada"] },
    { "parent": "Mary Janes", "name": "Kitten-Heel Mary Jane", "runway_count": 0, "runway_shows": ["Chanel", "Sandro"] },
    { "parent": "Mary Janes", "name": "Chunky Mary Jane",      "runway_count": 0, "runway_shows": ["Simone Rocha", "Erdem"] },
    # Power Suiting
    { "parent": "Power Suiting", "name": "Pinstripe Suit",       "runway_count": 0, "runway_shows": ["Gucci", "Versace", "Saint Laurent"] },
    { "parent": "Power Suiting", "name": "Oversized Blazer",     "runway_count": 0, "runway_shows": ["The Row", "Toteme", "Acne Studios"] },
    { "parent": "Power Suiting", "name": "Double-Breasted Suit", "runway_count": 0, "runway_shows": ["Brunello Cucinelli", "Max Mara"] },
    # Boucle
    { "parent": "Boucle", "name": "Boucle Jacket",     "runway_count": 0, "runway_shows": ["Chanel", "Balmain"] },
    { "parent": "Boucle", "name": "Boucle Coat",       "runway_count": 0, "runway_shows": ["Chanel", "Valentino"] },
    { "parent": "Boucle", "name": "Boucle Mini Skirt", "runway_count": 0, "runway_shows": ["Chanel", "Miu Miu"] },
    # Oversized Coat
    { "parent": "Oversized Coat", "name": "Cocoon Coat",         "runway_count": 0, "runway_shows": ["Max Mara", "Loewe", "The Row"] },
    { "parent": "Oversized Coat", "name": "Blanket Coat",        "runway_count": 0, "runway_shows": ["Acne Studios", "Toteme"] },
    { "parent": "Oversized Coat", "name": "Drop-Shoulder Coat",  "runway_count": 0, "runway_shows": ["Balenciaga", "Rick Owens"] },
]


# ── Seed functions ─────────────────────────────────────────────────────────────

async def seed_fw26_items(db: AsyncSession) -> dict:
    """
    Create FW26 TrendItem parent categories using the passed-in db session.
    Skips items that already exist by name.
    """
    created = 0
    skipped = 0

    for data in FW26_ITEMS:
        result = await db.execute(
            select(TrendItem).where(TrendItem.name == data["name"])
        )
        if result.scalars().first():
            skipped += 1
            continue

        db.add(TrendItem(
            name           = data["name"],
            category       = data["category"],
            season         = "FW26",
            search_keyword = data.get("search_keyword"),
        ))
        created += 1

    # session.commit() is handled by get_db dependency — no manual commit needed
    logger.info(f"Seed items: {created} created, {skipped} skipped")
    return {"status": "ok", "created": created, "skipped": skipped, "total": len(FW26_ITEMS)}


async def seed_fw26_subitems(db: AsyncSession) -> dict:
    """
    Create FW26 TrendSubItems using the passed-in db session.
    Skips sub-items that already exist. Run seed_fw26_items first.
    """
    created = 0
    skipped = 0
    missing_parents = []

    for data in FW26_SUB_ITEMS:
        # Look up parent
        parent_result = await db.execute(
            select(TrendItem).where(TrendItem.name == data["parent"])
        )
        parent = parent_result.scalars().first()

        if not parent:
            missing_parents.append(data["parent"])
            continue

        # Check if sub-item already exists
        existing = await db.execute(
            select(TrendSubItem).where(
                TrendSubItem.parent_id == parent.id,
                TrendSubItem.name     == data["name"],
            )
        )
        if existing.scalars().first():
            skipped += 1
            continue

        db.add(TrendSubItem(
            parent_id    = parent.id,
            name         = data["name"],
            season       = "FW26",
            runway_count = data.get("runway_count", 0),
            runway_shows = data.get("runway_shows", []),
            source       = "manual",
            verified     = True,
        ))
        created += 1

    logger.info(f"Seed sub-items: {created} created, {skipped} skipped")
    result = {"status": "ok", "created": created, "skipped": skipped, "total": len(FW26_SUB_ITEMS)}
    if missing_parents:
        result["warning"] = f"Missing parents: {list(set(missing_parents))}. Run /seed/items first."
    return result
