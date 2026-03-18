"""
reddit_trends.py — Reddit social signal
Queries r/femalefashionadvice, r/streetwear, r/fashionadvice for keyword mentions.
Uses Reddit's public JSON API — no API key required for read-only access.
"""

import httpx
from datetime import datetime, timedelta, timezone


FASHION_SUBREDDITS = [
    "femalefashionadvice",
    "streetwear",
    "fashionadvice",
    "malefashionadvice",
    "fashion",
]

HEADERS = {
    "User-Agent": "runwayfyi/1.0 (fashion trend analysis platform; contact: studio@runwayfyi.com)"
}


def search_subreddit(subreddit: str, keyword: str, limit: int = 25) -> list[dict]:
    """Search a subreddit for posts mentioning a keyword."""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": keyword,
            "restrict_sr": "true",
            "sort": "new",
            "limit": limit,
            "t": "month",
        }
        r = httpx.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("data", {}).get("children", [])
    except Exception as e:
        print(f"[reddit_trends] Error searching r/{subreddit} for '{keyword}': {e}")
        return []


def get_reddit_signal(keyword: str) -> float:
    """
    Get a 0-100 Reddit engagement score for a keyword.
    Based on post count + upvote velocity across fashion subreddits.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        total_posts = 0
        total_score = 0

        for subreddit in FASHION_SUBREDDITS:
            posts = search_subreddit(subreddit, keyword)
            for post in posts:
                data = post.get("data", {})
                created = datetime.fromtimestamp(
                    data.get("created_utc", 0), tz=timezone.utc
                )
                if created >= cutoff:
                    total_posts += 1
                    total_score += data.get("score", 0)

        if total_posts == 0:
            return 0.0

        # Combine post count and engagement score
        # 10+ posts = max post score (50), 500+ upvotes = max engagement score (50)
        post_score = min(50.0, (total_posts / 10) * 50)
        engagement_score = min(50.0, (total_score / 500) * 50)

        return round(post_score + engagement_score, 2)

    except Exception as e:
        print(f"[reddit_trends] Error for '{keyword}': {e}")
        return 0.0


def get_reddit_signals_batch(keywords: list[str]) -> dict[str, float]:
    """Get Reddit signals for multiple keywords."""
    results = {}
    for kw in keywords:
        results[kw] = get_reddit_signal(kw)
    return results
