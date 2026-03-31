#!/usr/bin/env python3
"""
run_social_scores.py — Run Google News + Reddit social scoring locally
and POST results directly to Railway.

Why local? Railway's shared IP is blocked by Google News RSS and Reddit's
bot detection. Running locally bypasses this entirely.

Usage:
  cd ~/Desktop/fashion-backend
  python3 run_social_scores.py

Requirements:
  pip3 install httpx feedparser requests
"""

import httpx
import feedparser
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

RAILWAY_API = "https://fashion-backend-production-6880.up.railway.app"
DELAY = 1.5  # seconds between Google News requests — be polite

# ── FW26 trend keyword aliases (from news_trends.py) ─────────────────────────
KEYWORD_ALIASES = {
    "Leather Outerwear": ["leather jacket 2026", "leather coat", "leather outerwear"],
    "Shearling":         ["shearling coat 2026", "shearling jacket", "sheepskin fashion"],
    "Ballet Flats":      ["ballet flats trend 2026", "ballet flat shoes", "ballet flats"],
    "Mary Janes":        ["mary jane shoes trend 2026", "mary jane fashion"],
    "Wide-Leg Tailoring":["wide leg trousers 2026", "wide leg pants trend"],
    "Power Suiting":     ["power suit trend 2026", "oversized suit fashion"],
    "Prairie Dress":     ["prairie dress trend 2026", "cottagecore 2026"],
    "Sheer Layers":      ["sheer fashion trend 2026", "transparent clothing trend"],
    "Boucle Tweed":      ["tweed fashion 2026", "boucle coat trend"],
    "Velvet":            ["velvet fashion 2026", "velvet clothing trend"],
    "Satin":             ["satin dress trend 2026", "satin fashion"],
    "Lace":              ["lace fashion trend 2026", "lace clothing"],
    "Camel":             ["camel coat 2026", "camel color fashion trend"],
    "Chocolate Brown":   ["chocolate brown fashion 2026", "brown clothing trend"],
    "Ivory & Cream":     ["ivory fashion 2026", "cream color trend fashion"],
    "Forest Green":      ["forest green fashion 2026", "dark green clothing trend"],
    "Burgundy":          ["burgundy fashion 2026", "wine color trend"],
    "Cobalt Blue":       ["cobalt blue fashion 2026", "bright blue clothing"],
    "Oversized Coat":    ["oversized coat trend 2026", "cocoon coat fashion"],
    "Trench Coat":       ["trench coat trend 2026", "classic trench"],
    "Column Dress":      ["column dress 2026", "minimal dress trend"],
    "Slip Dress":        ["slip dress trend 2026", "bias cut dress"],
    "Pleated Trousers":  ["pleated trousers 2026", "pleat pants trend"],
    "Kitten Heels":      ["kitten heel trend 2026", "low heel shoes"],
    "Knee-High Boots":   ["knee high boots 2026", "tall boot trend"],
}

# ── Reddit search terms ────────────────────────────────────────────────────────
REDDIT_ALIASES = {
    "Leather Outerwear": "leather jacket fashion 2026",
    "Shearling":         "shearling coat fashion",
    "Ballet Flats":      "ballet flats trend",
    "Mary Janes":        "mary jane shoes fashion",
    "Wide-Leg Tailoring":"wide leg pants fashion",
    "Power Suiting":     "power suit fashion 2026",
    "Prairie Dress":     "prairie dress cottagecore",
    "Boucle Tweed":      "tweed boucle fashion",
    "Velvet":            "velvet fashion trend",
    "Satin":             "satin dress fashion",
    "Lace":              "lace fashion trend",
    "Camel":             "camel coat fashion",
    "Chocolate Brown":   "chocolate brown fashion",
    "Burgundy":          "burgundy fashion trend",
    "Oversized Coat":    "oversized coat fashion",
    "Column Dress":      "column dress fashion",
}

# ── Google News RSS ────────────────────────────────────────────────────────────

def search_google_news(query: str, days: int = 30) -> int:
    try:
        encoded = quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        response = httpx.get(url, timeout=12, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        if response.status_code != 200:
            print(f"  ⚠ News HTTP {response.status_code} for '{query}'")
            return 0
        feed = feedparser.parse(response.text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        for entry in feed.entries:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published >= cutoff:
                    count += 1
            except Exception:
                count += 1
        return count
    except Exception as e:
        print(f"  ⚠ News error for '{query}': {e}")
        return 0


def get_news_signal(keyword: str) -> float:
    count = search_google_news(f"{keyword} fashion", 30)
    time.sleep(DELAY)
    aliases = KEYWORD_ALIASES.get(keyword, [])
    for alias in aliases[:2]:
        count += search_google_news(alias, 30)
        time.sleep(DELAY)
    return min(100.0, round((count / 30) * 100, 2))


# ── Reddit public JSON API ─────────────────────────────────────────────────────

def get_reddit_signal(keyword: str) -> float:
    try:
        query = REDDIT_ALIASES.get(keyword, f"{keyword} fashion")
        url = f"https://www.reddit.com/search.json?q={quote(query)}&sort=new&limit=25&t=month"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "runwayfyi-scorer/1.0 (fashion trend research)"
        })
        if resp.status_code != 200:
            return 0.0
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        total_score = sum(p["data"].get("score", 0) for p in posts)
        # Normalize: 500+ total upvotes = 100 signal
        return min(100.0, round((total_score / 500) * 100, 2))
    except Exception as e:
        print(f"  ⚠ Reddit error for '{keyword}': {e}")
        return 0.0


# ── Fetch all trend items from Railway ────────────────────────────────────────

def get_trend_items():
    resp = requests.get(f"{RAILWAY_API}/api/trends/all", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # Handle both list and dict response formats
    if isinstance(data, list):
        return data
    return data.get("items", data.get("trends", []))


# ── POST social scores back to Railway ────────────────────────────────────────

def post_social_scores(scores: dict):
    """
    POST social scores to Railway.
    Endpoint: POST /api/trends/ingest/social
    Body: { "scores": { "Leather Outerwear": 45.2, ... } }
    """
    resp = requests.post(
        f"{RAILWAY_API}/api/trends/ingest/social",
        json={"scores": scores},
        timeout=30
    )
    if resp.status_code == 404:
        print("\n⚠ /api/trends/ingest/social endpoint not found.")
        print("  You need to add this endpoint to your backend first.")
        print("  Saving scores to social_scores.json instead...")
        with open("social_scores.json", "w") as f:
            json.dump(scores, f, indent=2)
        print("  ✅ Saved to social_scores.json")
        return False
    resp.raise_for_status()
    print(f"  ✅ Posted to Railway: {resp.json()}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("📡 Fetching trend items from Railway...")
    try:
        items = get_trend_items()
        print(f"   Found {len(items)} trend items")
    except Exception as e:
        print(f"❌ Failed to fetch trends: {e}")
        # Fall back to known FW26 items
        items = [{"name": k} for k in KEYWORD_ALIASES.keys()]
        print(f"   Using {len(items)} fallback items")

    scores = {}
    print(f"\n🔍 Running social scoring for {len(items)} items...\n")

    for i, item in enumerate(items):
        name = item.get("name", item) if isinstance(item, dict) else item
        print(f"[{i+1}/{len(items)}] {name}")

        news  = get_news_signal(name)
        reddit = get_reddit_signal(name)
        social = round((news * 0.8) + (reddit * 0.2), 2)

        scores[name] = {
            "news_score":   news,
            "reddit_score": reddit,
            "social_score": social,
        }

        print(f"   News: {news:.1f}  Reddit: {reddit:.1f}  → Social: {social:.1f}")
        time.sleep(0.5)

    print(f"\n{'─'*50}")
    print("📊 Top 10 social scores:")
    top = sorted(scores.items(), key=lambda x: x[1]["social_score"], reverse=True)[:10]
    for name, s in top:
        print(f"   {s['social_score']:5.1f}  {name}")

    print(f"\n📤 Posting to Railway...")
    flat_scores = {name: s["social_score"] for name, s in scores.items()}
    posted = post_social_scores(flat_scores)

    if not posted:
        print("\n💡 Next step: add the /api/trends/ingest/social endpoint to Railway backend")
        print("   Then re-run this script to push scores automatically.")
    else:
        print("\n🏃 Re-running scoring pipeline...")
        resp = requests.post(f"{RAILWAY_API}/api/trends/run-scoring", timeout=60)
        print(f"   Scoring pipeline: {resp.json()}")

    print("\n✅ Done! Check leaderboard:")
    print(f"   curl {RAILWAY_API}/api/trends/leaderboard | python3 -m json.tool")


if __name__ == "__main__":
    main()
