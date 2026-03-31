#!/usr/bin/env python3
"""
manual_trend_tags.py — Manually set runway counts for each FW26 trend.

HOW TO USE:
1. Go through each trend below
2. Fill in `runway_count` (total looks across all shows)
3. Fill in `shows` (list of show names that featured this trend)
4. Run: python3 manual_trend_tags.py

The script will POST each trend's counts to Railway and re-run scoring.

TIPS:
- runway_count = total number of looks that featured this trend
  e.g. if Gucci had 20 leather looks and Saint Laurent had 15 = 35
- shows = just the show names, the script counts them automatically
- Leave runway_count as 0 if you're not sure — search+social will carry it
- Shows list is for your reference; show count is auto-calculated from len(shows)
"""

import requests
import json

RAILWAY_API = "https://fashion-backend-production-6880.up.railway.app"

# ─────────────────────────────────────────────────────────────────────────────
# FILL THIS IN — go through each trend and set the counts
# Current status shown for reference:
#   ✅ = already has runway data    ⚠ = missing runway data (0 looks)
# ─────────────────────────────────────────────────────────────────────────────

TREND_TAGS = {

    # ── OUTERWEAR ─────────────────────────────────────────────────────────────

    "Leather Outerwear": {  # ✅ currently: 1062 looks, 72 shows
        "runway_count": 1062,  # keep or update
        "shows": [
            "Gucci", "Saint Laurent", "Bottega Veneta", "Balenciaga",
            "Loewe", "Celine", "Burberry", "Diesel", "Rick Owens",
            "Mugler", "Givenchy", "Fendi", "Tom Ford", "McQueen",
            # add more shows here...
        ],
    },

    "Shearling": {  # ⚠ currently: 1 look, 1 show (WAY too low)
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Bottega Veneta", "Loewe", "Max Mara", "Stella McCartney"
        ],
    },

    "Oversized Coat": {  # ⚠ currently: 0 looks, 7 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Max Mara", "Burberry", "Toteme", "Lemaire"
        ],
    },

    "Trench Coat": {  # ⚠ currently: 0 looks, 0 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Burberry", "Celine", "Toteme", "Lemaire"
        ],
    },

    # ── DRESSES ───────────────────────────────────────────────────────────────

    "Column Dress": {  # ⚠ currently: 0 looks, 7 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Bottega Veneta", "Jil Sander", "Celine", "Hermes"
        ],
    },

    "Prairie Silhouette": {  # ⚠ currently: 0 looks, 6 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Chloe", "Zimmermann", "Erdem", "Simone Rocha"
        ],
    },

    "Slip Dress": {  # ⚠ currently: 0 looks, 0 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Saint Laurent", "Tom Ford", "Gucci"
        ],
    },

    # ── TAILORING ─────────────────────────────────────────────────────────────

    "Wide-Leg Tailoring": {  # ⚠ currently: 0 looks, 8 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Prada", "Bottega Veneta", "Loewe", "Khaite", "Jil Sander"
        ],
    },

    "Power Suiting": {  # ⚠ currently: 0 looks, 8 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Gucci", "Saint Laurent", "Balmain", "Givenchy", "McQueen"
        ],
    },

    "Pleated Trousers": {  # ⚠ currently: 0 looks, 0 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Prada", "Miu Miu", "Loewe"
        ],
    },

    # ── FOOTWEAR ──────────────────────────────────────────────────────────────

    "Ballet Flats": {  # ⚠ currently: 0 looks, 7 shows
        "runway_count": 0,  # fill in — Chanel had 52 alone (pony hair)
        "shows": [
            # e.g. "Chanel", "Miu Miu", "Prada", "Chloe", "Sandy Liang"
        ],
    },

    "Mary Janes": {  # ⚠ currently: 0 looks, 6 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Miu Miu", "Sandy Liang", "Simone Rocha"
        ],
    },

    "Kitten Heels": {  # ⚠ currently: 0 looks, 0 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Valentino", "Dior", "Chanel", "Ferragamo"
        ],
    },

    "Knee-High Boots": {  # ⚠ currently: 0 looks, 0 shows
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Balenciaga", "Rick Owens", "Celine", "Bottega Veneta"
        ],
    },

    # ── MATERIALS ─────────────────────────────────────────────────────────────

    "Lace": {  # ✅ currently: 72 looks, 20 shows — check if accurate
        "runway_count": 72,  # keep or update
        "shows": [
            "Valentino", "Dolce & Gabbana", "Givenchy", "Nina Ricci",
            "Erdem", "Simone Rocha",
            # add more...
        ],
    },

    "Velvet": {  # ✅ currently: 69 looks, 23 shows — check if accurate
        "runway_count": 69,  # keep or update
        "shows": [
            "Gucci", "Valentino", "Tom Ford", "Roberto Cavalli",
            # add more...
        ],
    },

    "Shearling": {  # ⚠ duplicate — handled above in outerwear
        "runway_count": 0,
        "shows": [],
    },

    "Boucle": {  # ⚠ currently: 0 looks, 4 shows
        "runway_count": 0,  # fill in — Chanel FW26 had heavy tweed/boucle
        "shows": [
            # e.g. "Chanel", "Chanel" (38/52 looks were tweed per session notes!)
        ],
    },

    "Satin": {  # ⚠ currently: 1 look, 1 show
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Tom Ford", "Saint Laurent", "Gucci"
        ],
    },

    # ── COLORS ────────────────────────────────────────────────────────────────

    "Camel": {  # ✅ currently: 952 looks, 85 shows — from hex detection
        "runway_count": 952,
        "shows": [],  # too many to list — hex detection handles this
    },

    "Chocolate Brown": {  # ✅ currently: 549 looks, 85 shows — from hex
        "runway_count": 549,
        "shows": [],
    },

    "Burgundy": {  # ⚠ currently: 0 looks (hex detection not matching)
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Gucci", "Bottega Veneta", "Valentino"
        ],
    },

    "Ivory & Cream": {  # ⚠ currently: 1 look
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "The Row", "Toteme", "Lemaire", "Jil Sander"
        ],
    },

    "Forest Green": {  # ⚠ currently: 0 looks
        "runway_count": 0,  # fill in
        "shows": [],
    },

    # ── ACCESSORIES ───────────────────────────────────────────────────────────

    "Oversized Tote": {  # ⚠ currently: 0 looks
        "runway_count": 0,  # fill in
        "shows": [],
    },

    "Shoulder Bag": {  # ⚠ currently: 0 looks
        "runway_count": 0,  # fill in
        "shows": [],
    },

    # ── AESTHETICS ────────────────────────────────────────────────────────────

    "Quiet Luxury": {  # ⚠ currently: 0 looks
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "The Row", "Toteme", "Lemaire", "Hermes", "Jil Sander"
        ],
    },

    "Romantic Dressing": {  # ⚠ currently: 0 looks
        "runway_count": 0,  # fill in
        "shows": [
            # e.g. "Valentino", "Simone Rocha", "Erdem", "Giambattista Valli"
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# DO NOT EDIT BELOW THIS LINE
# ─────────────────────────────────────────────────────────────────────────────

def post_tag(trend_name: str, runway_count: int, runway_show_count: int):
    resp = requests.post(
        f"{RAILWAY_API}/api/trends/manual-tag",
        json={
            "trend_name": trend_name,
            "runway_count": runway_count,
            "runway_show_count": runway_show_count,
        },
        timeout=15,
    )
    return resp.ok, resp.json() if resp.ok else resp.text


def main():
    print("=" * 60)
    print("Posting manual trend tags to Railway...")
    print("=" * 60)

    success = 0
    errors = []

    for trend_name, data in TREND_TAGS.items():
        # Skip duplicates and empty entries
        if trend_name == "Shearling" and data["runway_count"] == 0 and not data["shows"]:
            continue

        runway_count = data["runway_count"]
        show_count = len(data["shows"]) if data["shows"] else 0

        # If no show list provided, keep existing show count
        # by passing 0 (backend will skip if 0)
        ok, result = post_tag(trend_name, runway_count, show_count)

        status = "✅" if ok else "❌"
        print(f"{status} {trend_name}: {runway_count} looks, {show_count} shows")

        if ok:
            success += 1
        else:
            errors.append(f"{trend_name}: {result}")

    print(f"\n{'─'*60}")
    print(f"Posted: {success}/{len(TREND_TAGS)}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e}")

    print("\n🏃 Re-running scoring pipeline...")
    resp = requests.post(f"{RAILWAY_API}/api/trends/run-scoring", timeout=60)
    print(f"   {resp.json()}")

    print("\n✅ Done. Check the leaderboard:")
    print(f"   curl {RAILWAY_API}/api/trends/leaderboard | python3 -m json.tool")


if __name__ == "__main__":
    main()
