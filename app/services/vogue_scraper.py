"""
services/vogue_scraper.py — Scrape runway look image URLs from Vogue Runway pages.

Accepts a URL like:
    https://www.vogue.com/fashion-shows/fall-2026-ready-to-wear/gucci

First tries Vogue's internal slideshow API. If that fails, appends
/slideshow/collection, fetches the page, and extracts all look image URLs
from the slideshow gallery HTML.
"""
import logging
import re
from typing import List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.vogue.com",
    "Cookie": "",  # placeholder — populate with a valid session cookie if needed
}

# Matches Vogue's image CDN URLs for runway photos
_IMG_URL_RE = re.compile(r"https://assets\.vogue\.com/photos/[a-f0-9]+/")


def _normalise_url(url: str) -> str:
    """Ensure URL points to the /slideshow/collection sub-page."""
    url = url.rstrip("/")
    if not url.endswith("/slideshow/collection"):
        if "/slideshow" in url:
            url = url.rsplit("/slideshow", 1)[0] + "/slideshow/collection"
        else:
            url += "/slideshow/collection"
    return url


def _pick_best_src(img_tag) -> str | None:
    """Extract the highest-quality image URL from an <img> or <source> tag."""
    # Prefer srcset (usually has higher-res options), fall back to src
    srcset = img_tag.get("srcset", "")
    if srcset:
        # srcset format: "url1 width1w, url2 width2w, ..."
        # Pick the widest variant
        candidates = []
        for entry in srcset.split(","):
            parts = entry.strip().split()
            if len(parts) >= 1:
                src = parts[0]
                width = 0
                if len(parts) >= 2 and parts[1].endswith("w"):
                    try:
                        width = int(parts[1][:-1])
                    except ValueError:
                        pass
                candidates.append((width, src))
        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            return candidates[0][1]

    src = img_tag.get("src", "")
    if src and not src.startswith("data:"):
        return src

    return None


def _build_api_url(url: str) -> str | None:
    """Build the Vogue internal slideshow API URL from a show page URL.

    Expected path: /fashion-shows/<season>/<designer>[/slideshow/...]
    API pattern:   /api/v1/fashion-shows/<season>/<designer>/slideshow
    """
    path = urlparse(url).path.strip("/")
    # Remove any /slideshow/... suffix so we get clean season + designer
    path = re.sub(r"/slideshow.*$", "", path)
    parts = path.split("/")
    # parts should be ["fashion-shows", "<season>", "<designer>"]
    if len(parts) >= 3 and parts[0] == "fashion-shows":
        season = parts[1]
        designer = parts[2]
        return f"https://www.vogue.com/api/v1/fashion-shows/{season}/{designer}/slideshow"
    return None


async def _try_api(client: httpx.AsyncClient, api_url: str) -> List[str]:
    """Attempt to fetch look images from Vogue's internal slideshow API."""
    api_headers = {**_HEADERS, "Accept": "application/json"}
    resp = await client.get(api_url, headers=api_headers)
    resp.raise_for_status()
    data = resp.json()

    image_urls: list[str] = []
    seen: set[str] = set()

    # The API response typically nests images under a "slides" or "items" key.
    slides = data.get("slides") or data.get("items") or []
    if isinstance(data, list):
        slides = data

    for slide in slides:
        img_url = None
        # Try several known shapes the API may use
        if isinstance(slide, str):
            img_url = slide
        elif isinstance(slide, dict):
            img_url = (
                slide.get("photosTout", {}).get("url")
                or slide.get("image", {}).get("url")
                or slide.get("url")
                or slide.get("src")
            )
        if img_url and img_url not in seen:
            seen.add(img_url)
            image_urls.append(img_url)

    return image_urls


async def scrape_vogue_runway(url: str) -> List[str]:
    """
    Scrape all runway look image URLs from a Vogue Runway show page.

    Tries Vogue's internal slideshow API first; falls back to HTML scraping.

    Args:
        url: Vogue Runway show URL (e.g.
             https://www.vogue.com/fashion-shows/fall-2026-ready-to-wear/gucci)

    Returns:
        Deduplicated list of image URLs in look order.

    Raises:
        ValueError: If the URL doesn't look like a Vogue Runway page.
        httpx.HTTPStatusError: If the page returns a non-2xx status.
    """
    parsed = urlparse(url)
    if "vogue.com" not in parsed.netloc:
        raise ValueError(f"Not a Vogue URL: {url}")

    async with httpx.AsyncClient(
        headers=_HEADERS, follow_redirects=True, timeout=30.0
    ) as client:
        # --- Strategy 0: Vogue internal slideshow API -----------------------
        api_url = _build_api_url(url)
        if api_url:
            try:
                logger.info(f"[VogueScraper] Trying API {api_url}")
                api_results = await _try_api(client, api_url)
                if api_results:
                    logger.info(
                        f"[VogueScraper] API returned {len(api_results)} look images"
                    )
                    return api_results
                logger.info("[VogueScraper] API returned no images, falling back to HTML")
            except (httpx.HTTPStatusError, httpx.RequestError, ValueError, KeyError) as exc:
                logger.info(f"[VogueScraper] API failed ({exc}), falling back to HTML")

        # --- HTML scraping fallback -----------------------------------------
        page_url = _normalise_url(url)
        logger.info(f"[VogueScraper] Fetching {page_url}")
        resp = await client.get(page_url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    image_urls: list[str] = []
    seen: set[str] = set()

    # Strategy 1: Look for <img> tags inside the slideshow/gallery containers.
    # Vogue uses responsive images — check <picture> > <source> first, then <img>.
    for picture in soup.find_all("picture"):
        sources = picture.find_all("source")
        img = picture.find("img")
        best = None
        for source in sources:
            best = _pick_best_src(source)
            if best:
                break
        if not best and img:
            best = _pick_best_src(img)
        if best and best not in seen:
            seen.add(best)
            image_urls.append(best)

    # Strategy 2: If no <picture> tags found, fall back to standalone <img> tags
    # whose src matches the Vogue CDN pattern.
    if not image_urls:
        for img in soup.find_all("img"):
            src = _pick_best_src(img)
            if src and _IMG_URL_RE.search(src) and src not in seen:
                seen.add(src)
                image_urls.append(src)

    # Strategy 3: Extract from JSON-LD or inline script data.
    if not image_urls:
        for script in soup.find_all("script", type="application/ld+json"):
            text = script.string or ""
            urls = _IMG_URL_RE.findall(text)
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    image_urls.append(u)

    # Filter out non-runway images (thumbnails, logos, ads) by URL pattern.
    # Vogue runway photos live under assets.vogue.com/photos/
    runway_urls = [
        u for u in image_urls
        if "assets.vogue.com/photos/" in u or "assets.vogue.com/image/" in u
    ]

    # If filtering removed everything, return the unfiltered list — the caller
    # can inspect and decide.
    final = runway_urls if runway_urls else image_urls

    logger.info(f"[VogueScraper] Found {len(final)} look images from {page_url}")
    return final
