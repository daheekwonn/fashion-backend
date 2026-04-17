#!/usr/bin/env python3
"""
trend_score_combiner.py — runwayfyi scoring pipeline
-----------------------------------------------------
Reads:
  - ~/Desktop/tracker_history.json       (SociaVault — social WoW velocity)
  - ~/Desktop/cultural_signals_*.json    (DataForSEO — search volume + score)
    → picks the most recently modified file automatically

Produces a unified trend score per keyword and POSTs to Railway:
  POST /api/trends/run-scoring

Combined score formula:
  unified_score = dataforseo_score (search intent)
                + sociavault_wow_bonus (social momentum)

  Where WoW direction maps to:
    NEW      →  +3.0   (first time appearing — emerging)
    +X% WoW  →  +2.0   (growing social momentum)
    stable   →  +0.5   (holding)
    -X% WoW  →  -1.0   (declining social signal)
    missing  →   0.0   (no social data for this keyword)

Usage:
  python3 ~/Desktop/trend_score_combiner.py
  python3 ~/Desktop/trend_score_combiner.py --dry-run   # prints scores, no POST
  python3 ~/Desktop/trend_score_combiner.py --verbose   # extra detail per keyword
"""

import os
import json
import glob
import argparse
import requests
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DESKTOP = Path.home() / "Desktop"
TRACKER_HISTORY_PATH = DESKTOP / "tracker_history.json"
RAILWAY_ENDPOINT = "https://fashion-backend-production-6880.up.railway.app/api/trends/run-scoring"

# WoW direction → score bonus
WOW_BONUS = {
    "new":      3.0,   # first appearance — treat as emerging
    "up":       2.0,   # growing WoW
    "stable":   0.5,   # holding steady
    "down":    -1.0,   # declining
    "missing":  0.0,   # no social data
}

# ── Explicit social key mapping ───────────────────────────────────────────────
# Maps each DataForSEO signal name → list of tracker_history.json keys to
# aggregate. Keys are normalised (lowercase, no spaces/hyphens/underscores).
# Multiple keys are averaged together into one social signal.
# Add new mappings here whenever you add signals to DataForSEO or SociaVault.

SIGNAL_TO_SOCIAL_KEYS = {
    # CD Appointments
    "matthieu blazy chanel":        ["matthieublazychanel", "matthieublazy", "chanelfallwinter", "matthieu blazy chanel"],
    "jonathan anderson dior":       ["jonathanandersondior", "diorfw26"],
    "demna gucci":                  ["demnagucci", "guccifw26"],
    "narfarvar balenciaga":         ["narfarvarbalenciaga", "balenciagafw26"],
    "louise trotter bottega veneta":["bottegaveneta", "bottegavenetafw26"],
    "simone bellotti jil sander":   ["jilsander", "jilsanderfw26"],
    "pierpaolo piccioli balenciaga":["picciolivalentino"],
    "jonathan anderson loewe":      ["jonathanandersonloewe", "loewefw26"],
    "michael rider celine":         ["celinefw26"],
    "sarah burton givenchy":        ["givenchyfw26"],
    "veronica leoni calvin klein":  [],
    "alessandro michele valentino": ["valentinofw26"],
    "glenn martens margiela":       [],
    "haider ackermann tom ford":    [],
    "julian klausner dries van noten": [],
    "peter copping lanvin":         ["lanvinfw26"],
    "david koma blumarine":         [],
    "duran lantink jean paul gaultier": [],
    "miguel castro freitas mugler": [],
    "mccollough hernandez loewe":   ["loewefw26"],

    # Collaborations
    "john galliano zara":           ["galliano", "johngalliano", "gallianozara", "gallianozaratt", "gallianocontroversytt"],
    "willy chavarria zara":         ["willychavarria", "willychavarrianyfw", "willychavarriazaratt"],
    "kate moss gucci fw26":         ["guccifw26"],
    "gabbriette gucci fw26":        ["guccifw26"],

    # Shows
    "chanel fw26 show":             ["chanelfallwinter", "chanelfw26", "lenamiuchaneltt", "imanekhelifchaneltt", "chaneldenimtt", "margotrobbiechaneltt"],
    "dior fw26 show":               ["diorfw26", "jonathanandersondior"],
    "valentino rome fw26":          ["valentinofw26"],

    # Trend keywords
    "velvet fashion 2026":          ["velvet"],
    "wide leg trousers trend":      ["widelegtrousers"],
    "co-ord set trend":             ["coordset"],
    "end of quiet luxury":          ["quietluxury", "quietluxuryovertt"],
    "cobalt blue fashion":          ["cobaltblue"],
    "burgundy wine fashion":        ["burgundyfashion"],
    "leather fashion fw26":         ["leatherbomber", "leatherouterwear"],
    "dark romance aesthetic":       [],
    "80s fashion revival":          [],
    "maxi coat trend":              [],
    "purple fashion trend":         [],
    "yellow fashion trend":         [],
}



def find_latest_cultural_signals() -> Path:
    """Return the most recently modified cultural_signals_*.json on Desktop."""
    pattern = str(DESKTOP / "cultural_signals_*.json")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(
            f"No cultural_signals_*.json found in {DESKTOP}. "
            "Run dataforseo_cultural.py first."
        )
    latest = max(files, key=os.path.getmtime)
    return Path(latest)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_wow_direction(history_entry: dict) -> str:
    """
    Read the WoW direction from a tracker_history.json entry.
    Expected keys: 'direction' → 'new' | 'up' | 'stable' | 'down'
    Falls back gracefully if structure differs.
    """
    direction = history_entry.get("direction", "").lower()
    if direction in ("new", "up", "stable", "down"):
        return direction
    # Try to infer from wow_pct if direction key is absent
    wow_pct = history_entry.get("wow_pct", None)
    if wow_pct is None:
        return "missing"
    if wow_pct > 5:
        return "up"
    elif wow_pct < -5:
        return "down"
    else:
        return "stable"


def build_social_index(tracker_history: dict) -> dict:
    """
    Build a normalised keyword → {direction, score, avg_views} lookup.
    tracker_history.json structure (from SociaVault):
      {
        "matthieublazy": {
          "avg_views": 102720,
          "score": 6.7,
          "label": "MODERATE",
          "updated": "2026-04-10"
        },
        ...
      }
    After multiple weeks, entries will also have "wow_pct" and "direction".
    This handles both single-week (score+label only) and multi-week (with WoW).
    """
    index = {}
    for raw_key, entry in tracker_history.items():
        # Normalise: lowercase, strip all spaces/hyphens/underscores
        norm = raw_key.lower().replace(" ", "").replace("-", "").replace("_", "").replace("#", "")
        
        # Derive direction from label or wow_pct
        if "direction" in entry:
            direction = entry["direction"].lower()
        elif "wow_pct" in entry:
            wow_pct = entry["wow_pct"]
            direction = "up" if wow_pct > 5 else ("down" if wow_pct < -5 else "stable")
        elif "label" in entry:
            # Single-week run — no WoW yet, use label as proxy
            label = entry["label"].upper()
            if label in ("HIGH", "EXCEPTIONAL"):
                direction = "stable"   # strong but no WoW to compare yet
            elif label in ("MODERATE",):
                direction = "stable"
            else:
                direction = "stable"   # default until we have 2+ weeks
        else:
            direction = "stable"

        index[norm] = {
            "direction":  direction,
            "wow_pct":    entry.get("wow_pct", 0),
            "avg_views":  entry.get("avg_views", 0),
            "score":      entry.get("score", 0),
            "label":      entry.get("label", ""),
            "raw_key":    raw_key,
        }
    return index


def find_social_match(keyword: str, social_index: dict):
    """
    Look up social data using the explicit SIGNAL_TO_SOCIAL_KEYS mapping.
    Aggregates multiple social keys into one signal where mapped.
    Returns None if no mapping or no matching keys found.
    """
    norm_kw = keyword.lower().strip()
    mapped_keys = SIGNAL_TO_SOCIAL_KEYS.get(norm_kw, None)
    if mapped_keys is None or not mapped_keys:
        return None

    # Collect matching entries from social index
    matches = []
    for key in mapped_keys:
        norm_key = key.lower().replace(" ", "").replace("-", "").replace("_", "").replace("#", "")
        if norm_key in social_index:
            matches.append(social_index[norm_key])

    if not matches:
        return None

    # Aggregate across multiple keys
    label_rank     = {"EXCEPTIONAL": 5, "STRONG": 4, "MODERATE": 3, "LOW": 2, "MINIMAL": 1, "": 0}
    direction_rank = {"up": 3, "new": 2, "stable": 1, "down": 0, "missing": -1}

    avg_views      = sum(m.get("avg_views", 0) for m in matches) / len(matches)
    best_label     = max((m.get("label", "") for m in matches), key=lambda l: label_rank.get(l, 0))
    best_direction = max((m.get("direction", "stable") for m in matches), key=lambda d: direction_rank.get(d, 0))
    best_wow_pct   = max((m.get("wow_pct", 0) for m in matches), default=0)
    best_score     = max((m.get("score", 0) for m in matches), default=0)

    return {
        "direction":   best_direction,
        "wow_pct":     best_wow_pct,
        "avg_views":   avg_views,
        "score":       best_score,
        "label":       best_label,
        "raw_key":     ", ".join(mapped_keys),
        "match_count": len(matches),
    }


def compute_unified_score(dataforseo_score: float, social_match) -> dict:
    """
    Compute unified trend score and assemble longevity classification.

    Score = DataForSEO score + WoW bonus
    Longevity:
      - 'spike'     → high DataForSEO score, social going down/missing after peak
      - 'sustained' → consistent/growing across both sources
      - 'emerging'  → social NEW with low/zero DataForSEO
      - 'social_only' → strong social, zero DataForSEO search signal
    """
    if social_match:
        direction = social_match["direction"]
        wow_bonus = WOW_BONUS.get(direction, 0.0)
        wow_pct   = social_match.get("wow_pct", 0)
        avg_views = social_match.get("avg_views", 0)
        label     = social_match.get("label", "")
    else:
        direction = "missing"
        wow_bonus = 0.0
        wow_pct   = 0
        avg_views = 0
        label     = ""

    unified = round(dataforseo_score + wow_bonus, 2)

    # Longevity classification
    if dataforseo_score == 0 and direction in ("new", "up"):
        longevity = "emerging"          # TikTok/social native, no search yet
    elif dataforseo_score > 5 and direction in ("down", "missing"):
        longevity = "spike"             # peaked and declining
    elif dataforseo_score > 5 and direction in ("stable", "up", "new"):
        longevity = "sustained"         # search + social both healthy
    elif dataforseo_score == 0 and direction in ("stable", "down", "missing"):
        longevity = "no_signal"         # runway trend, not converting
    else:
        longevity = "watch"             # inconclusive — needs more weeks

    return {
        "unified_score":    unified,
        "longevity":        longevity,
        "dataforseo_score": dataforseo_score,
        "social_direction": direction,
        "social_wow_pct":   wow_pct,
        "social_avg_views": avg_views,
        "social_wow_bonus": wow_bonus,
        "social_label":     label,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="runwayfyi trend score combiner")
    parser.add_argument("--dry-run",  action="store_true", help="Print scores, skip POST to Railway")
    parser.add_argument("--verbose",  action="store_true", help="Print per-keyword detail")
    args = parser.parse_args()

    # ── Load DataForSEO cultural signals ──────────────────────────────────────
    signals_path = find_latest_cultural_signals()
    print(f"📊 DataForSEO signals:  {signals_path.name}")

    cultural_signals = load_json(signals_path)
    # cultural_signals_*.json structure:
    #   [ { "keyword": "...", "search_volume": 1900, "score": 1.3, ... }, ... ]
    # or dict keyed by keyword — handle both
    if isinstance(cultural_signals, dict):
        signals_list = [
            {"keyword": k, **v} for k, v in cultural_signals.items()
        ]
    else:
        signals_list = cultural_signals

    # ── Load SociaVault tracker history ───────────────────────────────────────
    if not TRACKER_HISTORY_PATH.exists():
        print(f"⚠️  tracker_history.json not found at {TRACKER_HISTORY_PATH}")
        print("   Continuing with DataForSEO scores only (no social signal).")
        social_index = {}
    else:
        print(f"📱 SociaVault history:  {TRACKER_HISTORY_PATH.name}")
        social_index = build_social_index(load_json(TRACKER_HISTORY_PATH))

    print(f"\n   {len(signals_list)} DataForSEO keywords  ·  {len(social_index)} social entries\n")

    # ── Combine scores ────────────────────────────────────────────────────────
    results = []
    for item in signals_list:
        keyword         = item.get("signal", item.get("keyword", item.get("term", "unknown")))
        dataforseo_score = float(item.get("score", 0))
        search_volume   = item.get("volume", item.get("search_volume", 0))
        category        = item.get("category", "")

        norm_kw      = keyword  # explicit mapping uses original keyword string
        social_match = find_social_match(keyword, social_index)
        scored       = compute_unified_score(dataforseo_score, social_match)

        row = {
            "keyword":        keyword,
            "category":       category,
            "search_volume":  search_volume,
            **scored,
        }
        results.append(row)

        if args.verbose:
            if scored["social_direction"] != "missing":
                label_str = scored.get("social_label", "")
                views_str = f"{scored['social_avg_views']:,} avg views"
                social_label = f"{scored['social_direction'].upper()} [{label_str}] {views_str}"
            else:
                social_label = "no social match"
            print(
                f"  {keyword:<35} "
                f"SEO: {dataforseo_score:>5.1f}  "
                f"Social: {social_label:<50} "
                f"→ UNIFIED: {scored['unified_score']:>5.1f}  "
                f"[{scored['longevity']}]"
            )

    # ── Sort by unified score ─────────────────────────────────────────────────
    results.sort(key=lambda x: x["unified_score"], reverse=True)

    # ── Print summary table ───────────────────────────────────────────────────
    print("─" * 80)
    print(f"{'KEYWORD':<35} {'UNIFIED':>7}  {'LONGEVITY':<12}  {'SEO':>5}  {'SOCIAL':>6}")
    print("─" * 80)
    for r in results:
        social_str = (
            f"{r['social_direction'].upper():>6}"
            if r["social_direction"] != "missing"
            else "  —   "
        )
        print(
            f"  {r['keyword']:<33} "
            f"{r['unified_score']:>7.2f}  "
            f"{r['longevity']:<12}  "
            f"{r['dataforseo_score']:>5.1f}  "
            f"{social_str}"
        )
    print("─" * 80)

    # ── Longevity breakdown ───────────────────────────────────────────────────
    from collections import Counter
    counts = Counter(r["longevity"] for r in results)
    print(f"\n  Longevity breakdown:")
    for label, count in counts.most_common():
        print(f"    {label:<14} {count} keywords")

    # ── Build payload ─────────────────────────────────────────────────────────
    payload = {
        "run_at":         datetime.utcnow().isoformat() + "Z",
        "source_seo":     signals_path.name,
        "source_social":  "tracker_history.json" if social_index else None,
        "keyword_count":  len(results),
        "scores":         results,
    }

    # ── POST to Railway ───────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n  ✅ Dry run — skipping POST to Railway.")
        print(f"     Would POST {len(results)} scored keywords.")
    else:
        print(f"\n  🚀 POSTing {len(results)} scored keywords to Railway...")
        try:
            resp = requests.post(
                RAILWAY_ENDPOINT,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code in (200, 201):
                print(f"  ✅ Railway responded {resp.status_code}: {resp.text[:200]}")
            else:
                print(f"  ⚠️  Railway responded {resp.status_code}: {resp.text[:400]}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ POST failed: {e}")

    # ── Save local copy ───────────────────────────────────────────────────────
    out_path = DESKTOP / f"unified_scores_{datetime.utcnow().strftime('%Y%m%d')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  💾 Saved local copy: {out_path.name}\n")


if __name__ == "__main__":
    main()
