"""
news_trends.py — Google News RSS signal
Counts how many news articles mention a trend keyword in the past 30 days.
No API key required.
"""

import httpx
import feedparser
from datetime import datetime, timedelta, timezone
from urllib.parse import quote


def get_news_signal(keyword: str, days: int = 30) -> float:
    """
    Search Google News RSS for a keyword and return a 0-100 score
    based on article count and recency over the past `days` days.
    """
    try:
        encoded = quote(f"{keyword} fashion")
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        response = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; runwayfyi/1.0)"
        })
        if response.status_code != 200:
            return 0.0

        feed = feedparser.parse(response.text)
        entries = feed.entries

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = []

        for entry in entries:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published >= cutoff:
                    recent.append(entry)
            except Exception:
                recent.append(entry)  # include if date parsing fails

        count = len(recent)

        # Normalise: 20+ articles = score of 100, scale linearly below that
        score = min(100.0, (count / 20) * 100)
        return round(score, 2)

    except Exception as e:
        print(f"[news_trends] Error for '{keyword}': {e}")
        return 0.0


def get_news_signals_batch(keywords: list[str]) -> dict[str, float]:
    """Get news signals for multiple keywords."""
    results = {}
    for kw in keywords:
        results[kw] = get_news_signal(kw)
    return results
