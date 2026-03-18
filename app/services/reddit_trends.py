"""
reddit_trends.py — Reddit social signal
Searches fashion subreddits using brand+season queries AND trend keywords.
Uses Reddit's public JSON API — no API key required.
"""

import httpx
import time
from datetime import datetime, timedelta, timezone

FASHION_SUBREDDITS = [
    "femalefashionadvice",
    "streetwear",
    "fashionadvice",
    "malefashionadvice",
    "fashion",
    "runway",
]

HEADERS = {
    "User-Agent": "runwayfyi:v1.0 (by /u/runwayfyi)"
}

# Conversational aliases per trend — what people actually type on Reddit
REDDIT_KEYWORD_ALIASES = {
    "Leather Outerwear": ["leather jacket", "leather coat", "leather outerwear", "crocodile leather", "croc leather"],
    "Shearling": ["shearling coat", "shearling jacket", "fluffy coat", "sheepskin coat", "lambskin jacket"],
    "Ballet Flats": ["ballet flats", "ballet shoes fashion", "ballet flat"],
    "Mary Janes": ["mary janes shoes", "mary jane trend"],
    "Wide-Leg Tailoring": ["wide leg trousers", "wide leg pants", "flowy trousers"],
    "Power Suiting": ["power suit", "oversized blazer", "suit trend"],
    "Prairie Dress": ["prairie dress", "cottagecore dress", "floral maxi"],
    "Sheer Layers": ["sheer top", "sheer dress", "transparent fashion"],
    "Boucle Tweed": ["tweed coat", "boucle jacket", "chanel style tweed"],
    "Velvet": ["velvet dress", "velvet blazer", "velvet fashion"],
    "Satin": ["satin dress", "satin skirt", "satin fashion"],
    "Lace": ["lace dress", "lace top", "lace fashion"],
    "Camel": ["camel coat", "camel color outfit", "camel fashion"],
    "Chocolate Brown": ["chocolate brown outfit", "brown coat", "brown fashion"],
    "Ivory & Cream": ["ivory dress", "cream outfit", "off white fashion"],
    "Oversized Coat": ["oversized coat", "cocoon coat", "big coat trend"],
    "Miu Miu aesthetic": ["miu miu", "miu miu fw26", "miu miu fall 2026"],
    "Matthieu Blazy Chanel": ["chanel fw26", "matthieu blazy", "chanel fall 2026"],
}

# Brand-specific Reddit search terms — all 85 FW26 shows
BRAND_SEARCH_TERMS = {
    "Acne Studios": ["acne studios fw26", "acne studios fall 2026", "jonny johansson acne"],
    "Alaia": ["alaia fw26", "alaia fall 2026", "pieter mullier alaia"],
    "Altuzarra": ["altuzarra fw26", "altuzarra fall 2026"],
    "Balmain": ["balmain fw26", "balmain fall 2026", "antonin tron balmain"],
    "Baum und Pferdgarten": ["baum und pferdgarten fw26", "baum und pferdgarten fall 2026"],
    "Blumarine": ["blumarine fw26", "blumarine fall 2026", "david koma blumarine"],
    "Boss": ["boss fw26", "boss fall 2026", "marco falcioni boss"],
    "Bottega Veneta": ["bottega veneta fw26", "bottega fall 2026", "louise trotter bottega"],
    "Burberry": ["burberry fw26", "burberry fall 2026", "daniel lee burberry"],
    "Carolina Herrera": ["carolina herrera fw26", "carolina herrera fall 2026", "wes gordon herrera"],
    "Celine": ["celine fw26", "celine fall 2026", "michael rider celine"],
    "Chanel": ["chanel fw26", "chanel fall 2026", "matthieu blazy chanel"],
    "Chloe": ["chloe fw26", "chloe fall 2026", "chemena kamali chloe"],
    "Coach": ["coach fw26", "coach fall 2026", "stuart vevers coach"],
    "Comme des Garcons": ["comme des garcons fw26", "comme des garcons fall 2026", "rei kawakubo"],
    "Conner Ives": ["conner ives fw26", "conner ives fall 2026"],
    "Courreges": ["courreges fw26", "courreges fall 2026", "nicolas di felice"],
    "Diesel": ["diesel fw26", "diesel fall 2026", "glenn martens diesel"],
    "Dior": ["dior fw26", "dior fall 2026", "jonathan anderson dior"],
    "Dolce & Gabbana": ["dolce gabbana fw26", "dolce gabbana fall 2026"],
    "Dries Van Noten": ["dries van noten fw26", "dries van noten fall 2026", "julian klausner"],
    "Emporio Armani": ["emporio armani fw26", "emporio armani fall 2026"],
    "Erdem": ["erdem fw26", "erdem fall 2026", "erdem moralioglu"],
    "Etro": ["etro fw26", "etro fall 2026", "marco de vincenzo etro"],
    "Fendi": ["fendi fw26", "fendi fall 2026", "maria grazia chiuri fendi"],
    "Ferragamo": ["ferragamo fw26", "ferragamo fall 2026", "maximilian davis ferragamo"],
    "Gabriela Hearst": ["gabriela hearst fw26", "gabriela hearst fall 2026"],
    "Giorgio Armani": ["giorgio armani fw26", "giorgio armani fall 2026"],
    "Givenchy": ["givenchy fw26", "givenchy fall 2026", "sarah burton givenchy"],
    "Gucci": ["gucci fw26", "gucci fall 2026", "demna gucci"],
    "Balenciaga": ["balenciaga fw26", "balenciaga fall 2026", "pierpaolo piccioli balenciaga"],
    "Hermes": ["hermes fw26", "hermes fall 2026", "nadege vanhee hermes"],
    "Holzweiler": ["holzweiler fw26", "holzweiler fall 2026"],
    "Isabel Marant": ["isabel marant fw26", "isabel marant fall 2026", "kim bekker marant"],
    "Jacquemus": ["jacquemus fw26", "jacquemus fall 2026", "simon porte jacquemus"],
    "Jean Paul Gaultier": ["jean paul gaultier fw26", "jean paul gaultier fall 2026", "duran lantink gaultier"],
    "Jil Sander": ["jil sander fw26", "jil sander fall 2026", "simone bellotti jil sander"],
    "Junya Watanabe": ["junya watanabe fw26", "junya watanabe fall 2026"],
    "Khaite": ["khaite fw26", "khaite fall 2026", "catherine holstein khaite"],
    "Kiko Kostadinov": ["kiko kostadinov fw26", "kiko kostadinov fall 2026"],
    "Lacoste": ["lacoste fw26", "lacoste fall 2026", "pelagia kolotouros lacoste"],
    "Lanvin": ["lanvin fw26", "lanvin fall 2026", "peter copping lanvin"],
    "Lemaire": ["lemaire fw26", "lemaire fall 2026", "christophe lemaire"],
    "Loewe": ["loewe fw26", "loewe fall 2026", "jake mccollough loewe"],
    "Louis Vuitton": ["louis vuitton fw26", "louis vuitton fall 2026", "nicolas ghesquiere"],
    "Magda Butrym": ["magda butrym fw26", "magda butrym fall 2026"],
    "Marco Rambaldi": ["marco rambaldi fw26", "marco rambaldi fall 2026"],
    "Marni": ["marni fw26", "marni fall 2026", "meryll rogge marni"],
    "Max Mara": ["max mara fw26", "max mara fall 2026", "ian griffiths max mara"],
    "McQueen": ["mcqueen fw26", "mcqueen fall 2026", "sean mcgirr mcqueen"],
    "Michael Kors": ["michael kors fw26", "michael kors fall 2026"],
    "Missoni": ["missoni fw26", "missoni fall 2026", "alberto caliri missoni"],
    "Miu Miu": ["miu miu fw26", "miu miu fall 2026", "miuccia prada miu miu"],
    "MM6 Maison Margiela": ["mm6 fw26", "mm6 maison margiela fall 2026"],
    "Moschino": ["moschino fw26", "moschino fall 2026", "adrian appiolaza moschino"],
    "Mugler": ["mugler fw26", "mugler fall 2026", "miguel castro freitas mugler"],
    "Nina Ricci": ["nina ricci fw26", "nina ricci fall 2026", "harris reed nina ricci"],
    "No. 21": ["no 21 fw26", "no 21 fall 2026", "alessandro dell acqua"],
    "Patou": ["patou fw26", "patou fall 2026", "guillaume henry patou"],
    "Prabal Gurung": ["prabal gurung fw26", "prabal gurung fall 2026"],
    "Prada": ["prada fw26", "prada fall 2026", "miuccia prada raf simons"],
    "Proenza Schouler": ["proenza schouler fw26", "proenza schouler fall 2026", "rachel scott proenza"],
    "Rabanne": ["rabanne fw26", "rabanne fall 2026", "julien dossena rabanne"],
    "Ralph Lauren": ["ralph lauren fw26", "ralph lauren fall 2026"],
    "Rave Review": ["rave review fw26", "rave review fall 2026"],
    "Richard Quinn": ["richard quinn fw26", "richard quinn fall 2026"],
    "Rick Owens": ["rick owens fw26", "rick owens fall 2026"],
    "Roberto Cavalli": ["roberto cavalli fw26", "roberto cavalli fall 2026", "fausto puglisi cavalli"],
    "Saint Laurent": ["saint laurent fw26", "ysl fall 2026", "anthony vaccarello saint laurent"],
    "Sandy Liang": ["sandy liang fw26", "sandy liang fall 2026"],
    "Schiaparelli": ["schiaparelli fw26", "schiaparelli fall 2026", "daniel roseberry schiaparelli"],
    "Simone Rocha": ["simone rocha fw26", "simone rocha fall 2026"],
    "Skall Studio": ["skall studio fw26", "skall studio fall 2026"],
    "Sportmax": ["sportmax fw26", "sportmax fall 2026"],
    "Stella McCartney": ["stella mccartney fw26", "stella mccartney fall 2026"],
    "Tod's": ["tods fw26", "tods fall 2026", "matteo tamburini tods"],
    "Tom Ford": ["tom ford fw26", "tom ford fall 2026", "haider ackermann tom ford"],
    "Tory Burch": ["tory burch fw26", "tory burch fall 2026"],
    "Toteme": ["toteme fw26", "toteme fall 2026", "elin kling toteme"],
    "Ulla Johnson": ["ulla johnson fw26", "ulla johnson fall 2026"],
    "Undercover": ["undercover fw26", "undercover fall 2026", "jun takahashi undercover"],
    "Valentino": ["valentino fw26", "valentino fall 2026", "alessandro michele valentino"],
    "Victoria Beckham": ["victoria beckham fw26", "victoria beckham fall 2026"],
    "Yohji Yamamoto": ["yohji yamamoto fw26", "yohji yamamoto fall 2026"],
    "Zimmermann": ["zimmermann fw26", "zimmermann fall 2026", "nicky zimmermann"],
}


def search_reddit(query: str, subreddit: str = None, limit: int = 25) -> list:
    """Search Reddit for posts matching a query."""
    try:
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {"q": query, "restrict_sr": "true", "sort": "new", "limit": limit, "t": "year"}
        else:
            url = "https://www.reddit.com/search.json"
            params = {"q": query, "sort": "new", "limit": limit, "t": "year"}

        r = httpx.get(url, params=params, headers=HEADERS, timeout=15)
        time.sleep(0.5)

        if r.status_code == 429:
            print(f"[reddit_trends] Rate limited, skipping '{query}'")
            return []
        if r.status_code != 200:
            return []

        return r.json().get("data", {}).get("children", [])
    except Exception as e:
        print(f"[reddit_trends] Error for '{query}': {e}")
        return []


def score_posts(posts: list, days: int = 90) -> tuple[int, int]:
    """Return (post_count, total_upvotes) for recent posts."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = 0
    upvotes = 0
    for post in posts:
        data = post.get("data", {})
        try:
            created = datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc)
            if created >= cutoff:
                count += 1
                upvotes += max(0, data.get("score", 0))
        except Exception:
            count += 1
    return count, upvotes


def get_reddit_signal(keyword: str) -> float:
    """Get a 0-100 Reddit signal for a trend keyword."""
    try:
        total_posts = 0
        total_upvotes = 0

        aliases = REDDIT_KEYWORD_ALIASES.get(keyword, [keyword])

        for alias in aliases[:3]:
            posts = search_reddit(alias)
            c, u = score_posts(posts)
            total_posts += c
            total_upvotes += u

        primary_alias = aliases[0] if aliases else keyword
        for sub in ["femalefashionadvice", "streetwear", "fashion"]:
            posts = search_reddit(primary_alias, subreddit=sub)
            c, u = score_posts(posts)
            total_posts += c
            total_upvotes += u

        if total_posts == 0:
            return 0.0

        post_score = min(60.0, (total_posts / 20) * 60)
        upvote_score = min(40.0, (total_upvotes / 1000) * 40)
        return round(post_score + upvote_score, 2)

    except Exception as e:
        print(f"[reddit_trends] Error for '{keyword}': {e}")
        return 0.0


def get_brand_reddit_signal(brand: str) -> float:
    """Get Reddit engagement for a specific brand's FW26 show."""
    try:
        search_terms = BRAND_SEARCH_TERMS.get(brand, [f"{brand} fall 2026", f"{brand} fw26"])
        total_posts = 0
        total_upvotes = 0

        for term in search_terms[:2]:
            posts = search_reddit(term)
            c, u = score_posts(posts, days=180)
            total_posts += c
            total_upvotes += u

        if total_posts == 0:
            return 0.0

        post_score = min(60.0, (total_posts / 15) * 60)
        upvote_score = min(40.0, (total_upvotes / 500) * 40)
        return round(post_score + upvote_score, 2)

    except Exception as e:
        print(f"[reddit_trends] Error for brand '{brand}': {e}")
        return 0.0
