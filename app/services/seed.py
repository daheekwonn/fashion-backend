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
from app.models.database import TrendItem, TrendSubItem, Show

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


# ── FW26 runway shows ────────────────────────────────────────────────────────

FW26_SHOWS = [
    # Paris
    {"brand": "Alaia",              "city": "Paris"},
    {"brand": "Balenciaga",         "city": "Paris"},
    {"brand": "Balmain",            "city": "Paris"},
    {"brand": "Celine",             "city": "Paris"},
    {"brand": "Chanel",             "city": "Paris"},
    {"brand": "Chloe",              "city": "Paris"},
    {"brand": "Christian Dior",     "city": "Paris"},
    {"brand": "Comme des Garcons",  "city": "Paris"},
    {"brand": "Courrèges",          "city": "Paris"},
    {"brand": "Dries Van Noten",    "city": "Paris"},
    {"brand": "Gabriela Hearst",    "city": "Paris"},
    {"brand": "Givenchy",           "city": "Paris"},
    {"brand": "Hermes",             "city": "Paris"},
    {"brand": "Isabel Marant",      "city": "Paris"},
    {"brand": "Jacquemus",          "city": "Paris"},
    {"brand": "Jean Paul Gaultier", "city": "Paris"},
    {"brand": "Jil Sander",         "city": "Paris"},
    {"brand": "Junya Watanabe",     "city": "Paris"},
    {"brand": "Kiko Kostadinov",    "city": "Paris"},
    {"brand": "Lacoste",            "city": "Paris"},
    {"brand": "Lanvin",             "city": "Paris"},
    {"brand": "Lemaire",            "city": "Paris"},
    {"brand": "Loewe",              "city": "Paris"},
    {"brand": "Louis Vuitton",      "city": "Paris"},
    {"brand": "Magda Butrym",       "city": "Paris"},
    {"brand": "McQueen",            "city": "Paris"},
    {"brand": "Miu Miu",            "city": "Paris"},
    {"brand": "Mugler",             "city": "Paris"},
    {"brand": "Nina Ricci",         "city": "Paris"},
    {"brand": "Patou",              "city": "Paris"},
    {"brand": "Rabanne",            "city": "Paris"},
    {"brand": "Rick Owens",         "city": "Paris"},
    {"brand": "Saint Laurent",      "city": "Paris"},
    {"brand": "Schiaparelli",       "city": "Paris"},
    {"brand": "Stella McCartney",   "city": "Paris"},
    {"brand": "Tom Ford",           "city": "Paris"},
    {"brand": "Toteme",             "city": "Paris"},
    {"brand": "Undercover",         "city": "Paris"},
    {"brand": "Valentino",          "city": "Paris"},
    {"brand": "Victoria Beckham",   "city": "Paris"},
    {"brand": "Yohji Yamamoto",     "city": "Paris"},
    {"brand": "Zimmermann",         "city": "Paris"},
    # Milan
    {"brand": "Blumarine",             "city": "Milan"},
    {"brand": "Boss",                  "city": "Milan"},
    {"brand": "Bottega Veneta",        "city": "Milan"},
    {"brand": "Diesel",                "city": "Milan"},
    {"brand": "Dolce & Gabbana",       "city": "Milan"},
    {"brand": "Emporio Armani",        "city": "Milan"},
    {"brand": "Etro",                  "city": "Milan"},
    {"brand": "Fendi",                 "city": "Milan"},
    {"brand": "Ferragamo",             "city": "Milan"},
    {"brand": "Giorgio Armani",        "city": "Milan"},
    {"brand": "Gucci",                 "city": "Milan"},
    {"brand": "Marco Rambaldi",        "city": "Milan"},
    {"brand": "Marni",                 "city": "Milan"},
    {"brand": "Max Mara",              "city": "Milan"},
    {"brand": "Missoni",               "city": "Milan"},
    {"brand": "MM6 Maison Margiela",   "city": "Milan"},
    {"brand": "Moschino",              "city": "Milan"},
    {"brand": "No. 21",                "city": "Milan"},
    {"brand": "Prada",                 "city": "Milan"},
    {"brand": "Roberto Cavalli",       "city": "Milan"},
    {"brand": "Sportmax",              "city": "Milan"},
    {"brand": "Tod's",                 "city": "Milan"},
    {"brand": "Valentino",             "city": "Milan"},
    # London
    {"brand": "Acne Studios",    "city": "London"},
    {"brand": "Burberry",        "city": "London"},
    {"brand": "Conner Ives",     "city": "London"},
    {"brand": "Erdem",           "city": "London"},
    {"brand": "Simone Rocha",    "city": "London"},
    {"brand": "Richard Quinn",   "city": "London"},
    # New York
    {"brand": "Altuzarra",        "city": "New York"},
    {"brand": "Carolina Herrera", "city": "New York"},
    {"brand": "Coach",            "city": "New York"},
    {"brand": "Khaite",           "city": "New York"},
    {"brand": "Michael Kors",     "city": "New York"},
    {"brand": "Prabal Gurung",    "city": "New York"},
    {"brand": "Proenza Schouler", "city": "New York"},
    {"brand": "Ralph Lauren",     "city": "New York"},
    {"brand": "Sandy Liang",      "city": "New York"},
    {"brand": "Tory Burch",       "city": "New York"},
    {"brand": "Ulla Johnson",     "city": "New York"},
    # Copenhagen
    {"brand": "Baum und Pferdgarten", "city": "Copenhagen"},
    {"brand": "Holzweiler",           "city": "Copenhagen"},
    {"brand": "Rave Review",          "city": "Copenhagen"},
    {"brand": "Skall Studio",         "city": "Copenhagen"},
]


async def seed_fw26_shows(db: AsyncSession) -> dict:
    """
    Create FW26 Show rows for all major designers/cities.
    Skips shows that already exist (unique on brand+season).
    """
    created = 0
    skipped = 0

    for data in FW26_SHOWS:
        result = await db.execute(
            select(Show).where(Show.brand == data["brand"], Show.season == "FW26")
        )
        if result.scalars().first():
            skipped += 1
            continue

        db.add(Show(
            brand  = data["brand"],
            season = "FW26",
            city   = data["city"],
        ))
        created += 1

    logger.info(f"Seed shows: {created} created, {skipped} skipped")
    return {"status": "ok", "created": created, "skipped": skipped, "total": len(FW26_SHOWS)}
