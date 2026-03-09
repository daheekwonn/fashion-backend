"""
services/ingestion.py
─────────────────────
Pulls runway look data from Tagwalk API and stores it in the DB.
Also handles re-processing looks through Google Vision for auto-tagging.

Tagwalk API docs: https://tagwalk.com/api
  GET /api/looks?season=FW26&city=Paris&limit=50&offset=0
  GET /api/shows?season=FW26&city=Paris
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.database import Show, Look

logger = logging.getLogger(__name__)
settings = get_settings()

TAGWALK_BASE = "https://api.tagwalk.com"   # confirmed base URL
VISION_BASE  = "https://vision.googleapis.com/v1/images:annotate"

# Material keywords to look for in Vision API labels
MATERIAL_KEYWORDS = {
    "linen", "silk", "satin", "velvet", "denim", "leather", "suede",
    "organza", "chiffon", "wool", "cashmere", "tweed", "mesh", "lace",
    "sequin", "brocade", "jersey", "knit", "fur", "shearling", "nylon",
    "cotton", "polyester", "vinyl", "latex", "tulle", "crepe",
}

SILHOUETTE_KEYWORDS = {
    "oversized", "fitted", "tailored", "draped", "sculptural", "column",
    "a-line", "balloon", "deconstructed", "asymmetric", "layered",
    "cropped", "midi", "maxi", "mini", "relaxed", "structured",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Tagwalk client
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _tagwalk_get(path: str, params: Dict = {}) -> Dict:
    """Authenticated GET to Tagwalk API with automatic retries."""
    headers = {"Authorization": f"Bearer {settings.TAGWALK_API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{TAGWALK_BASE}{path}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_shows_for_season(season: str, city: Optional[str] = None) -> List[Dict]:
    """
    Returns list of shows from Tagwalk for a given season (and optionally city).

    Example response item:
      {
        "id": "valentino-fw26-paris",
        "brand": "Valentino",
        "city": "Paris",
        "date": "2026-03-05",
        "total_looks": 48,
        "url": "https://tagwalk.com/en/show/..."
      }
    """
    params = {"season": season}
    if city:
        params["city"] = city
    data = await _tagwalk_get("/api/shows", params)
    return data.get("shows", [])


async def fetch_looks_for_show(
    show_tagwalk_id: str,
    limit: int = 100,
) -> List[Dict]:
    """
    Returns looks for a specific show from Tagwalk.

    Example response item:
      {
        "look_number": 1,
        "image_url": "https://cdn.tagwalk.com/...",
        "tags": ["linen", "oversized", "beige"],
        "colors": ["#F5EFE0"],
        "color_names": ["Ivory"],
        "materials": ["linen"],
        "silhouette": "oversized"
      }
    """
    data = await _tagwalk_get(
        f"/api/shows/{show_tagwalk_id}/looks",
        params={"limit": limit}
    )
    return data.get("looks", [])


# ─────────────────────────────────────────────────────────────────────────────
#  Google Vision tagging
# ─────────────────────────────────────────────────────────────────────────────

async def tag_look_with_vision(image_url: str) -> Dict[str, List[str]]:
    """
    Sends an image to Google Cloud Vision and extracts fashion-relevant tags.

    Returns:
        {
          "materials":   ["linen", "organza"],
          "silhouettes": ["oversized"],
          "colors":      ["#C4A882", "#2B2B2B"],
          "color_names": ["Sand", "Black"],
          "raw":         { ... full Vision response ... }
        }
    """
    if not settings.GOOGLE_VISION_API_KEY:
        logger.debug("[Vision] No API key — skipping tagging.")
        return {"materials": [], "silhouettes": [], "colors": [], "color_names": [], "raw": {}}

    payload = {
        "requests": [{
            "image": {"source": {"imageUri": image_url}},
            "features": [
                {"type": "LABEL_DETECTION",    "maxResults": 20},
                {"type": "IMAGE_PROPERTIES"},   # dominant colors
                {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
            ]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                VISION_BASE,
                params={"key": settings.GOOGLE_VISION_API_KEY},
                json=payload,
            )
            resp.raise_for_status()
            raw = resp.json()
    except Exception as e:
        logger.error(f"[Vision] Request failed for {image_url}: {e}")
        return {"materials": [], "silhouettes": [], "colors": [], "color_names": [], "raw": {}}

    annotations = raw.get("responses", [{}])[0]

    # ── Extract labels → materials & silhouettes ─────────────────────────────
    labels = [a["description"].lower() for a in annotations.get("labelAnnotations", [])]
    materials   = [l for l in labels if l in MATERIAL_KEYWORDS]
    silhouettes = [l for l in labels if l in SILHOUETTE_KEYWORDS]

    # ── Extract dominant colors ───────────────────────────────────────────────
    color_info  = annotations.get("imagePropertiesAnnotation", {}).get("dominantColors", {})
    color_hex   = []
    color_names = []
    for c in color_info.get("colors", [])[:5]:
        rgb = c.get("color", {})
        r, g, b = int(rgb.get("red", 0)), int(rgb.get("green", 0)), int(rgb.get("blue", 0))
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        color_hex.append(hex_color)
        # Simple named color approximation (can swap in a color-namer library)
        color_names.append(_approximate_color_name(r, g, b))

    return {
        "materials":   list(dict.fromkeys(materials)),    # deduplicated, order preserved
        "silhouettes": list(dict.fromkeys(silhouettes)),
        "colors":      color_hex,
        "color_names": color_names,
        "raw":         annotations,
    }


def _approximate_color_name(r: int, g: int, b: int) -> str:
    """
    Very simple color naming by comparing to palette anchors.
    Replace with a proper color-namer library (e.g. `color` or `colormath`)
    for production use.
    """
    named = {
        "Black":       (0,   0,   0),
        "White":       (255, 255, 255),
        "Ivory":       (245, 239, 224),
        "Beige":       (196, 168, 130),
        "Sand":        (194, 168, 116),
        "Camel":       (180, 130, 70),
        "Cream":       (255, 245, 220),
        "Sage":        (143, 175, 138),
        "Forest":      (50,  100, 60),
        "Slate Blue":  (122, 150, 176),
        "Cobalt":      (0,   71,  171),
        "Navy":        (0,   0,   128),
        "Blush":       (232, 196, 184),
        "Rose":        (200, 120, 120),
        "Red":         (200, 0,   0),
        "Clay":        (184, 122, 106),
        "Chocolate":   (120, 70,  40),
        "Onyx":        (43,  43,  43),
        "Charcoal":    (80,  80,  80),
        "Silver":      (192, 192, 192),
    }
    best, best_dist = "Unknown", float("inf")
    for name, (nr, ng, nb) in named.items():
        dist = ((r - nr)**2 + (g - ng)**2 + (b - nb)**2) ** 0.5
        if dist < best_dist:
            best, best_dist = name, dist
    return best


# ─────────────────────────────────────────────────────────────────────────────
#  Full ingestion pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def ingest_season(
    db: AsyncSession,
    season: str,
    cities: Optional[List[str]] = None,
    tag_images: bool = True,
) -> Dict[str, Any]:
    """
    Full ingestion pipeline for a season:
      1. Fetch shows from Tagwalk
      2. Upsert Show rows
      3. Fetch looks per show
      4. Optionally tag images via Google Vision
      5. Upsert Look rows

    Args:
        db:         Async DB session
        season:     e.g. "FW26"
        cities:     Filter to specific cities (None = all)
        tag_images: Whether to call Vision API (costs money — disable for dev)
    """
    cities = cities or settings.active_cities_list
    total_shows = 0
    total_looks = 0

    for city in cities:
        logger.info(f"[Ingest] Fetching shows for {season} {city}")
        try:
            shows_data = await fetch_shows_for_season(season, city)
        except Exception as e:
            logger.error(f"[Ingest] Failed to fetch shows for {city}: {e}")
            continue

        for show_data in shows_data:
            # Upsert Show
            result = await db.execute(
                select(Show).where(
                    Show.brand == show_data["brand"],
                    Show.season == season,
                )
            )
            show: Optional[Show] = result.scalar_one_or_none()
            if show is None:
                show = Show(brand=show_data["brand"], season=season, city=city)
                db.add(show)

            show.total_looks = show_data.get("total_looks", 0)
            show.source_url  = show_data.get("url")
            if show_data.get("date"):
                try:
                    show.show_date = datetime.fromisoformat(show_data["date"])
                except ValueError:
                    pass

            await db.flush()  # get show.id
            total_shows += 1

            # Fetch looks
            show_id = show_data.get("id", "")
            try:
                looks_data = await fetch_looks_for_show(show_id)
            except Exception as e:
                logger.error(f"[Ingest] Failed to fetch looks for {show_id}: {e}")
                continue

            for look_data in looks_data:
                look_num = look_data.get("look_number")

                result = await db.execute(
                    select(Look).where(
                        Look.show_id == show.id,
                        Look.look_number == look_num,
                    )
                )
                look: Optional[Look] = result.scalar_one_or_none()
                if look is None:
                    look = Look(show_id=show.id, look_number=look_num)
                    db.add(look)

                look.image_url  = look_data.get("image_url")
                look.materials  = look_data.get("materials", [])
                look.silhouettes= look_data.get("silhouette", [])
                look.colors     = look_data.get("colors", [])
                look.color_names= look_data.get("color_names", [])

                # Vision API tagging (if image_url present and not already tagged)
                if tag_images and look.image_url and not look.tagged_at:
                    tags = await tag_look_with_vision(look.image_url)
                    # Merge Tagwalk tags + Vision tags (deduplicated)
                    look.materials  = list(dict.fromkeys(look.materials + tags["materials"]))
                    look.silhouettes= list(dict.fromkeys(look.silhouettes + tags["silhouettes"]))
                    look.colors     = list(dict.fromkeys(look.colors + tags["colors"]))
                    look.color_names= list(dict.fromkeys(look.color_names + tags["color_names"]))
                    look.vision_raw = tags["raw"]
                    look.tagged_at  = datetime.now(timezone.utc)

                total_looks += 1

        await db.commit()

    logger.info(f"[Ingest] Done — {total_shows} shows, {total_looks} looks ingested.")
    return {
        "status":       "ok",
        "season":       season,
        "cities":       cities,
        "shows_indexed": total_shows,
        "looks_indexed": total_looks,
    }
