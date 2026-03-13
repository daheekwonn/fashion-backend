"""
services/vogue_scraper.py — Scrape runway look image URLs from Vogue Runway pages.
Uses Playwright for full JS rendering to capture all look images.
"""
import logging
import re
import asyncio
from typing import List

logger = logging.getLogger(__name__)

_EXCLUDED_SUBSTRINGS = (".svg", "logo", "static", "/verso/", "profile-pic", "w_80")

def _is_runway_photo(url: str) -> bool:
    url_lower = url.lower()
    return not any(sub in url_lower for sub in _EXCLUDED_SUBSTRINGS)

async def scrape_vogue_runway(page_url: str) -> List[str]:
    """
    Scrape all look image URLs from a Vogue Runway show page using Playwright.
    Scrolls the full page to trigger lazy-loaded images.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[VogueScraper] Playwright not installed")
        return []

    image_urls = []
    seen = set()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            await page.goto(page_url, wait_until="networkidle", timeout=60000)

            # Scroll down slowly to trigger lazy loading
            for i in range(20):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await asyncio.sleep(0.5)

            # Get all image sources
            images = await page.evaluate("""
                () => {
                    const imgs = document.querySelectorAll('img');
                    return Array.from(imgs).map(img => img.src || img.dataset.src || '').filter(Boolean);
                }
            """)

            await browser.close()

            for url in images:
                if url and url not in seen and _is_runway_photo(url) and 'assets.vogue.com/photos' in url:
                    seen.add(url)
                    image_urls.append(url)

    except Exception as e:
        logger.error(f"[VogueScraper] Playwright error: {e}")
        return []

    # Deduplicate by photo ID to avoid same look in multiple resolutions
    deduped = {}
    for url in image_urls:
        match = re.search(r'/photos/([a-f0-9]+)/', url)
        if match:
            photo_id = match.group(1)
            if photo_id not in deduped:
                deduped[photo_id] = url

    final = list(deduped.values())
    logger.info(f"[VogueScraper] Found {len(final)} look images from {page_url}")
    return final
