#!/usr/bin/env python3
"""
vision_pipeline.py — Two-phase Vision pipeline for runway.fyi

PHASE 1: Tag all looks with Google Vision (run this first, takes ~45-60 min)
PHASE 2: Report all unique labels Vision found (run after phase 1 to review)

Usage:
  # Tag all looks:
  GOOGLE_VISION_API_KEY=your_key python3 vision_pipeline.py --phase 1

  # See what Vision found (review before updating trend_scorer.py):
  python3 vision_pipeline.py --phase 2

  # Tag only looks missing Vision data (faster if partially done):
  GOOGLE_VISION_API_KEY=your_key python3 vision_pipeline.py --phase 1 --missing-only
"""

import argparse
import json
import os
import time
import requests
from collections import defaultdict

RAILWAY_API = "https://fashion-backend-production-6880.up.railway.app"
VISION_KEY  = os.environ.get("GOOGLE_VISION_API_KEY", "")
DELAY       = 0.4   # seconds between Vision calls — slightly longer to avoid rate limits

# ── Vision API ────────────────────────────────────────────────────────────────

def call_vision(image_url: str) -> dict:
    """
    Call Google Vision on a single image URL.
    Returns dict with: materials, silhouettes, color_names, raw_labels
    """
    if not VISION_KEY:
        raise ValueError("GOOGLE_VISION_API_KEY not set")

    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={VISION_KEY}"
    payload = {
        "requests": [{
            "image": {"source": {"imageUri": image_url}},
            "features": [
                {"type": "LABEL_DETECTION",    "maxResults": 30},
                {"type": "OBJECT_LOCALIZATION","maxResults": 20},
                {"type": "IMAGE_PROPERTIES"},
            ]
        }]
    }

    for attempt in range(3):
        try:
            resp = requests.post(endpoint, json=payload, timeout=30)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3)
    data = resp.json()
    r = data.get("responses", [{}])[0]

    label_annotations  = r.get("labelAnnotations", [])
    object_annotations = r.get("localizedObjectAnnotations", [])
    color_data         = r.get("imagePropertiesAnnotation", {}).get("dominantColors", {}).get("colors", [])

    # Collect all labels (both label detection and object localization)
    all_labels = []
    for l in label_annotations:
        if l.get("score", 0) > 0.6:
            all_labels.append(l["description"].lower())

    for o in object_annotations:
        if o.get("score", 0) > 0.5:
            all_labels.append(o["name"].lower())

    # Extract dominant colors as hex
    colors = []
    for c in color_data[:5]:
        rgb = c.get("color", {})
        r_val = int(rgb.get("red", 0))
        g_val = int(rgb.get("green", 0))
        b_val = int(rgb.get("blue", 0))
        colors.append(f"#{r_val:02x}{g_val:02x}{b_val:02x}")

    # Classify labels into categories
    MATERIAL_KEYWORDS = {
        "leather","silk","satin","velvet","lace","tweed","boucle","shearling",
        "cashmere","wool","denim","cotton","chiffon","organza","sequin","fur",
        "suede","corduroy","knit","crochet","nylon","polyester","jersey",
        "feather","fringe","linen","taffeta","crepe","mesh","tulle","latex",
        "snakeskin","crocodile","patent","metallic","embroidery","print"
    }
    SILHOUETTE_KEYWORDS = {
        "coat","jacket","blazer","trouser","skirt","dress","gown","suit",
        "blouse","shirt","boot","heel","loafer","flat","bag","glove","hat",
        "scarf","vest","bodysuit","jumpsuit","cape","trench","parka","cardigan",
        "sweater","top","shorts","jeans","legging","pump","sandal","mule",
        "outerwear","overcoat","miniskirt","maxi","midi","wrap","slip",
        "turtleneck","crew neck","v-neck","sleeveless","strapless","off shoulder",
        "shoe","footwear","handbag","clutch","tote","belt","boot","sneaker"
    }
    COLOR_KEYWORDS = {
        "black","white","red","blue","green","yellow","pink","purple","orange",
        "brown","beige","cream","ivory","grey","gray","navy","camel","burgundy",
        "chocolate","forest","emerald","cobalt","scarlet","ochre","teal",
        "nude","tan","khaki","olive","rust","coral","mustard","lilac","mauve",
        "ecru","off-white","charcoal","taupe","blush","rose","champagne"
    }

    materials   = list({l for l in all_labels if any(k in l for k in MATERIAL_KEYWORDS)})
    silhouettes = list({l for l in all_labels if any(k in l for k in SILHOUETTE_KEYWORDS)})
    color_names = list({l for l in all_labels if any(k in l for k in COLOR_KEYWORDS)})
    raw_labels  = list(set(all_labels))

    return {
        "materials":   materials,
        "silhouettes": silhouettes,
        "color_names": color_names,
        "colors":      colors,
        "raw_labels":  raw_labels,
    }


# ── Railway API helpers ───────────────────────────────────────────────────────

def get_all_shows() -> list:
    resp = requests.get(f"{RAILWAY_API}/api/trends/shows", timeout=15)
    resp.raise_for_status()
    return resp.json()

def get_looks_for_show(show_id: int) -> list:
    resp = requests.get(f"{RAILWAY_API}/api/trends/shows/{show_id}/looks", timeout=15)
    resp.raise_for_status()
    return resp.json()

def patch_look(show_id: int, look_id: int, tags: dict):
    for attempt in range(3):
        try:
            requests.patch(
                f"{RAILWAY_API}/api/trends/shows/{show_id}/looks/{look_id}",
                json=tags, timeout=30
            )
            return
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)

def run_scoring():
    resp = requests.post(f"{RAILWAY_API}/api/trends/run-scoring", timeout=60)
    return resp.json()


# ── Phase 1: Tag all looks ────────────────────────────────────────────────────

def phase1_tag_looks(missing_only: bool = False):
    print("=" * 60)
    print("PHASE 1 — Tagging all looks with Google Vision")
    print("=" * 60)

    if not VISION_KEY:
        print("❌ GOOGLE_VISION_API_KEY not set. Export it first:")
        print("   export GOOGLE_VISION_API_KEY=your_actual_key")
        return

    shows = get_all_shows()
    print(f"\n📋 Found {len(shows)} shows\n")

    total_tagged = 0
    total_skipped = 0
    total_failed = 0
    all_labels_seen = defaultdict(int)  # label → count across all looks

    for i, show in enumerate(shows):
        show_id   = show.get("id")
        show_name = show.get("designer") or show.get("brand") or f"show_{show_id}"
        looks     = get_looks_for_show(show_id)

        if not looks:
            continue

        needs_tagging = [l for l in looks if not l.get("materials") and not l.get("raw_labels")] if missing_only else looks
        if not needs_tagging:
            print(f"[{i+1}/{len(shows)}] {show_name} — all {len(looks)} looks already tagged, skipping")
            total_skipped += len(looks)
            continue

        print(f"[{i+1}/{len(shows)}] {show_name} — tagging {len(needs_tagging)} looks...")

        for look in needs_tagging:
            look_id   = look.get("id")
            look_num  = look.get("look_number", "?")
            image_url = look.get("image_url", "")

            if not image_url:
                total_failed += 1
                continue

            try:
                tags = call_vision(image_url)
                patch_look(show_id, look_id, tags)

                # Accumulate label stats
                for label in tags["raw_labels"]:
                    all_labels_seen[label] += 1

                total_tagged += 1
                time.sleep(DELAY)

            except Exception as e:
                print(f"    ⚠ Look {look_num} failed: {e}")
                total_failed += 1
                time.sleep(DELAY)

    # Save label report to disk for Phase 2
    report = {
        "total_tagged": total_tagged,
        "total_skipped": total_skipped,
        "total_failed": total_failed,
        "labels": dict(sorted(all_labels_seen.items(), key=lambda x: x[1], reverse=True))
    }
    with open("vision_labels_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Phase 1 complete")
    print(f"   Tagged : {total_tagged}")
    print(f"   Skipped: {total_skipped}")
    print(f"   Failed : {total_failed}")
    print(f"   Labels report saved to: vision_labels_report.json")
    print(f"\n🏃 Running scoring pipeline...")
    result = run_scoring()
    print(f"   {result}")
    print(f"\n▶  Next: python3 vision_pipeline.py --phase 2")


# ── Phase 2: Report all labels ────────────────────────────────────────────────

def phase2_report_labels():
    print("=" * 60)
    print("PHASE 2 — Vision Label Report")
    print("=" * 60)

    # Try to load from saved report first
    if os.path.exists("vision_labels_report.json"):
        with open("vision_labels_report.json") as f:
            report = json.load(f)
        labels = report.get("labels", {})
        print(f"\nLoaded from vision_labels_report.json")
        print(f"Total looks tagged: {report.get('total_tagged', '?')}\n")
    else:
        # Pull directly from DB via API
        print("\nNo saved report found — fetching from Railway...\n")
        shows  = get_all_shows()
        labels = defaultdict(int)
        for show in shows:
            show_id = show.get("id")
            looks   = get_looks_for_show(show_id)
            for look in looks:
                for label in (look.get("raw_labels") or []):
                    labels[label.lower()] += 1
        labels = dict(sorted(labels.items(), key=lambda x: x[1], reverse=True))

    if not labels:
        print("❌ No labels found. Run Phase 1 first.")
        return

    # Print grouped report
    print(f"{'─'*60}")
    print(f"TOP 80 VISION LABELS (sorted by frequency across all looks)")
    print(f"{'─'*60}")
    print(f"{'LABEL':<35} {'COUNT':>6}")
    print(f"{'─'*60}")
    for label, count in list(labels.items())[:80]:
        print(f"{label:<35} {count:>6}")

    print(f"\n{'─'*60}")
    print("HOW TO USE THIS REPORT:")
    print("─"*60)
    print("""
1. Look through the labels above
2. Tell me which labels map to which FW26 trends
   e.g. "dress, gown → Column Dress"
        "coat, overcoat, outerwear → Oversized Coat"
        "shoe, footwear, high heels → Ballet Flats"
        "leather → Leather Outerwear"
3. I'll update TREND_KEYWORDS in trend_scorer.py exactly
4. Re-run: curl -X POST https://fashion-backend-production-6880.up.railway.app/api/trends/run-scoring
""")

    # Also save a clean text version
    with open("vision_labels_for_review.txt", "w") as f:
        f.write("Vision Labels Found Across All Looks\n")
        f.write("="*60 + "\n\n")
        for label, count in labels.items():
            f.write(f"{label:<35} {count}\n")
    print(f"Full label list saved to: vision_labels_for_review.txt")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vision pipeline for runway.fyi")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True,
                        help="1 = tag all looks, 2 = report labels")
    parser.add_argument("--missing-only", action="store_true",
                        help="Phase 1 only: skip looks that already have tags")
    args = parser.parse_args()

    if args.phase == 1:
        phase1_tag_looks(missing_only=args.missing_only)
    elif args.phase == 2:
        phase2_report_labels()
