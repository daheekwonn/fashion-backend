#!/usr/bin/env python3
"""
sociavault_monday_run.py — runwayfyi
-------------------------------------
Runs all SociaVault tracking in sequence every Monday.
Covers all 6 batches: FW26 shows, CD appointments, Galliano,
news topics, trend keywords, and Exa Scout findings.

Usage:
  python3 ~/Desktop/sociavault_monday_run.py
  python3 ~/Desktop/sociavault_monday_run.py --dry-run    # prints commands, doesn't run them
  python3 ~/Desktop/sociavault_monday_run.py --batch 3    # run one batch only
  python3 ~/Desktop/sociavault_monday_run.py --skip 1,5   # skip specific batches
"""

import subprocess
import sys
import time
import argparse
import os
from datetime import datetime

# ── Load environment variables from ~/.zshrc ──────────────────────────────────
# subprocess doesn't inherit zshrc env vars — parse and inject them explicitly
def load_zshrc_env():
    zshrc = os.path.expanduser("~/.zshrc")
    if not os.path.exists(zshrc):
        return
    with open(zshrc, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key.isidentifier():
                    os.environ.setdefault(key, val)

load_zshrc_env()

TRACKER = "python3 ~/Desktop/api/sociavault_tracker.py"

# ── All tracking targets ───────────────────────────────────────────────────────
# Each entry: (batch_number, batch_label, flag, value)
# flag is either "--hashtag" or "--mode news --topic"

# ── Date windows ──────────────────────────────────────────────────────────────
# Update these at the start of each new season.
# Shows + CDs: main fashion week window
FW_START = "2026-02-17"   # earliest show (NYFW opens)
FW_END   = "2026-03-14"   # latest show (Paris closes)

# Galliano/Zara: announcement came after fashion week, wider window
COLLAB_START = "2026-03-01"
COLLAB_END   = None        # up to present

# Trends + news + Exa: no date filter — ongoing cultural signals
NO_FILTER_START = None
NO_FILTER_END   = None

BATCHES = {

    1: {
        "label": "FW26 Shows",
        "note": "Official show hashtags — TikTok signal. FW26 and AW26 both tracked (EU/UK publications use AW).",
        "date_start": FW_START,
        "date_end":   FW_END,
        "items": [
            # Paris
            ("--hashtag", "CHANELFallWinter"),
            ("--hashtag", "DiorFW26"),
            ("--hashtag", "DiorAW26"),
            ("--hashtag", "SaintLaurentFW26"),
            ("--hashtag", "SaintLaurentAW26"),
            ("--hashtag", "LoeWeFW26"),
            ("--hashtag", "LoeweAW26"),
            # Valentino — show was in Rome, broader tags perform better than #ValentinoFW26
            ("--hashtag", "MaisonValentino"),
            ("--hashtag", "ValentinoAW26"),
            ("--hashtag", "ValentinoGaravani"),
            ("--hashtag", "BottegaVenetaFW26"),
            ("--hashtag", "BottegaVenetaAW26"),
            ("--hashtag", "GucciFW26"),
            ("--hashtag", "GucciAW26"),
            ("--hashtag", "BalenciagaFW26"),
            ("--hashtag", "BalenciagaAW26"),
            ("--hashtag", "CelineFW26"),
            ("--hashtag", "CelineAW26"),
            ("--hashtag", "GivenchyFW26"),
            ("--hashtag", "GivenchyAW26"),
            ("--hashtag", "HermesFW26"),
            ("--hashtag", "HermesAW26"),
            ("--hashtag", "MiumiuFW26"),
            ("--hashtag", "MiumiuAW26"),
            ("--hashtag", "LanvinFW26"),
            ("--hashtag", "LanvinAW26"),
            ("--hashtag", "CourregesFW26"),
            ("--hashtag", "CourregesAW26"),
            ("--hashtag", "RickOwensFW26"),
            ("--hashtag", "RickOwensAW26"),
            ("--hashtag", "AnnDemeulemeesterFW26"),
            ("--hashtag", "AnnDemeulemeesterAW26"),
            ("--hashtag", "MarnieFW26"),
            ("--hashtag", "MarnieAW26"),
            # Milan
            ("--hashtag", "PradaFW26"),
            ("--hashtag", "PradaAW26"),
            ("--hashtag", "FendiFW26"),
            ("--hashtag", "FendiAW26"),
            ("--hashtag", "VersaceFW26"),
            ("--hashtag", "VersaceAW26"),
            ("--hashtag", "MoschinoFW26"),
            ("--hashtag", "MoschinoAW26"),
            ("--hashtag", "MaxMaraFW26"),
            ("--hashtag", "MaxMaraAW26"),
            ("--hashtag", "JilSanderFW26"),
            ("--hashtag", "JilSanderAW26"),
            ("--hashtag", "DolceGabbanaFW26"),
            ("--hashtag", "DolceGabbanaAW26"),
            ("--hashtag", "EtroFW26"),
            ("--hashtag", "EtroAW26"),
            ("--hashtag", "SportmaxFW26"),
            ("--hashtag", "SportmaxAW26"),
            # London
            ("--hashtag", "BurberryFW26"),
            ("--hashtag", "BurberryAW26"),
            ("--hashtag", "SimoneRochaFW26"),
            ("--hashtag", "SimoneRochaAW26"),
            ("--hashtag", "ErdemFW26"),
            ("--hashtag", "ErdemAW26"),
            ("--hashtag", "ChetLoFW26"),
            ("--hashtag", "ChetLoAW26"),
            # New York
            ("--hashtag", "WillyChavarriaNYFW"),
            ("--hashtag", "ThomBrowneFW26"),
            ("--hashtag", "ThomBrowneAW26"),
            ("--hashtag", "ProenzaSchoulderFW26"),
            ("--hashtag", "ProenzaSchoulderAW26"),
            ("--hashtag", "MarcJacobsFW26"),
            ("--hashtag", "MarcJacobsAW26"),
            # ERD — use full name only, #ERD pulls Elden Ring noise
            ("--hashtag", "EnfantsRichesDeprimes"),
        ]
    },

    2: {
        "label": "Creative Director Appointments",
        "note": "New era excitement + outgoing CD nostalgia. Maps to DataForSEO CD signals.",
        "date_start": FW_START,
        "date_end":   FW_END,
        "items": [
            ("--hashtag", "MatthieuBlazyChanel"),
            ("--hashtag", "JonathanAndersonDior"),
            ("--hashtag", "DemnaGucci"),
            ("--hashtag", "NarfarvarBalenciaga"),
            # Outgoing CD nostalgia — DataForSEO found these spiking
            ("--hashtag", "PiccioliValentino"),
            ("--hashtag", "JonathanAndersonLoewe"),
            # Highest spike scores of FW26 season
            ("--hashtag", "BottegaVeneta"),
            ("--hashtag", "JilSander"),
            # New appointments from Exa Scout April 3-10
            ("--hashtag", "ZendayaLawRoach"),
            ("--hashtag", "StefanoGabbana"),
        ]
    },

    3: {
        "label": "Galliano",
        "note": "Track all three hashtags separately — each represents a different audience. "
                "Zara audience vs fashion community signal is a publishable distinction.",
        "date_start": COLLAB_START,
        "date_end":   COLLAB_END,
        "items": [
            ("--hashtag", "Galliano"),
            ("--hashtag", "JohnGalliano"),
            ("--hashtag", "GallianoZara"),
            # Twitter/Reddit accountability discourse
            ("--mode news --topic", "galliano_zara"),
            ("--mode news --topic", "galliano_controversy"),
        ]
    },

    4: {
        "label": "Collaborations & Cultural News",
        "note": "Pre-built news topics in sociavault_tracker.py. Twitter + Reddit signal.",
        "date_start": NO_FILTER_START,
        "date_end":   NO_FILTER_END,
        "items": [
            ("--mode news --topic", "willy_chavarria_zara"),
            ("--mode news --topic", "chanel_denim"),
            ("--mode news --topic", "margot_robbie_chanel"),
            ("--mode news --topic", "quiet_luxury_over"),
            ("--mode news --topic", "fashion_diversity_news"),
            ("--mode news --topic", "fashion_industry_news"),
            ("--mode news --topic", "imane_khelif_chanel"),
            ("--mode news --topic", "lena_miu_chanel"),
        ]
    },

    5: {
        "label": "Consumer Trend Keywords",
        "note": "Maps to DataForSEO trend signals. Cobalt blue / burgundy / co-ord sets "
                "currently have ZERO search signal — watching for TikTok-to-search conversion.",
        "date_start": NO_FILTER_START,
        "date_end":   NO_FILTER_END,
        "items": [
            # Currently have search signal
            ("--hashtag", "velvet"),
            ("--hashtag", "widelegtrousers"),
            ("--hashtag", "leatherbomber"),
            ("--hashtag", "leatherouterwear"),
            ("--hashtag", "maximalism"),
            # Zero search signal — watch for emergence
            ("--hashtag", "cobaltblue"),
            ("--hashtag", "burgundyfashion"),
            ("--hashtag", "coordset"),
            ("--hashtag", "quietluxury"),
        ]
    },

    6: {
        "label": "Exa Scout Findings",
        "note": "New stories surfaced by Exa this week (April 3-10). "
                "Update this batch each Sunday after your digest arrives.",
        "date_start": NO_FILTER_START,
        "date_end":   NO_FILTER_END,
        "items": [
            ("--hashtag", "plussize"),
            ("--hashtag", "AIfashion"),
            ("--hashtag", "WillyChavarria"),
            ("--hashtag", "QueenElizabethfashion"),
            ("--hashtag", "ancestralfashion"),
        ]
    },

}

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_command(flag: str, value: str, start_date: str = None, end_date: str = None) -> str:
    """Build the full shell command for a SociaVault run."""
    date_flags = ""
    if start_date:
        date_flags += f' --start-date "{start_date}"'
    if end_date:
        date_flags += f' --end-date "{end_date}"'

    if flag.startswith("--mode news --topic"):
        return f"python3 ~/Desktop/api/sociavault_tracker.py --mode news --topic {value}{date_flags}"
    else:
        return f'python3 ~/Desktop/api/sociavault_tracker.py {flag} "{value}"{date_flags}'


def run_command(cmd: str, dry_run: bool) -> bool:
    """Run a command and return True if successful."""
    if dry_run:
        print(f"    [DRY RUN] {cmd}")
        return True
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            executable="/bin/bash",
            capture_output=False,
            text=True,
            env=os.environ,   # pass loaded env vars including SOCIAVAULT_API_KEY
        )
        return result.returncode == 0
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="runwayfyi Monday SociaVault runner")
    parser.add_argument("--dry-run",  action="store_true", help="Print commands without running them")
    parser.add_argument("--batch",    type=int, help="Run a single batch number only (1-6)")
    parser.add_argument("--skip",     type=str, help="Comma-separated batch numbers to skip, e.g. --skip 1,5")
    args = parser.parse_args()

    skip_batches = set()
    if args.skip:
        skip_batches = {int(x.strip()) for x in args.skip.split(",")}

    batches_to_run = (
        [args.batch] if args.batch
        else [b for b in BATCHES if b not in skip_batches]
    )

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  runway fyi · SociaVault Monday Run")
    print(f"  {datetime.now().strftime('%A %d %B %Y · %H:%M')}")
    if args.dry_run:
        print("  MODE: DRY RUN — no commands will execute")
    if skip_batches:
        print(f"  Skipping batches: {sorted(skip_batches)}")
    total_items = sum(
        len(BATCHES[b]["items"]) for b in batches_to_run if b in BATCHES
    )
    print(f"  Running {len(batches_to_run)} batches · {total_items} total tracking calls")
    print("=" * 70)

    # ── Run batches ───────────────────────────────────────────────────────────
    summary = {}

    for batch_num in batches_to_run:
        if batch_num not in BATCHES:
            print(f"\n⚠️  Batch {batch_num} not found — skipping.")
            continue

        batch = BATCHES[batch_num]
        items = batch["items"]

        print(f"\n{'─' * 70}")
        print(f"  BATCH {batch_num} — {batch['label'].upper()}")
        print(f"  {batch['note']}")
        print(f"  {len(items)} items")
        batch_start = batch.get("date_start")
        batch_end   = batch.get("date_end")
        date_label  = (
            f"{batch_start} → {batch_end or 'present'}"
            if batch_start else "no date filter"
        )
        print(f"  Date window: {date_label}")
        print(f"{'─' * 70}\n")

        passed = 0
        failed = 0
        failed_items = []

        for i, (flag, value) in enumerate(items, 1):
            cmd = build_command(flag, value, start_date=batch_start, end_date=batch_end)
            label = value
            print(f"  [{i}/{len(items)}] {label}")

            success = run_command(cmd, args.dry_run)

            if success:
                passed += 1
            else:
                failed += 1
                failed_items.append(value)

            # Small pause between calls to avoid rate limiting
            if not args.dry_run and i < len(items):
                time.sleep(2)

        summary[batch_num] = {
            "label":   batch["label"],
            "total":   len(items),
            "passed":  passed,
            "failed":  failed,
            "failed_items": failed_items,
        }

        status = "✅" if failed == 0 else "⚠️ "
        print(f"\n  {status} Batch {batch_num} complete — {passed}/{len(items)} successful")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    total_passed = sum(s["passed"] for s in summary.values())
    total_failed = sum(s["failed"] for s in summary.values())

    for batch_num, s in summary.items():
        status = "✅" if s["failed"] == 0 else "⚠️ "
        print(f"  {status} Batch {batch_num} {s['label']:<35} {s['passed']}/{s['total']}")
        if s["failed_items"]:
            for item in s["failed_items"]:
                print(f"       ❌ failed: {item}")

    print(f"\n  Total: {total_passed} passed · {total_failed} failed")
    print()

    if total_failed == 0:
        print("  ✅ All done. tracker_history.json is updated.")
        print()
        print("  Next step — run the scoring combiner:")
        print("  python3 ~/Desktop/trend_score_combiner.py --dry-run --verbose")
        print()
        print("  Then if scores look right, POST to Railway:")
        print("  python3 ~/Desktop/trend_score_combiner.py")
    else:
        print(f"  ⚠️  {total_failed} items failed. Check SociaVault credits and API key.")
        print("  Re-run failed batches with: --batch N")

    print()


if __name__ == "__main__":
    main()
