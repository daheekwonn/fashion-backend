#!/usr/bin/env python3
"""
runway fyi — Exa Weekly Scout
Runs every Sunday at 10pm. Autonomously discovers emerging fashion trends,
cultural moments, and keywords before they hit mainstream coverage.
Sends a digest email to summer@runwayfyi.com for approval before anything
gets added to DataForSEO tracking.

Usage:
  export EXA_API_KEY="your-exa-key"
  export ANTHROPIC_API_KEY="sk-ant-..."
  python3 exa_scout.py

  # Run specific category only:
  python3 exa_scout.py --category aesthetics

  # Dry run — no email sent:
  python3 exa_scout.py --dry-run

Schedule on Railway (cron):
  0 22 * * 0  python3 exa_scout.py  # Every Sunday at 10pm UTC
"""

import os, sys, json, time, argparse, urllib.request, urllib.error, smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Config ────────────────────────────────────────────────────────────────────

EXA_KEY       = os.environ.get("EXA_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RAILWAY_API   = "https://fashion-backend-production-6880.up.railway.app"
EXA_API       = "https://api.exa.ai/search"

SEND_TO       = "summer@runwayfyi.com"
SEND_FROM     = os.environ.get("EMAIL_FROM", "scout@runwayfyi.com")
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASS     = os.environ.get("SMTP_PASS", "")

if not EXA_KEY:
    print("ERROR: Set EXA_API_KEY")
    sys.exit(1)

# ── Scout Query Categories ────────────────────────────────────────────────────
# Exa is a neural search engine — it understands intent, not just keywords.
# These queries are designed to surface things you haven't thought of yet.

SCOUT_QUERIES = {

    "aesthetics": {
        "label": "Emerging Aesthetics & Subcultures",
        "queries": [
            "emerging fashion aesthetic subculture 2026 niche blog",
            "new micro trend fashion underground community this week",
            "aesthetic movement fashion growing popularity recent",
            "fashion subculture gaining traction social media 2026",
            "indie fashion aesthetic viral underreported",
        ],
        "purpose": "Discovers new aesthetics before they hit Google Trends. Exa finds niche blog coverage that DataForSEO can't surface.",
        "action": "Add top findings to DataForSEO tracking"
    },

    "cultural_criticism": {
        "label": "Race, Representation & Cultural Criticism",
        "queries": [
            "fashion industry racism diversity controversy recent week",
            "cultural appropriation fashion brand criticism 2026",
            "POC representation fashion industry data analysis recent",
            "fashion creative director diversity appointment criticism",
            "black fashion designers industry exclusion recent",
            "fashion week diversity failure report recent",
        ],
        "purpose": "Surfaces emerging conversations about race and representation that need editorial coverage.",
        "action": "Review for editorial content on runwayfyi.com"
    },

    "political_cultural": {
        "label": "Political & Cultural Events Affecting Fashion",
        "queries": [
            "political event fashion industry response this week",
            "economic indicator fashion consumer spending recent",
            "cultural moment fashion aesthetic shift recent",
            "social movement fashion industry impact 2026",
            "geopolitical event fashion luxury market recent",
        ],
        "purpose": "Connects macro events to fashion trends for contextual editorial content.",
        "action": "Review for contextual framing in articles"
    },

    "cd_appointments": {
        "label": "New Creative Director Appointments & Industry Moves",
        "queries": [
            "fashion creative director appointment 2026 new",
            "fashion house creative director change recent announcement",
            "designer leaving joining fashion brand recent news",
            "fashion industry executive appointment recent week",
        ],
        "purpose": "Tracks industry moves to add to spike analysis script.",
        "action": "Add new appointments to dataforseo_spike_analysis.py"
    },

    "viral_moments": {
        "label": "Viral Fashion Moments Not Yet in Mainstream Press",
        "queries": [
            "fashion show moment viral social media this week",
            "runway look viral tiktok instagram recent",
            "fashion week unexpected moment viral 2026",
            "fashion designer controversy viral recent week",
            "fashion campaign viral reaction recent",
        ],
        "purpose": "Catches ERD-type moments that DataForSEO misses — social virality that hasn't converted to search yet.",
        "action": "Add to SociaVault tracking and DataForSEO"
    },

    "collaboration_news": {
        "label": "Fashion Collaborations & Brand News",
        "queries": [
            "fashion brand collaboration announcement recent 2026",
            "designer x brand collaboration new this week",
            "luxury brand mass market collaboration recent",
            "fashion collab viral cultural reaction recent",
            "unexpected fashion collaboration announcement 2026",
        ],
        "purpose": "Tracks new collabs to add to DataForSEO monitoring.",
        "action": "Add to dataforseo_cultural.py collaborations section"
    },

    "historical_context": {
        "label": "Historical Fashion Parallels & Academic Research",
        "queries": [
            "fashion history parallel current trend academic recent",
            "historical fashion event anniversary relevance today",
            "fashion academic research publication recent 2026",
            "fashion history repeating current season analysis",
        ],
        "purpose": "Surfaces historical parallels for Firecrawl Wayback research.",
        "action": "Queue for Firecrawl historical research"
    },
}

# ── API Helpers ───────────────────────────────────────────────────────────────

def exa_search(query: str, num_results: int = 5, days_back: int = 7) -> list:
    """
    Search Exa using the exa-py SDK (avoids Cloudflare 403 blocks).
    Install first: pip3 install exa-py
    Falls back to raw HTTP if SDK not installed.
    """
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try SDK first — avoids Cloudflare blocks
    try:
        from exa_py import Exa
        exa    = Exa(api_key=EXA_KEY)
        result = exa.search_and_contents(
            query,
            type="auto",
            num_results=num_results,
            start_published_date=start_date,
            highlights={"max_characters": 4000},
        )
        return [
            {
                "title":      r.title or "",
                "url":        r.url or "",
                "text":       r.text or "",
                "highlights": r.highlights or [],
                "published":  getattr(r, "published_date", "") or "",
            }
            for r in (result.results or [])
        ]
    except ImportError:
        print("  exa-py not installed — run: pip3 install exa-py")
    except Exception as e:
        print(f"  Exa SDK error: {e}")
        return []

    # Fallback: raw HTTP
    payload = {
        "query":              query,
        "numResults":         num_results,
        "type":               "auto",
        "startPublishedDate": start_date,
        "contents":           {"highlights": {"maxCharacters": 4000}},
    }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(EXA_API, data=data)
    req.add_header("x-api-key", EXA_KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "runwayfyi-scout/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("results", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Exa HTTP error {e.code}: {body[:200]}")
        return []
    except Exception as e:
        print(f"  Exa error: {e}")
        return []

def synthesise_with_claude(category_label: str, results: list, purpose: str) -> dict:
    """Use Claude to synthesise Exa results into actionable intelligence."""
    # Re-read key each call in case environment updated after script start
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key or not results:
        return {"summary": "No synthesis available", "keywords": [], "action_items": []}

    # Format results for Claude
    content = f"Category: {category_label}\nPurpose: {purpose}\n\nResults found this week:\n\n"
    for i, r in enumerate(results[:8], 1):
        content += f"{i}. {r.get('title', 'No title')}\n"
        content += f"   URL: {r.get('url', '')}\n"
        highlights = r.get("highlights", [])
        if highlights:
            content += f"   Key excerpt: {' '.join(highlights[:2])}\n"
        text = r.get("text", "")
        if text:
            content += f"   Content: {text[:400]}\n"
        content += "\n"

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 600,
        "system": """You are the editorial intelligence engine for runway fyi, a fashion trend and cultural analysis platform.
Analyse these weekly Exa scout results and extract:
1. The 3 most significant findings (1-2 sentences each)
2. New keywords to add to DataForSEO tracking (max 5, specific and searchable)
3. Specific action items (e.g. "write article about X", "add Y to spike tracker", "research Z via Wayback")
4. One editorial angle for runwayfyi.com

Format as JSON:
{
  "top_findings": ["finding 1", "finding 2", "finding 3"],
  "new_keywords": ["keyword 1", "keyword 2"],
  "action_items": ["action 1", "action 2"],
  "editorial_angle": "one sentence pitch"
}""",
        "messages": [{"role": "user", "content": content}]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", anthropic_key)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
        text = result["content"][0]["text"].strip()
        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"summary": text, "keywords": [], "action_items": []}
    except Exception as e:
        return {"summary": f"Synthesis error: {e}", "keywords": [], "action_items": []}

def send_digest_email(weekly_results: list, dry_run: bool = False):
    """Send the weekly digest email to summer@runwayfyi.com."""

    # Build HTML email
    now = datetime.now().strftime("%B %d, %Y")
    week_start = (datetime.now() - timedelta(days=7)).strftime("%B %d")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Courier New', monospace; background: #F5F2ED; color: #0C0B09; margin: 0; padding: 0; }}
  .wrapper {{ max-width: 680px; margin: 0 auto; background: #fff; }}
  .header {{ background: #0C0B09; padding: 32px 40px; }}
  .header h1 {{ color: #fff; font-size: 22px; font-weight: 700; letter-spacing: 0.06em; margin: 0; text-transform: lowercase; }}
  .header p {{ color: rgba(255,255,255,0.5); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; margin: 8px 0 0; }}
  .intro {{ padding: 28px 40px 20px; border-bottom: 1px solid #eee; }}
  .intro p {{ font-size: 13px; color: #555; line-height: 1.7; margin: 0; }}
  .category {{ padding: 24px 40px; border-bottom: 1px solid #eee; }}
  .cat-label {{ font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: #A09A94; margin: 0 0 4px; }}
  .cat-title {{ font-size: 18px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 16px; }}
  .finding {{ background: #F5F2ED; padding: 12px 16px; margin: 8px 0; font-size: 12px; line-height: 1.6; }}
  .finding::before {{ content: "→ "; color: #A09A94; }}
  .keywords {{ margin: 12px 0 0; }}
  .kw-label {{ font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: #A09A94; margin: 0 0 6px; }}
  .kw {{ display: inline-block; background: #0C0B09; color: #fff; font-size: 10px; padding: 3px 8px; margin: 2px; letter-spacing: 0.06em; }}
  .actions {{ margin: 12px 0 0; }}
  .action {{ font-size: 11px; color: #444; padding: 4px 0; border-left: 2px solid #0C0B09; padding-left: 10px; margin: 4px 0; }}
  .angle {{ background: #0C0B09; color: #fff; padding: 10px 16px; margin: 12px 0 0; font-size: 12px; font-style: italic; }}
  .sources {{ padding: 4px 0; }}
  .source {{ font-size: 10px; color: #A09A94; display: block; margin: 2px 0; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .footer {{ background: #F5F2ED; padding: 20px 40px; }}
  .footer p {{ font-size: 10px; color: #A09A94; letter-spacing: 0.08em; margin: 4px 0; }}
  .approve-btn {{ display: inline-block; background: #0C0B09; color: #fff; padding: 12px 24px; text-decoration: none; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; margin: 4px 4px 4px 0; }}
  .cta {{ padding: 20px 40px; border-top: 1px solid #eee; }}
  h3 {{ font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: #555; margin: 0 0 8px; font-weight: 400; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>runway fyi</h1>
    <p>Weekly Scout | {week_start} to {now}</p>
  </div>
  <div class="intro">
    <p>Your autonomous Exa scout found the following this week. Review each category and approve which keywords should be added to DataForSEO tracking. Nothing is added automatically.</p>
  </div>
"""

    all_new_keywords = []
    all_action_items = []

    for cat in weekly_results:
        cat_key = cat["category_key"]
        cat_label = cat["category_label"]
        synthesis = cat.get("synthesis", {})
        sources = cat.get("sources", [])

        findings = synthesis.get("top_findings", [])
        keywords = synthesis.get("new_keywords", [])
        actions = synthesis.get("action_items", [])
        angle = synthesis.get("editorial_angle", "")

        all_new_keywords.extend(keywords)
        all_action_items.extend(actions)

        html += f"""
  <div class="category">
    <p class="cat-label">{cat_key.replace('_', ' ')}</p>
    <h2 class="cat-title">{cat_label}</h2>
"""
        if findings:
            html += '<h3>Key Findings</h3>'
            for f in findings:
                html += f'<div class="finding">{f}</div>'

        if keywords:
            html += '<div class="keywords"><p class="kw-label">Suggested keywords to track</p>'
            for kw in keywords:
                html += f'<span class="kw">{kw}</span>'
            html += '</div>'

        if actions:
            html += '<div class="actions">'
            for a in actions:
                html += f'<div class="action">{a}</div>'
            html += '</div>'

        if angle:
            html += f'<div class="angle">"{angle}"</div>'

        if sources:
            html += '<div class="sources" style="margin-top:12px">'
            html += '<p class="kw-label">Sources found</p>'
            for s in sources[:4]:
                url = s.get("url", "")
                title = s.get("title", url)
                html += f'<a class="source" href="{url}">{title[:80]}</a>'
            html += '</div>'

        html += '</div>'

    # Summary CTA
    html += f"""
  <div class="cta">
    <h3>This week: {len(all_new_keywords)} new keywords suggested · {len(all_action_items)} action items</h3>
    <p style="font-size:12px;color:#444;line-height:1.7;margin:8px 0 16px">Reply to this email with which keywords you want to add to DataForSEO, or forward this to add them manually via the scripts.</p>
    <a class="approve-btn" href="mailto:summer@runwayfyi.com?subject=Exa Scout Approval {now}">Reply to approve keywords →</a>
  </div>
  <div class="footer">
    <p>runway fyi · Autonomous Scout · Every Sunday 10pm</p>
    <p>Powered by Exa.ai neural search · Synthesised by Claude</p>
    <p>To stop receiving: set EXA_SCOUT_ENABLED=false in Railway env vars</p>
  </div>
</div>
</body>
</html>
"""

    # Clean non-ASCII characters that break SMTP
    html = html

    if dry_run:
        print("\n  [DRY RUN] Email not sent. HTML preview:")
        print(f"  To: {SEND_TO}")
        print(f"  Subject: runway fyi Weekly Scout - {now}")
        print(f"  Body: {len(html)} chars HTML")
        print(f"\n  All new keywords suggested: {all_new_keywords}")
        print(f"  All action items: {all_action_items}")
        return

    # Send via SMTP
    if not SMTP_USER or not SMTP_PASS:
        print("\n  SMTP credentials not set. Saving email to scout_digest.html instead.")
        with open("scout_digest.html", "w") as f:
            f.write(html)
        print("  Open scout_digest.html in your browser to preview.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = ("runway fyi Weekly Scout - " + now).encode("ascii", "ignore").decode("ascii")
        msg["From"]    = SEND_FROM
        msg["To"]      = SEND_TO
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print(f"\n  ✓ Email sent to {SEND_TO}")
    except Exception as e:
        print(f"\n  Email error: {e}")
        print("  Saving to scout_digest.html instead.")
        with open("scout_digest.html", "w") as f:
            f.write(html)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--category", help=f"Run one category only: {', '.join(SCOUT_QUERIES.keys())}")
    parser.add_argument("--days-back", type=int, default=7, help="How many days back to search (default: 7)")
    args = parser.parse_args()

    print()
    print("  runway fyi — Exa Weekly Scout")
    print("  ──────────────────────────────────────")
    print(f"  Searching last {args.days_back} days")
    if args.dry_run:
        print("  DRY RUN — email will not be sent")
    print()

    categories = SCOUT_QUERIES
    if args.category:
        if args.category not in SCOUT_QUERIES:
            print(f"  ERROR: '{args.category}' not found.")
            print(f"  Available: {', '.join(SCOUT_QUERIES.keys())}")
            sys.exit(1)
        categories = {args.category: SCOUT_QUERIES[args.category]}

    weekly_results = []

    for cat_key, cat_data in categories.items():
        print(f"  ── {cat_data['label']} ──")

        all_sources = []
        for query in cat_data["queries"]:
            print(f"  Searching: {query[:60]}")
            results = exa_search(query, num_results=3, days_back=args.days_back)
            all_sources.extend(results)
            time.sleep(0.5)

        # Deduplicate by URL
        seen_urls = set()
        unique_sources = []
        for s in all_sources:
            url = s.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(s)

        print(f"  Found {len(unique_sources)} unique sources")

        # Synthesise with Claude
        import time as _time
        _time.sleep(3)  # Avoid Claude rate limiting between categories
        synthesis = synthesise_with_claude(
            cat_data["label"],
            unique_sources,
            cat_data["purpose"]
        )

        weekly_results.append({
            "category_key": cat_key,
            "category_label": cat_data["label"],
            "purpose": cat_data["purpose"],
            "action": cat_data["action"],
            "sources": unique_sources,
            "synthesis": synthesis,
        })

        print(f"  → {len(synthesis.get('new_keywords', []))} new keywords found")
        print(f"  → {len(synthesis.get('action_items', []))} action items")
        print()

    # Save raw results
    output_file = f"exa_scout_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, "w") as f:
        json.dump(weekly_results, f, indent=2)
    print(f"  Raw results saved: {output_file}")

    # Send digest email
    send_digest_email(weekly_results, dry_run=args.dry_run)

    # Summary
    total_sources = sum(len(r["sources"]) for r in weekly_results)
    total_keywords = sum(len(r.get("synthesis", {}).get("new_keywords", [])) for r in weekly_results)
    print()
    print(f"  ── DONE ──")
    print(f"  {total_sources} sources scanned")
    print(f"  {total_keywords} new keywords to review")
    print()

if __name__ == "__main__":
    main()
