#!/usr/bin/env python3
"""
runway fyi — SociaVault Social Signal Tracker
Tracks TikTok, Twitter/X, and Reddit for fashion trends.
Features:
  - Top 3 viral TikTok videos with titles, views, and direct links
  - Week-over-week trend direction (stores history in tracker_history.json)
  - Twitter/X search with correct deep-nested response parsing
  - Autonomous discovery mode (no keywords needed)

Usage:
  export SOCIAVAULT_API_KEY="your-key"

  python3 sociavault_tracker.py --hashtag ChanelFW26
  python3 sociavault_tracker.py --hashtag MatthieuBlazy
  python3 sociavault_tracker.py --mode discover
  python3 sociavault_tracker.py --mode weekly
  python3 sociavault_tracker.py --mode keywords
"""

import os, sys, json, time, re, argparse, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta

SOCIAVAULT_KEY = os.environ.get("SOCIAVAULT_API_KEY", "")
SV_API         = "https://api.sociavault.com/v1"
HISTORY_FILE   = os.path.expanduser("~/Desktop/tracker_history.json")

if not SOCIAVAULT_KEY:
    print("ERROR: Set SOCIAVAULT_API_KEY")
    sys.exit(1)

# ── Tracking Lists ─────────────────────────────────────────────────────────────

CD_HASHTAGS = [
    "DemnaGucci", "MatthieuBlazy", "JonathanAndersonDior",
    "AlessandroMichele", "GlennMartens", "PierpaoloPiccioli",
    "SarahBurton", "MichaelRider", "LouiseTrotter", "HaiderAckermann",
    "ChanelFW26", "DiorFW26", "GucciFW26", "ValentinoFW26",
    "Balenciaga", "BottegaVeneta", "Givenchy", "Celine", "Loewe",
]

COLLAB_HASHTAGS = [
    "GallianoZara", "WillyChavarria", "JohnGalliano",
]

CULTURE_HASHTAGS = [
    "FashionDiversity", "RunwayRepresentation", "BlackFashionDesigners",
    "FashionRacism", "CulturalAppropriation",
]

TREND_HASHTAGS = [
    "DarkRomance", "QuietLuxury", "MaximalistFashion",
    "WideLetTrousers", "MaxiCoat", "StatementDressing",
    "BurgundyFashion", "CobaltBlue", "DarkRomanceAesthetic",
]

# ── API Helper ─────────────────────────────────────────────────────────────────

def sv_get(endpoint: str, params: dict = None) -> dict:
    url = f"{SV_API}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("X-API-Key", SOCIAVAULT_KEY)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 402:
            print(f"  SociaVault: out of credits")
        elif e.code == 400:
            err = json.loads(body).get("error", body)
            print(f"  SociaVault 400: {err}")
        else:
            print(f"  SociaVault error {e.code}: {body[:120]}")
        return {}
    except Exception as e:
        print(f"  SociaVault error: {e}")
        return {}

# ── TikTok ─────────────────────────────────────────────────────────────────────

def get_tiktok_data(hashtag: str) -> dict:
    """
    Try hashtag search first (letters only), fall back to keyword search.
    Returns raw API data.
    """
    clean = re.sub(r'[^a-zA-Z]', '', hashtag)
    if clean:
        result = sv_get("scrape/tiktok/search/hashtag", {"hashtag": clean, "count": 20})
        data = result.get("data", {})
        if data and (data.get("aweme_list") or data.get("videos")):
            return data

    # Fallback: keyword search (handles numbers, spaces, multi-word)
    result = sv_get("scrape/tiktok/search/keyword", {"keyword": hashtag, "count": 20})
    return result.get("data", {})

def extract_videos(data: dict) -> list:
    """Normalise TikTok response into a clean list of video dicts."""
    raw = data.get("aweme_list") or data.get("videos") or data.get("items") or {}
    if isinstance(raw, dict):
        videos = list(raw.values())
    elif isinstance(raw, list):
        videos = raw
    else:
        return []

    results = []
    for v in videos:
        if not isinstance(v, dict):
            continue
        stats = v.get("statistics", {}) or {}

        def si(*keys):
            for k in keys:
                val = v.get(k) or stats.get(k)
                if val:
                    try: return int(val)
                    except: pass
            return 0

        views    = si("playCount", "play_count", "views")
        likes    = si("diggCount", "digg_count", "likes")
        comments = si("commentCount", "comment_count", "comments")
        shares   = si("shareCount", "share_count", "shares")

        # Build TikTok URL from aweme_id if available
        aweme_id = v.get("aweme_id") or v.get("id") or ""
        author   = v.get("author", {}) or {}
        username = author.get("unique_id") or author.get("uniqueId") or ""
        desc     = v.get("desc") or v.get("title") or v.get("description") or ""

        if aweme_id and username:
            url = f"https://www.tiktok.com/@{username}/video/{aweme_id}"
        else:
            url = ""

        results.append({
            "views":    views,
            "likes":    likes,
            "comments": comments,
            "shares":   shares,
            "desc":     desc[:120],
            "username": username,
            "url":      url,
            "aweme_id": str(aweme_id),
        })

    # Sort by views descending
    results.sort(key=lambda x: -x["views"])
    return results

def score_tiktok(videos: list) -> dict:
    """Fashion-calibrated signal score from video list."""
    if not videos:
        return {"score": 0, "label": "NO DATA", "avg_views": 0,
                "top_video": 0, "engagement": 0, "post_count": 0}

    view_counts = [v["views"] for v in videos]
    avg_views   = sum(view_counts) / len(view_counts) if view_counts else 0
    top_video   = max(view_counts) if view_counts else 0
    avg_eng     = sum(v["likes"] + v["comments"] for v in videos) / len(videos)

    # Fashion baseline: 500k avg = score 50, 2M avg = 100
    view_score = min(80, (avg_views / 2_000_000) * 80)
    top_bonus  = min(15, (top_video / 5_000_000) * 15)
    eng_bonus  = min(5,  (avg_eng / 50_000) * 5)
    score      = round(view_score + top_bonus + eng_bonus, 1)

    if avg_views >= 1_000_000:   label = "EXCEPTIONAL"
    elif avg_views >= 300_000:   label = "STRONG"
    elif avg_views >= 80_000:    label = "MODERATE"
    elif avg_views >= 15_000:    label = "LOW"
    else:                         label = "MINIMAL"

    return {
        "score":      score,
        "label":      label,
        "avg_views":  round(avg_views),
        "top_video":  top_video,
        "engagement": round(avg_eng),
        "post_count": len(videos),
    }

# ── Twitter/X ──────────────────────────────────────────────────────────────────

def search_twitter(query: str) -> list:
    """
    Search Twitter. The response is deeply nested inside:
    data.result.timeline.instructions[].entries[].content.itemContent.tweet_results.result.legacy
    We walk the tree to extract tweet texts and engagement.
    """
    result = sv_get("scrape/twitter/search", {"query": query, "count": 20})
    data   = result.get("data", {})
    if not data:
        return []

    tweets = []

    # Walk the deeply nested timeline structure
    try:
        instructions = (
            data.get("result", {})
                .get("timeline", {})
                .get("instructions", []) or []
        )
        for instruction in instructions:
            entries = instruction.get("entries", []) or []
            for entry in entries:
                content = entry.get("content", {}) or {}

                # Single tweet entry
                item_content = content.get("itemContent", {}) or {}
                tweet_result = item_content.get("tweet_results", {}).get("result", {}) or {}
                legacy = tweet_result.get("legacy", {}) or {}
                if legacy.get("full_text"):
                    tweets.append({
                        "text":     legacy.get("full_text", "")[:200],
                        "likes":    legacy.get("favorite_count", 0),
                        "retweets": legacy.get("retweet_count", 0),
                        "replies":  legacy.get("reply_count", 0),
                        "date":     legacy.get("created_at", ""),
                    })

                # Module entry (carousel of tweets)
                items = content.get("items", []) or []
                for item in items:
                    item2 = item.get("item", {}) or {}
                    ic2   = item2.get("itemContent", {}) or {}
                    tr2   = ic2.get("tweet_results", {}).get("result", {}) or {}
                    leg2  = tr2.get("legacy", {}) or {}
                    if leg2.get("full_text"):
                        tweets.append({
                            "text":     leg2.get("full_text", "")[:200],
                            "likes":    leg2.get("favorite_count", 0),
                            "retweets": leg2.get("retweet_count", 0),
                            "replies":  leg2.get("reply_count", 0),
                            "date":     leg2.get("created_at", ""),
                        })
    except Exception as e:
        print(f"  Twitter parse error: {e}")

    return tweets

# ── Reddit ──────────────────────────────────────────────────────────────────────

def search_reddit(query: str) -> list:
    result = sv_get("scrape/reddit/search", {"query": query, "limit": 10})
    data   = result.get("data", {})
    posts  = data.get("posts") or data.get("results") or data or {}
    if isinstance(posts, dict):
        posts = list(posts.values())
    elif not isinstance(posts, list):
        posts = []
    return [p for p in posts if isinstance(p, dict)]

# ── Week-over-Week History ─────────────────────────────────────────────────────

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_history(history: dict):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def get_wow_direction(hashtag: str, current_avg: int, history: dict) -> str:
    """Compare current avg_views against last week's stored value."""
    key      = hashtag.lower()
    prev     = history.get(key, {}).get("avg_views")
    if not prev or prev == 0:
        return "NEW ◆"
    change   = ((current_avg - prev) / prev) * 100
    if change >= 50:   return f"↑↑ +{round(change)}% WoW"
    elif change >= 15: return f"↑ +{round(change)}% WoW"
    elif change >= -15:return f"→ STABLE WoW"
    elif change >= -50:return f"↓ {round(change)}% WoW"
    else:              return f"↓↓ {round(change)}% WoW"

def store_snapshot(hashtag: str, signal: dict, history: dict):
    history[hashtag.lower()] = {
        "avg_views":  signal.get("avg_views", 0),
        "score":      signal.get("score", 0),
        "label":      signal.get("label", ""),
        "updated":    datetime.now().strftime("%Y-%m-%d"),
    }

# ── Modes ──────────────────────────────────────────────────────────────────────

def mode_hashtag(hashtag: str):
    """Full analysis for one hashtag: TikTok top videos + Twitter + Reddit + WoW."""
    history = load_history()
    print(f"\n  ── #{hashtag} ──")

    # TikTok
    print(f"  Fetching TikTok...")
    tt_data  = get_tiktok_data(hashtag)
    videos   = extract_videos(tt_data)
    signal   = score_tiktok(videos)
    wow      = get_wow_direction(hashtag, signal["avg_views"], history)
    store_snapshot(hashtag, signal, history)
    save_history(history)

    print(f"\n  TikTok Signal:   {signal['label']}  (score {signal['score']}/100)")
    print(f"  Avg views/video: {signal['avg_views']:>12,}  {wow}")
    print(f"  Top video:       {signal['top_video']:>12,}  views")
    print(f"  Engagement/vid:  {signal['engagement']:>12,}  likes+comments")
    print(f"  Videos sampled:  {signal['post_count']:>12}")

    # Top 3 videos
    if videos:
        print(f"\n  TOP VIDEOS:")
        for i, v in enumerate(videos[:3], 1):
            views_str = f"{v['views']:,}"
            eng_str   = f"{v['likes']+v['comments']:,} eng"
            desc      = v['desc'][:80] if v['desc'] else "(no description)"
            print(f"  {i}. {views_str} views · {eng_str}")
            print(f"     @{v['username']} — {desc}")
            if v['url']:
                print(f"     {v['url']}")
            print()

    # Twitter
    print(f"  Fetching Twitter/X...")
    tweets = search_twitter(hashtag)
    time.sleep(0.5)
    if tweets:
        total_eng = sum(t["likes"] + t["retweets"] for t in tweets)
        print(f"  Twitter results: {len(tweets)} tweets · {total_eng:,} total engagement")
        # Show top tweet
        top_tweet = max(tweets, key=lambda t: t["likes"] + t["retweets"])
        print(f"  Top tweet:       {top_tweet['likes']:,} likes · {top_tweet['retweets']:,} RTs")
        print(f"  \"{top_tweet['text'][:100]}\"")
    else:
        print(f"  Twitter results: 0")

    # Reddit
    print(f"\n  Fetching Reddit...")
    posts = search_reddit(hashtag)
    print(f"  Reddit results:  {len(posts)} posts")
    if posts:
        top_post = max(posts, key=lambda p: p.get("score", 0) or p.get("ups", 0))
        title    = top_post.get("title", "")[:80]
        score    = top_post.get("score") or top_post.get("ups", 0)
        if title:
            print(f"  Top post:        {score} upvotes — {title}")
    print()

def mode_weekly():
    """Run all hashtags, show ranked table with WoW direction."""
    history = load_history()
    all_hashtags = CD_HASHTAGS + COLLAB_HASHTAGS + CULTURE_HASHTAGS + TREND_HASHTAGS
    print(f"\n  Weekly Social Report · {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  {len(all_hashtags)} hashtags · TikTok signal\n")

    results = []
    for hashtag in all_hashtags:
        sys.stdout.write(f"  {hashtag:<30}")
        sys.stdout.flush()
        tt_data = get_tiktok_data(hashtag)
        videos  = extract_videos(tt_data)
        signal  = score_tiktok(videos)
        wow     = get_wow_direction(hashtag, signal["avg_views"], history)
        store_snapshot(hashtag, signal, history)
        results.append({"hashtag": hashtag, **signal, "wow": wow})
        print(f"  {signal['label']:<12}  avg {signal['avg_views']:>8,}/video  {wow}")
        time.sleep(0.4)

    save_history(history)

    print(f"\n  ── TOP 10 SIGNALS ──")
    top = sorted(results, key=lambda x: -x["score"])[:10]
    for i, r in enumerate(top, 1):
        print(f"  {i:>2}. #{r['hashtag']:<28} {r['label']:<12} {r['wow']}")

    output = f"social_weekly_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved: {output}")

def mode_discover():
    """Autonomous discovery — trending TikTok feed + popular hashtags, no keywords needed."""
    print("\n  Autonomous Discovery Mode")
    fashion_kws = {
        "fashion", "style", "outfit", "ootd", "designer", "runway", "vogue",
        "clothes", "clothing", "dress", "coat", "trend", "aesthetic", "luxury",
        "vintage", "streetwear", "couture", "editorial", "fw26", "fashionweek",
        "chanel", "dior", "gucci", "prada", "balenciaga", "loewe", "celine",
    }

    print("  Fetching TikTok trending feed...")
    trending_raw = sv_get("scrape/tiktok/trending")
    trending     = extract_videos(trending_raw.get("data", {}))

    print("  Fetching popular hashtags...")
    ht_raw  = sv_get("scrape/tiktok/popular/hashtags")
    ht_data = ht_raw.get("data", {}) or {}
    ht_list = ht_data.get("hashtags") or ht_data.get("items") or []
    if isinstance(ht_list, dict):
        ht_list = list(ht_list.values())

    discovered = []

    for v in trending:
        text = (v.get("desc", "") or "").lower()
        if any(k in text for k in fashion_kws):
            discovered.append({
                "type":   "trending_video",
                "desc":   v["desc"][:80],
                "views":  v["views"],
                "url":    v["url"],
                "source": "TikTok Trending",
            })

    for ht in ht_list:
        if not isinstance(ht, dict):
            continue
        tag   = (ht.get("hashtag") or ht.get("name") or ht.get("cha_name") or "").lower()
        views = ht.get("viewCount") or ht.get("view_count") or ht.get("video_count") or 0
        if any(k in tag for k in fashion_kws):
            discovered.append({
                "type":   "trending_hashtag",
                "tag":    tag,
                "views":  views,
                "source": "TikTok Popular Hashtags",
            })

    print(f"\n  Found {len(discovered)} fashion signals in trending data:\n")
    for d in discovered[:15]:
        if d["type"] == "trending_video":
            print(f"  VIDEO  {d['views']:>10,} views · {d['desc']}")
            if d["url"]:
                print(f"         {d['url']}")
        else:
            print(f"  TAG    #{d['tag']}  {d['views']:,} views")
    if not discovered:
        print("  No fashion content found in current trending feed.")

    return discovered

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["weekly", "discover", "keywords"],
                        default="weekly")
    parser.add_argument("--hashtag")
    args = parser.parse_args()

    print()
    print("  runway fyi — SociaVault Social Tracker")
    print("  ──────────────────────────────────────────")

    if args.hashtag:
        mode_hashtag(args.hashtag)
    elif args.mode == "discover":
        mode_discover()
    elif args.mode == "weekly":
        mode_weekly()
    elif args.mode == "keywords":
        print(f"\n  CD ({len(CD_HASHTAGS)}): {', '.join(CD_HASHTAGS)}")
        print(f"  Collabs ({len(COLLAB_HASHTAGS)}): {', '.join(COLLAB_HASHTAGS)}")
        print(f"  Culture ({len(CULTURE_HASHTAGS)}): {', '.join(CULTURE_HASHTAGS)}")
        print(f"  Trends ({len(TREND_HASHTAGS)}): {', '.join(TREND_HASHTAGS)}")
    print()

if __name__ == "__main__":
    main()
