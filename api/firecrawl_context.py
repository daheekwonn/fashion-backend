#!/usr/bin/env python3
"""
runway fyi — Firecrawl Cultural Context Engine
Scrapes fashion publications and historical sources to provide cultural,
social, and political context for trend analysis.

Three modes:
  1. designer  — Pull historical press coverage for a CD across years
  2. cultural  — Pull historical context (recessions, politics) for a date window
  3. wayback   — Scrape a specific archived page from the Wayback Machine
  4. topic     — Run a pre-built research topic
  5. list-topics — Show all available topics

Usage:
  export FIRECRAWL_API_KEY="fc-..."
  export ANTHROPIC_API_KEY="sk-ant-..."

  python3 firecrawl_context.py --mode list-topics
  python3 firecrawl_context.py --mode topic --topic-key galliano_racism
  python3 firecrawl_context.py --mode topic --topic-key poc_representation_runway
  python3 firecrawl_context.py --mode topic --topic-key post_war_japan_fashion
  python3 firecrawl_context.py --mode designer --query "Rei Kawakubo" --years 1981,1990,2000,2010,2017,2026
  python3 firecrawl_context.py --mode wayback --url "https://vogue.com/article/galliano-dior" --date 2011-02-25
"""

import os, sys, json, time, argparse, urllib.request, urllib.error, urllib.parse
from datetime import datetime

FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FIRECRAWL_API = "https://api.firecrawl.dev/v2"
WAYBACK_API   = "https://archive.org/wayback/available"

if not FIRECRAWL_KEY:
    print("ERROR: Set FIRECRAWL_API_KEY")
    sys.exit(1)

# ── Research Topics ────────────────────────────────────────────────────────────

RESEARCH_TOPICS = {

    # ── RACE & REPRESENTATION ─────────────────────────────────────────────────

    "galliano_racism": {
        "label": "John Galliano — Racism, Antisemitism, and the Industry's Short Memory",
        "queries": [
            "john galliano racist antisemitic rant 2011 dior fired",
            "galliano blackface caricatures fashion shows controversy",
            "fashion industry forgiveness galliano redemption arc margiela",
            "john galliano zara creative director appointment controversy 2024",
            "fashion industry accountability racism short memory galliano",
            "galliano antisemitism trial paris 2011 dior",
        ],
        "date_from": "2011-01-01",
        "date_to": "2026-01-01",
        "context": "Galliano's 2011 arrest and firing from Dior, subsequent Margiela appointment, and now Zara CD role. Track the industry's short memory and lack of accountability on racism.",
        "editorial_angle": "Why does fashion keep forgiving its racists? The Galliano data tells a story."
    },

    "poc_representation_runway": {
        "label": "POC Representation on the Runway — Historical Data and Ongoing Failures",
        "queries": [
            "diversity runway fashion week statistics annual report",
            "models of color fashion week representation percentage data",
            "lack of black models runway fashion historical",
            "fashion week diversity report CFDA 2020 2021 2022 2023 2024 2025",
            "casting director racism fashion industry documented",
            "runway diversity improvement actual data evidence",
            "fashion week all white cast controversy brands",
        ],
        "date_from": "2013-01-01",
        "date_to": "2026-01-01",
        "context": "Track diversity statistics and representation failures over time with actual numbers. Are things actually improving or is it performative diversity?",
        "editorial_angle": "The numbers on runway diversity — what 10 years of data actually shows."
    },

    "colorism_runway": {
        "label": "Colorism on the Runway — Light-Skinned vs Dark-Skinned Model Casting",
        "queries": [
            "colorism fashion runway light skin dark skin casting",
            "fashion industry colorism bias model casting documented",
            "dark skinned black models underrepresented fashion week",
            "colorism luxury fashion brands casting directors",
            "fashion colorism data evidence shows analysis",
        ],
        "date_from": "2015-01-01",
        "date_to": "2026-01-01",
        "context": "Even within diversity progress, colorism remains — lighter-skinned POC models are disproportionately cast over darker-skinned models.",
        "editorial_angle": "Fashion got more diverse but not less colorist — the data behind the gap."
    },

    "asian_representation_fashion": {
        "label": "Asian Representation in Western Fashion Houses",
        "queries": [
            "asian representation western luxury fashion industry",
            "asian models fashion week underrepresentation stereotype",
            "east asian south asian fashion creative director appointments",
            "orientalism fashion industry western designers asian culture",
            "asian fashion designers recognition western fashion system",
            "fashion week asia representation diversity eastern designers",
        ],
        "date_from": "2010-01-01",
        "date_to": "2026-01-01",
        "context": "How Asian designers and models are represented — and misrepresented — in the Western fashion system.",
        "editorial_angle": "Orientalism in fashion is alive and well — here's the evidence."
    },

    "indigenous_appropriation": {
        "label": "Indigenous Cultural Appropriation in Fashion — Headdresses, Prints, Ceremony",
        "queries": [
            "indigenous cultural appropriation fashion headdress runway",
            "native american fashion appropriation brands controversy",
            "fashion brand sacred indigenous ceremony wear appropriation",
            "navajo fashion appropriation urban outfitters lawsuit",
            "fashion week indigenous appropriation documented cases",
            "tribal print fashion appropriation history",
        ],
        "date_from": "2010-01-01",
        "date_to": "2026-01-01",
        "context": "Fashion's repeated use of sacred indigenous cultural elements as aesthetic choices — headdresses, ceremony prints, tribal motifs.",
        "editorial_angle": "Fashion keeps stealing from indigenous cultures and calling it inspiration."
    },

    "fatphobia_fashion": {
        "label": "Fatphobia and Size Exclusion in Luxury Fashion",
        "queries": [
            "fatphobia luxury fashion size exclusion history",
            "plus size fashion runway representation luxury brands",
            "fashion industry thinness ideal body size discrimination",
            "sample size fashion industry fatphobia structural",
            "luxury fashion size range exclusion business decision",
            "fashion week plus size models history progress",
        ],
        "date_from": "2000-01-01",
        "date_to": "2026-01-01",
        "context": "Size exclusion in luxury fashion is a deliberate business and aesthetic choice — track its history and the industry's resistance to change.",
        "editorial_angle": "Luxury fashion's size problem is a policy, not an accident."
    },

    "white_creatives_poc_culture": {
        "label": "White Creatives Profiting from POC Culture — Patterns and Accountability",
        "queries": [
            "white fashion designers appropriating black culture profit",
            "fashion industry white creatives black aesthetic profit",
            "cultural appropriation fashion economic benefit white designers",
            "fashion brand black culture profit without credit accountability",
            "streetwear appropriation luxury fashion black origins",
        ],
        "date_from": "2010-01-01",
        "date_to": "2026-01-01",
        "context": "The pattern of white designers and brands profiting from Black, Latinx, and other POC cultural aesthetics without credit, compensation, or inclusion.",
        "editorial_angle": "Fashion's most profitable trend? Stealing from POC and calling it inspiration."
    },

    "virgil_abloh_legacy": {
        "label": "Virgil Abloh — First Black CD at Louis Vuitton, Legacy and Industry Critique",
        "queries": [
            "virgil abloh louis vuitton first black creative director",
            "virgil abloh legacy fashion industry diversity impact",
            "virgil abloh criticism streetwear luxury appropriation",
            "virgil abloh death fashion industry diversity regression",
            "off white virgil abloh cultural impact black designers luxury",
            "who replaced virgil abloh louis vuitton diversity regression",
        ],
        "date_from": "2018-01-01",
        "date_to": "2026-01-01",
        "context": "Abloh's appointment, his work, his death, and whether the industry's 'progress' on Black representation at the CD level has regressed since.",
        "editorial_angle": "Since Virgil Abloh died, how many Black CDs have been appointed at major luxury houses?"
    },

    "dapper_dan_gucci": {
        "label": "Dapper Dan — The Original Appropriation Story and Gucci's Reckoning",
        "queries": [
            "dapper dan gucci appropriation history harlem",
            "gucci copied dapper dan fur coat 1988",
            "dapper dan gucci collaboration after appropriation",
            "dapper dan fashion history black culture luxury",
            "gucci appropriation accountability dapper dan resolution",
        ],
        "date_from": "1988-01-01",
        "date_to": "2026-01-01",
        "context": "Gucci spent decades appropriating Dapper Dan's designs, shut him down legally, then hired him after public pressure. The definitive appropriation-to-collaboration story.",
        "editorial_angle": "Gucci stole from Dapper Dan for 30 years. What their 'reconciliation' actually means."
    },

    "diversity_hire_narrative": {
        "label": "The 'Diversity Hire' Narrative and How It's Used Against POC Designers",
        "queries": [
            "diversity hire fashion creative director criticism",
            "fashion industry diversity hire label POC designers",
            "black creative directors fashion tokenism criticism",
            "fashion diversity appointment merit vs tokenism debate",
            "POC fashion creative directors undermined diversity hire label",
        ],
        "date_from": "2015-01-01",
        "date_to": "2026-01-01",
        "context": "POC creative directors face a 'diversity hire' label that white CDs never encounter — track how this narrative is deployed and its effects.",
        "editorial_angle": "They called him a diversity hire. They never call the white ones that."
    },

    # ── CULTURAL & POLITICAL CONTEXT ──────────────────────────────────────────

    "recession_fashion": {
        "label": "Economic Recession and Fashion Trends — Historical Pattern Analysis",
        "queries": [
            "recession fashion trends history hemline index",
            "2008 financial crisis fashion industry impact luxury spending",
            "economic downturn quiet luxury fashion austerity dressing",
            "fashion industry recession spending patterns historical data",
            "great depression fashion history 1930s influence",
            "covid recession fashion industry impact 2020 2021",
            "economic anxiety fashion maximalism minimalism cycles",
        ],
        "date_from": "1929-01-01",
        "date_to": "2026-01-01",
        "context": "Economic context for why FW26's end of quiet luxury is happening — what economic signals correlate with maximalism returning? Is FW26 maximalism a recession signal?",
        "editorial_angle": "Every time the economy gets scary, fashion gets loud. FW26 is no exception."
    },

    "political_fashion_history": {
        "label": "Political Climate and Fashion — Protest Dressing, Cultural Signals, Industry Response",
        "queries": [
            "fashion political protest dressing history examples",
            "fashion industry political statement runway collections history",
            "designers political messages runway documented examples",
            "fashion week political climate response after elections",
            "fashion diversity inclusion pledges after george floyd 2020",
            "fashion industry political activism accountability follow through",
        ],
        "date_from": "1960-01-01",
        "date_to": "2026-01-01",
        "context": "How political events shape fashion aesthetics — from 60s protest dressing to post-2020 diversity pledges. Did the industry follow through?",
        "editorial_angle": "Fashion makes political statements at shows. The data on whether it follows through."
    },

    "cd_appointment_diversity": {
        "label": "Creative Director Diversity Gap — Who Gets Appointed and Why",
        "queries": [
            "fashion creative director race diversity gap data",
            "black creative directors luxury fashion houses list",
            "diversity creative director appointments luxury fashion history",
            "why are most creative directors white fashion analysis",
            "fashion cd appointments diversity statistics 2020 2021 2022 2023 2024 2025",
            "fw26 creative director appointments race gender diversity audit",
        ],
        "date_from": "2000-01-01",
        "date_to": "2026-01-01",
        "context": "Of the 18 CD appointments this FW26 season, how many are POC? What is the 20-year historical pattern of who gets appointed at major houses?",
        "editorial_angle": "We tracked every major CD appointment this season. The diversity numbers are exactly what you'd expect."
    },

    "fashion_week_city_bias": {
        "label": "Why Fashion Weeks Are Still Held in Four White Western Cities",
        "queries": [
            "fashion week big four paris milan london new york history",
            "fashion week africa africa fashion week recognition",
            "fashion week Lagos Nairobi Lagos fashion week recognition",
            "fashion week global city diversity expansion African Asian",
            "why no fashion week big four African city analysis",
            "fashion system western bias four cities power structure",
        ],
        "date_from": "1990-01-01",
        "date_to": "2026-01-01",
        "context": "The Big Four fashion weeks are all in white Western cities — why this hasn't changed despite decades of globalisation and the rise of African and Asian fashion markets.",
        "editorial_angle": "Fashion is global. Fashion week is not. Here's why that's a choice."
    },

    "fashion_labour_immigration": {
        "label": "Immigration Policy and Fashion Labour — Who Actually Makes the Clothes",
        "queries": [
            "fashion garment workers immigration labour exploitation",
            "fast fashion labour immigration workers undocumented",
            "luxury fashion made in italy immigration labour",
            "fashion supply chain immigration workers conditions",
            "garment workers fashion industry immigration policy impact",
            "rana plaza fashion labour immigration exploitation history",
        ],
        "date_from": "2000-01-01",
        "date_to": "2026-01-01",
        "context": "The people who make the clothes are overwhelmingly immigrants and POC — contrast this with who designs, leads, and profits from fashion.",
        "editorial_angle": "Fashion's labour is immigrant. Fashion's leadership is not. That gap is the story."
    },

    "climate_fashion_anxiety": {
        "label": "Climate Anxiety and Fashion Cycle — Maximalism vs Minimalism as Psychological Response",
        "queries": [
            "climate anxiety fashion aesthetics maximalism minimalism",
            "environmental crisis fashion industry response",
            "gen z climate anxiety fashion consumption behaviour",
            "fashion sustainability climate crisis consumer response",
            "climate change fashion aesthetic shifts analysis",
        ],
        "date_from": "2015-01-01",
        "date_to": "2026-01-01",
        "context": "Is FW26 maximalism a response to climate anxiety — if the world is ending, dress loudly? Or a rejection of austere climate guilt messaging?",
        "editorial_angle": "FW26 went maximalist as climate anxiety peaked. That's not a coincidence."
    },

    "gen_z_old_money_economics": {
        "label": "Gen Z Economic Anxiety and the Old Money Aesthetic — Why It Resonates",
        "queries": [
            "gen z old money aesthetic economic anxiety psychology",
            "quiet luxury old money gen z aspiration economic insecurity",
            "gen z fashion aspiration economic inequality analysis",
            "housing crisis gen z fashion spending behaviour",
            "cost of living crisis fashion aesthetic escapism gen z",
        ],
        "date_from": "2020-01-01",
        "date_to": "2026-01-01",
        "context": "The old money aesthetic became dominant precisely as gen z faced housing unaffordability, student debt, and wage stagnation — aspiration as escape.",
        "editorial_angle": "You can't afford a house but you can dress like you can. The economics of quiet luxury."
    },

    # ── HISTORICAL DESIGNER & ERA RESEARCH ───────────────────────────────────

    "post_war_japan_fashion": {
        "label": "Post-War Japan and the Western World — Fashion as Reconstruction and Resistance",
        "queries": [
            "rei kawakubo comme des garcons born wartime japan influence",
            "post world war ii japan fashion industry rebuilding",
            "japanese avant garde fashion 1980s paris invasion history",
            "yohji yamamoto comme des garcons post war japan aesthetic",
            "occupation japan 1945 fashion western influence reconstruction",
            "japanese fashion designers paris debut 1981 cultural significance",
            "issey miyake wartime japan childhood atomic bomb hiroshima fashion",
            "japanese fashion anti western beauty standard 1980s history",
            "rei kawakubo deconstruction post war japan trauma aesthetic theory",
            "japan economic miracle 1960s 1970s fashion industry growth",
        ],
        "date_from": "1945-01-01",
        "date_to": "2026-01-01",
        "context": "Rei Kawakubo born 1942, Yohji Yamamoto born 1943, Issey Miyake born 1938 — all shaped by WWII and occupied Japan. Their work is inseparable from this history. The 1981 Paris debut was not just a fashion moment, it was a post-colonial aesthetic statement.",
        "editorial_angle": "Comme des Garçons was born from the rubble of wartime Japan. That's not a metaphor — it's history."
    },

    "alexander_mcqueen_trauma": {
        "label": "Alexander McQueen — Trauma, Art, and Fashion's Exploitation of Mental Health",
        "queries": [
            "alexander mcqueen mental health depression suicide fashion",
            "mcqueen trauma art fashion exploitation dark work",
            "fashion industry mental health designers pressure suicide mcqueen",
            "alexander mcqueen fashion industry complicity mental health",
            "mcqueen highland rape bumsters controversial shows history",
            "fashion industry response designer mental health crisis",
        ],
        "date_from": "1992-01-01",
        "date_to": "2026-01-01",
        "context": "McQueen's work was explicitly about trauma and darkness — the industry celebrated it commercially while he deteriorated. What responsibility did fashion have?",
        "editorial_angle": "Fashion made millions from McQueen's trauma. Then he died. What the industry has and hasn't learned."
    },

    "hiv_aids_fashion": {
        "label": "HIV/AIDS Crisis and Its Impact on Fashion — The Lost Generation",
        "queries": [
            "HIV AIDS fashion industry 1980s 1990s impact designers deaths",
            "AIDS crisis fashion designers who died 1980s 1990s",
            "fashion industry AIDS epidemic response history",
            "halston perry ellis aids crisis fashion history",
            "fashion week aids crisis silence response history",
            "aids fashion industry mourning lost generation designers",
        ],
        "date_from": "1981-01-01",
        "date_to": "2005-01-01",
        "context": "AIDS devastated fashion in the 80s and 90s — designers, stylists, models, photographers. Understanding this shapes understanding of the entire era.",
        "editorial_angle": "AIDS killed a generation of fashion's most creative people. The industry barely acknowledged it."
    },

    "postcolonial_fashion": {
        "label": "Post-Colonial Fashion — African and Asian Designers Reclaiming the Narrative",
        "queries": [
            "african fashion designers global recognition post colonial",
            "post colonial fashion theory designers reclaiming narrative",
            "African fashion week global influence Lagos Nairobi recognition",
            "asian fashion designers paris milan recognition history",
            "fashion colonialism western gaze African Asian designers",
            "decolonising fashion industry movement designers",
        ],
        "date_from": "2000-01-01",
        "date_to": "2026-01-01",
        "context": "As former colonial powers struggle with diversity, designers from Africa, Asia, and the Global South are building their own fashion systems on their own terms.",
        "editorial_angle": "African and Asian designers aren't waiting for Paris to validate them anymore."
    },

    "galliano_full_arc": {
        "label": "John Galliano — Full Career Arc Pre and Post Incident",
        "queries": [
            "john galliano dior early career 1990s genius reviews",
            "galliano dior golden era fashion history critical reception",
            "galliano romanticism maximalism fashion influence legacy",
            "galliano before racism incident career timeline fashion",
            "galliano margiela 2014 comeback fashion critical reception",
            "galliano rehabilitation fashion industry accountability question",
        ],
        "date_from": "1990-01-01",
        "date_to": "2026-01-01",
        "context": "Understanding Galliano as a full figure — the extraordinary work, the racism, the comeback — to write about his Zara appointment with full context.",
        "editorial_angle": "A complete timeline of John Galliano: genius, racist, and fashion's most complicated rehabilitation story."
    },

    "cultural_appropriation_fashion": {
        "label": "Cultural Appropriation in Fashion — Systematic Patterns and Industry Response",
        "queries": [
            "cultural appropriation fashion industry examples documented history",
            "fashion brand cultural appropriation controversy timeline",
            "white designers profiting black culture fashion documented cases",
            "fashion appropriation vs appreciation line industry debate",
            "fashion week cultural appropriation cornrows headdress examples",
            "fashion industry cultural appropriation accountability cases outcomes",
        ],
        "date_from": "2010-01-01",
        "date_to": "2026-01-01",
        "context": "Map the recurring pattern of appropriation in fashion and measure whether industry response has resulted in actual accountability or just PR.",
        "editorial_angle": "Ten years of fashion appropriation controversies. The score: brands 47, accountability 0."
    },

    # ── CURRENT EVENTS & POLITICAL MOMENTS ───────────────────────────────────

    "willy_chavarria_ice_detention": {
        "label": "Willy Chavarria — ICE Detention, El Salvador, Fashion as Political Protest",
        "queries": [
            "willy chavarria ICE detention el salvador fashion show protest",
            "willy chavarria runway immigration political statement",
            "fashion designer ICE deportation protest collection 2025 2026",
            "willy chavarria latinx community detention fashion response",
            "fashion political protest immigration policy designers 2025 2026",
            "willy chavarria show detained immigrants el salvador statement",
        ],
        "date_from": "2024-01-01",
        "date_to": "2026-12-31",
        "context": "Willy Chavarria used his runway to respond to ICE detention of El Salvadorans — one of the most explicitly political fashion moments in recent memory. A Latino designer using fashion as direct protest against government policy targeting his community.",
        "editorial_angle": "Willy Chavarria made a show about ICE detention. The industry gave him a standing ovation and moved on. Did anything actually change?"
    },

    "galliano_zara_accountability": {
        "label": "John Galliano x Zara — The Accountability Gap",
        "queries": [
            "john galliano zara appointment controversy accountability",
            "galliano zara reaction fashion industry criticism",
            "john galliano redemption arc fashion industry forgiveness analysis",
            "galliano zara jewish community response antisemitism",
            "fashion industry racism accountability double standard galliano",
            "galliano zara appointment criticism 2024 2025",
        ],
        "date_from": "2024-01-01",
        "date_to": "2026-12-31",
        "context": "Galliano went from being fired for antisemitism to being appointed CD of Zara — one of the world's biggest fashion brands. Track the reaction, the criticism, and what it reveals about fashion's accountability standards.",
        "editorial_angle": "Zara hired the man Dior fired for racism. Here's what the reaction tells us about fashion's memory."
    },

    "maximalism_quiet_luxury_end": {
        "label": "The Death of Quiet Luxury — Why FW26 Went Maximalist",
        "queries": [
            "quiet luxury trend over 2026 maximalism return analysis",
            "end of quiet luxury fashion trend 2025 2026",
            "maximalist fashion return 2026 consumer behaviour",
            "old money aesthetic decline bold fashion 2026",
            "statement dressing trend return 2026 analysis",
            "why quiet luxury failed fashion cultural analysis",
        ],
        "date_from": "2024-01-01",
        "date_to": "2026-12-31",
        "context": "FW26 was dominated by statement dressing and the explicit rejection of quiet luxury. Why did the aesthetic shift happen now? What economic, cultural, and political signals drove it?",
        "editorial_angle": "Quiet luxury is over. FW26 made that official. Here's the data and the cultural forces behind the shift."
    },

    "fashion_political_protest_2026": {
        "label": "Fashion as Political Protest — Who Is Actually Saying Something in 2026",
        "queries": [
            "fashion designers political statement 2026 runway protest",
            "fashion political activism 2026 documented designers",
            "runway show political message 2025 2026 examples",
            "fashion week political protest designers government response",
            "fashion industry political silence complicity 2026",
            "designers using platform social justice fashion 2026",
        ],
        "date_from": "2025-01-01",
        "date_to": "2026-12-31",
        "context": "Who in fashion is making explicitly political work in 2026 and who is staying silent? Map the landscape beyond individual viral moments.",
        "editorial_angle": "Fashion is political whether it admits it or not. Here's who's actually saying something in 2026 — and who isn't."
    },

    "fw26_trend_analysis": {
        "label": "FW26 Macro Trend Analysis — What the Season Actually Means",
        "queries": [
            "fall winter 2026 fashion week trend analysis overview",
            "FW26 biggest trends fashion week critical analysis",
            "fashion week fall 2026 cultural significance analysis",
            "fw26 fashion trends meaning cultural context",
            "fall winter 2026 collections critical reception analysis",
            "fw26 fashion trends consumer impact prediction",
        ],
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "context": "Pull critical analysis and editorial commentary on FW26 as a whole — what did the season mean culturally, what trends will actually land with consumers, and what was the critical consensus.",
        "editorial_angle": "What FW26 actually meant — beyond the viral moments and the data."
    },

    "fast_fashion_luxury_gap": {
        "label": "Fast Fashion vs Luxury — The Widening Gap and Who Gets Left Behind",
        "queries": [
            "fast fashion luxury gap widening 2025 2026 analysis",
            "fashion industry wealth gap consumer fast fashion luxury",
            "luxury fashion price increase accessibility crisis",
            "fashion industry middle market collapse 2025 2026",
            "fast fashion environmental impact luxury sustainability gap",
            "who can afford fashion 2026 economic analysis",
        ],
        "date_from": "2023-01-01",
        "date_to": "2026-12-31",
        "context": "As luxury prices have increased dramatically and fast fashion has worsened, the middle ground of fashion has collapsed. Who is this leaving behind and what does it mean culturally?",
        "editorial_angle": "Fashion used to have a middle class. It doesn't anymore. Here's what that means."
    },
}

# ── API Helpers ───────────────────────────────────────────────────────────────

def firecrawl_scrape(url: str) -> dict:
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "blockAds": True,
        "timeout": 30000,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{FIRECRAWL_API}/scrape", data=data)
    req.add_header("Authorization", f"Bearer {FIRECRAWL_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read()).get("data", {})
    except Exception as e:
        print(f"  Firecrawl scrape error: {e}")
        return {}

def exa_find_urls(query: str, limit: int = 5) -> list:
    """Use Exa to find relevant URLs for a query."""
    EXA_KEY = os.environ.get("EXA_API_KEY", "")
    if not EXA_KEY:
        return []
    try:
        from exa_py import Exa
        exa = Exa(api_key=EXA_KEY)
        result = exa.search(query, type="auto", num_results=limit)
        return [{"url": r.url, "title": r.title or ""} for r in (result.results or [])]
    except Exception as e:
        return []

def firecrawl_search(query: str, limit: int = 5) -> list:
    """
    Find URLs via Exa, then scrape full content via Firecrawl.
    This bypasses Firecrawl's broken search endpoint.
    """
    # Step 1: Find URLs using Exa
    urls = exa_find_urls(query, limit)

    if not urls:
        # Fallback: try Firecrawl search directly
        payload = {
            "query": query,
            "limit": limit,
            "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{FIRECRAWL_API}/search", data=data)
        req.add_header("Authorization", f"Bearer {FIRECRAWL_KEY}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = json.loads(r.read()).get("data", [])
                urls = [{"url": i.get("url",""), "title": i.get("title","")}
                        for i in raw if isinstance(i, dict) and i.get("url")]
        except Exception as e:
            print(f"  Firecrawl search error: {e}")
            return []

    # Step 2: Scrape each URL with Firecrawl for full content
    pages = []
    for item in urls[:limit]:
        url = item.get("url", "")
        if not url:
            continue
        scraped = firecrawl_scrape(url)
        md = scraped.get("markdown", "") or ""
        if md and len(md) > 200:
            pages.append({
                "url":      url,
                "title":    item.get("title") or scraped.get("metadata", {}).get("title", ""),
                "markdown": md,
            })
        time.sleep(0.5)

    return pages

def get_wayback_url(original_url: str, target_date: str) -> str:
    params = urllib.parse.urlencode({"url": original_url, "timestamp": target_date})
    try:
        with urllib.request.urlopen(f"{WAYBACK_API}?{params}", timeout=15) as r:
            data = json.loads(r.read())
        closest = data.get("archived_snapshots", {}).get("closest", {})
        return closest.get("url") if closest.get("available") else None
    except Exception as e:
        print(f"  Wayback error: {e}")
        return None

def summarise_with_claude(text: str, context_prompt: str) -> str:
    if not ANTHROPIC_KEY:
        return text[:2000] + "\n...[set ANTHROPIC_API_KEY for AI synthesis]"
    truncated = text[:8000] if len(text) > 8000 else text
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 800,
        "system": """You are a fashion cultural analyst for runway fyi — a fashion intelligence platform with an explicit editorial commitment to covering race, representation, and cultural criticism in fashion honestly and with data.

Extract and summarise the most relevant insights from scraped web content.
Focus on: specific data points with numbers, direct quotes, historical facts, documented incidents, industry patterns, accountability (or lack thereof).
Flag anything related to race, representation, appropriation, or controversy with specific details — do not soften or both-sides these issues.

Output format:
- 3-5 bullet points with specific facts/data
- One "EDITORIAL ANGLE:" sentence for a potential runwayfyi.com article
- One "FURTHER RESEARCH:" note if you identify a gap that needs more investigation""",
        "messages": [{"role": "user", "content": f"Research context: {context_prompt}\n\nContent:\n{truncated}"}]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", ANTHROPIC_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["content"][0]["text"]
    except Exception as e:
        return f"[Claude error: {e}]"

def save_results(results: list, filename: str):
    with open(f"{filename}.json", "w") as f:
        json.dump(results, f, indent=2)
    with open(f"{filename}.md", "w") as f:
        f.write(f"# runway fyi — Cultural Context Research\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        for r in results:
            f.write(f"---\n\n## {r.get('title', r.get('url', 'Unknown'))}\n")
            f.write(f"**Source:** {r.get('url', '—')}  \n")
            f.write(f"**Query:** {r.get('query', '—')}\n\n")
            if r.get("summary"):
                f.write(f"### Insights\n{r['summary']}\n\n")
            if r.get("raw_excerpt"):
                f.write(f"### Excerpt\n> {r['raw_excerpt'][:600]}...\n\n")
    print(f"  Saved: {filename}.json")
    print(f"  Saved: {filename}.md")

# ── Modes ─────────────────────────────────────────────────────────────────────

def mode_topic(topic_key: str) -> list:
    if topic_key not in RESEARCH_TOPICS:
        print(f"  Unknown: {topic_key}. Run --mode list-topics")
        sys.exit(1)
    topic = RESEARCH_TOPICS[topic_key]
    print(f"\n  {topic['label']}")
    print(f"  {topic['context']}\n")
    results = []
    for query in topic["queries"]:
        print(f"  Searching: {query[:65]}")
        pages = firecrawl_search(query, limit=3)
        for page in pages:
            if isinstance(page, str):
                content = page
                title = ""
                url = ""
            elif isinstance(page, dict):
                content = page.get("markdown", "") or page.get("description", "")
                title = page.get("title", "")
                url = page.get("url", "")
            else:
                continue
            if not content:
                continue
            print(f"    → {title[:70] if title else content[:70]}")
            summary = summarise_with_claude(content, f"{topic['label']}: {topic['context']}")
            results.append({
                "topic": topic_key,
                "query": query,
                "url": url,
                "title": title,
                "summary": summary,
                "raw_excerpt": content[:600],
            })
            time.sleep(1)
    return results

def mode_designer(query: str, years: list) -> list:
    print(f"\n  Designer: {query}  |  Years: {', '.join(years)}\n")
    results = []
    for year in years:
        print(f"  [{year}]")
        for search_query in [
            f"{query} fashion collection review {year}",
            f"{query} fashion criticism {year}",
        ]:
            pages = firecrawl_search(search_query, limit=2)
            for page in pages:
                content = page.get("markdown", "") or page.get("description", "")
                if not content:
                    continue
                print(f"    → {page.get('title', '')[:70]}")
                summary = summarise_with_claude(content,
                    f"Historical critical reception and cultural context for {query} in {year}. Include any mentions of race, appropriation, politics, or controversy.")
                results.append({
                    "year": year, "query": search_query,
                    "url": page.get("url", ""), "title": page.get("title", ""),
                    "summary": summary, "raw_excerpt": content[:600],
                })
                time.sleep(1)
    return results

def mode_wayback(url: str, date: str) -> list:
    print(f"\n  URL: {url}\n  Date: {date}")
    wb_date = date.replace("-", "")
    snapshot_url = get_wayback_url(url, wb_date)
    if not snapshot_url:
        print(f"  No snapshot found for {date}")
        return []
    print(f"  Snapshot: {snapshot_url}")
    page = firecrawl_scrape(snapshot_url)
    content = page.get("markdown", "")
    if not content:
        print("  No content returned")
        return []
    print(f"  Scraped {len(content):,} characters")
    summary = summarise_with_claude(content,
        f"Archived page from {date}. Extract key editorial content, critical perspective, historical significance, and any cultural/political context.")
    return [{
        "original_url": url, "snapshot_url": snapshot_url,
        "archive_date": date,
        "title": page.get("metadata", {}).get("title", url),
        "summary": summary, "raw_excerpt": content[:600],
    }]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["topic", "designer", "wayback", "cultural", "list-topics"], required=True)
    parser.add_argument("--topic-key")
    parser.add_argument("--query")
    parser.add_argument("--url")
    parser.add_argument("--date")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--years")
    parser.add_argument("--output")
    args = parser.parse_args()

    print("\n  runway fyi — Cultural Context Engine")
    print("  ──────────────────────────────────────")

    if args.mode == "list-topics":
        print(f"\n  {len(RESEARCH_TOPICS)} research topics available:\n")
        categories = {
            "RACE & REPRESENTATION": ["galliano_racism", "poc_representation_runway", "colorism_runway",
                "asian_representation_fashion", "indigenous_appropriation", "fatphobia_fashion",
                "white_creatives_poc_culture", "virgil_abloh_legacy", "dapper_dan_gucci",
                "diversity_hire_narrative", "cultural_appropriation_fashion"],
            "CULTURAL & POLITICAL": ["recession_fashion", "political_fashion_history", "cd_appointment_diversity",
                "fashion_week_city_bias", "fashion_labour_immigration", "climate_fashion_anxiety",
                "gen_z_old_money_economics"],
            "HISTORICAL RESEARCH": ["post_war_japan_fashion", "alexander_mcqueen_trauma", "hiv_aids_fashion",
                "postcolonial_fashion", "galliano_full_arc"],
        }
        for cat, keys in categories.items():
            print(f"  ── {cat} ──")
            for k in keys:
                if k in RESEARCH_TOPICS:
                    t = RESEARCH_TOPICS[k]
                    print(f"  {k}")
                    print(f"    {t['label']}")
                    print(f"    → {t['editorial_angle']}\n")
        return

    results = []
    filename = args.output

    if args.mode == "topic":
        if not args.topic_key:
            print("ERROR: --topic-key required"); sys.exit(1)
        results = mode_topic(args.topic_key)
        filename = filename or f"context_{args.topic_key}_{datetime.now().strftime('%Y%m%d')}"

    elif args.mode == "designer":
        if not args.query:
            print("ERROR: --query required"); sys.exit(1)
        years = [y.strip() for y in args.years.split(",")] if args.years else ["2015", "2020", "2026"]
        results = mode_designer(args.query, years)
        filename = filename or f"context_designer_{args.query.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    elif args.mode == "wayback":
        if not args.url or not args.date:
            print("ERROR: --url and --date required"); sys.exit(1)
        results = mode_wayback(args.url, args.date)
        filename = filename or f"context_wayback_{datetime.now().strftime('%Y%m%d_%H%M')}"

    elif args.mode == "cultural":
        topic = args.query or ""
        if not topic:
            print("ERROR: --query required for cultural mode"); sys.exit(1)
        results = mode_topic(topic) if topic in RESEARCH_TOPICS else []
        filename = filename or f"context_cultural_{topic[:20]}_{datetime.now().strftime('%Y%m%d')}"

    if results:
        save_results(results, filename)
        print(f"\n  {len(results)} sources researched and saved")
    else:
        print("  No results returned")
    print()

if __name__ == "__main__":
    main()
