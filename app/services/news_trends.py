"""
news_trends.py — Google News RSS signal
Searches both trend keywords AND brand/season combinations.
No API key required.
"""

import httpx
import feedparser
from datetime import datetime, timedelta, timezone
from urllib.parse import quote


# Keyword aliases — broader search terms for each trend
KEYWORD_ALIASES = {
    "Leather Outerwear": ["leather jacket 2026", "leather coat", "crocodile leather", "leather outerwear", "croc-embossed leather"],
    "Shearling": ["shearling coat 2026", "shearling jacket", "sheepskin", "sheepskin fashion", "lambskin"],
    "Ballet Flats": ["ballet flats trend 2026", "ballet flat shoes", "ballet flats", "ballet shoes", "ballet flat"],
    "Mary Janes": ["mary jane shoes trend 2026", "mary jane fashion"],
    "Wide-Leg Tailoring": ["wide leg trousers 2026", "wide leg pants trend"],
    "Power Suiting": ["power suit trend 2026", "oversized suit"],
    "Prairie Dress": ["prairie dress trend 2026", "cottagecore 2026"],
    "Sheer Layers": ["sheer fashion trend 2026", "transparent clothing trend"],
    "Boucle Tweed": ["tweed fashion 2026", "boucle coat trend"],
    "Velvet": ["velvet fashion 2026", "velvet clothing trend"],
    "Satin": ["satin dress trend 2026", "satin fashion"],
    "Lace": ["lace fashion trend 2026", "lace clothing"],
    "Camel": ["camel coat 2026", "camel color fashion trend"],
    "Chocolate Brown": ["chocolate brown fashion 2026", "brown clothing trend"],
    "Ivory & Cream": ["ivory fashion 2026", "cream color trend fashion"],
    "Forest Green": ["forest green fashion 2026", "dark green clothing trend"],
    "Burgundy": ["burgundy fashion 2026", "wine color trend"],
    "Cobalt Blue": ["cobalt blue fashion 2026", "bright blue clothing"],
    "Oversized Coat": ["oversized coat trend 2026", "cocoon coat fashion"],
    "Miu Miu aesthetic": ["miu miu fall 2026", "miu miu fw26", "miuccia prada 2026", "raf simons 2026"],
    "Matthieu Blazy Chanel": ["matthieu blazy chanel fw26", "chanel fall 2026 collection", "pony hair ballet flat"],
}

# Brand search terms — all 85 FW26 shows
BRAND_NEWS_TERMS = {
    "Acne Studios": ["Acne studios fw26", "Acne studios fall 2026", "Jonny Johansson acne studios", "Acne studios fall/winter 2026"],
    "Alaia": ["Alaia fw26", "Alaia fall 2026", "Pieter mullier Alaia", "Alaia fall/winter 2026"],
    "Altuzarra": ["Altuzarra fw26", "Altuzarra fall 2026", "Joseph Altuzarra", "Altuzarra fall/winter 2026"],
    "Balmain": ["Balmain fw26", "Balmain fall 2026", "Antonin Tron Balmain", "Balmain fall/winter 2026"],
    "Baum und Pferdgarten": ["Baum und Pferdgarten fw26", "Baum und Pferdgarten fall 2026", "Rikke Baumgarten Helle Hestehave", "Baum und Pferdgarten fall/winter 2026"],
    "Blumarine": ["Blumarine fw26", "Blumarine fall 2026", "David Koma Blumarine", "Blumarine fall/winter 2026"],
    "Boss": ["Boss fw26", "Boss fall 2026", "Marco Falcioni Boss", "Boss fall/winter 2026"],
    "Bottega Veneta": ["bottega veneta fw26", "bottega fall 2026", "Louise trotter bottega", "Bottega veneta fall/winter 2026"],
    "Burberry": ["Burberry fw26", "Burberry fall 2026", "Daniel Lee Burberry", "Burberry fall/winter 2026"],
    "Carolina Herrera": ["Carolina Herrera fw26", "Carolina Herrera fall 2026", "Wes Gordon Carolina Herrera", "Carolina Herrera fall/winter 2026"],
    "Celine": ["Celine fw26", "Celine fall 2026", "Michael Rider Celine", "Celine fall/winter 2026"],
    "Chanel": ["chanel fw26", "chanel fall 2026", "matthieu blazy chanel", "Chanel fall/winter 2026"],
    "Chloe": ["chloe fw26", "chloe fall 2026", "Chemena Kamali Chloe", "Chloe fall/winter 2026"],
    "Coach": ["Coach fw26", "Coach fall 2026", "Stuart Vevers Coach", "Coach fall/winter 2026"],
    "Comme des Garcons": ["Comme des Garcons fw26", "Comme des Garcons fall 2026", "Rei Kawakubo Comme des Garcons", "Comme des Garcons fall/winter 2026"],
    "Conner Ives": ["Conner Ives fw26", "Conner Ives fall 2026", "Conner Ives", "Conner Ives fall/winter 2026"],
    "Courreges": ["Courreges fw26", "Courreges fall 2026", "Nicolas di Felice Courreges", "Courreges fall/winter 2026"],
    "Diesel": ["Diesel fw26", "Diesel fall 2026", "Glenn Martens Diesel", "Diesel fall/winter 2026"],
    "Dior": ["dior fw26", "dior fall 2026", "jonathan anderson dior", "Dior fall/winter 2026"],
    "Dolce & Gabbana": ["Dolce & Gabbana fw26", "Dolce & Gabbana fall 2026", "Domenico Dolce Stefano Gabbana", "Dolce & Gabbana fall/winter 2026"],
    "Dries Van Noten": ["Dries Van Noten fw26", "Dries Van Noten fall 2026", "Julian Klausner Dries Van Noten", "Dries Van Noten fall/winter 2026"],
    "Emporio Armani": ["Emporio Armani fw26", "Emporio Armani fall 2026", "Silvana Armani Leo Dell'Orco", "Emporio Armani fall/winter 2026"],
    "Erdem": ["Erdem fw26", "Erdem fall 2026", "Erdem Moralioglu", "Erdem fall/winter 2026"],
    "Etro": ["Etro fw26", "Etro fall 2026", "Marco de Vincenzo Etro", "Etro fall/winter 2026"],
    "Fendi": ["fendi fw26", "fendi fall 2026", "Maria Grazia Chiuri Fendi", "Fendi fall/winter 2026"],
    "Ferragamo": ["Ferragamo fw26", "Ferragamo fall 2026", "Maximilian Davis Ferragamo", "Ferragamo fall/winter 2026"],
    "Gabriela Hearst": ["Gabriela Hearst fw26", "Gabriela Hearst fall 2026", "Gabriela Hearst", "Gabriela Hearst fall/winter 2026"],
    "Giorgio Armani": ["Giorgio Armani fw26", "Giorgio Armani fall 2026", "Silvana Armani", "Giorgio Armani fall/winter 2026"],
    "Givenchy": ["Givenchy fw26", "Givenchy fall 2026", "Sarah Burton Givenchy", "Givenchy fall/winter 2026"],
    "Gucci": ["gucci fw26", "gucci fall 2026", "Demna gucci", "Gucci fall/winter 2026"],
    "Balenciaga": ["Balenciaga fw26", "Balenciaga fall 2026", "Pierpaolo Piccioli balenciaga", "Balenciaga fall/winter 2026"],
    "Hermes": ["Hermes fw26", "Hermes fall 2026", "Nadege Vanhee Hermes", "Hermes fall/winter 2026"],
    "Holzweiler": ["Holzweiler fw26", "Holzweiler fall 2026", "Maria Skappel Holzweiler", "Holzweiler fall/winter 2026"],
    "Isabel Marant": ["Isabel marant fw26", "Isabel Marant fall 2026", "Kim Bekker Isabel Marant", "Isabel Marant fall/winter 2026"],
    "Jacquemus": ["Jacquemus fw26", "Jacquemus fall 2026", "Simone Porte Jacquemus", "Jacquemus fall/winter 2026"],
    "Jean Paul Gaultier": ["Jean Paul Gaultier fw26", "Jean Paul Gaultier fall 2026", "Duran Lantink Jean Paul Gaultier", "Jean Paul Gaultier fall/winter 2026"],
    "Jil Sander": ["Jil Sander fw26", "Jil Sander fall 2026", "Simone Bellotti Jil Sander", "Jil Sander fall/winter 2026"],
    "Junya Watanabe": ["Junya Watanabe fw26", "Junya Watanabe fall 2026", "Junya Watanabe", "Junya Watanabe fall/winter 2026"],
    "Khaite": ["Khaite fw26", "Khaite fall 2026", "Catherine Holstein Khaite", "Khaite fall/winter 2026"],
    "Kiko Kostadinov": ["Kiko Kostadinov fw26", "Kiko Kostadinov fall 2026", "Deanna Fanning Laura Fanning Kiko Kostadinov", "Kiko Kostadinov fall/winter 2026"],
    "Lacoste": ["Lacoste fw26", "Lacoste fall 2026", "Pelagia Kolotouros Lacoste", "Lacoste fall/winter 2026"],
    "Lanvin": ["Lanvin fw26", "Lanvin fall 2026", "Peter Copping Lanvin", "Lanvin fall/winter 2026"],
    "Lemaire": ["Lemaire fw26", "Lemaire fall 2026", "Christophe Lemaire Sarah-Linh Tran", "Lemaire fall/winter 2026"],
    "Loewe": ["Loewe fw26", "Loewe fall 2026", "Jake McCollough Lazaro Hernandez Loewe", "Loewe fall/winter 2026"],
    "Louis Vuitton": ["Louis Vuitton fw26", "Louis Vuitton fall 2026", "Nicolas Ghesquiere Louis Vuitton", "Louis Vuitton fall/winter 2026"],
    "Magda Butrym": ["Magda Butrym fw26", "Magda Butrym fall 2026", "Magda Butrym", "Magda Butrym fall/winter 2026"],
    "Marco Rambaldi": ["Marco Rambaldi fw26", "Marco Rambaldi fall 2026", "Marco Rambaldi", "Marco Rambaldi fall/winter 2026"],
    "Marni": ["Marni fw26", "Marni fall 2026", "Meryll Rogge Marni", "Marni fall/winter 2026"],
    "Max Mara": ["Max Mara fw26", "Max Mara fall 2026", "Ian Griffiths Max Mara", "Max Mara fall/winter 2026"],
    "McQueen": ["McQueen fw26", "McQueen fall 2026", "Sean McGirr McQueen", "McQueen fall/winter 2026"],
    "Michael Kors": ["Michael Kors fw26", "Michael Kors fall 2026", "Michael Kors", "Michael Kors fall/winter 2026"],
    "Missoni": ["Missoni fw26", "Missoni fall 2026", "Alberto Caliri Missoni", "Missoni fall/winter 2026"],
    "Miu Miu": ["Miu Miu fw26", "Miu Miu fall 2026", "Miuccia Prada", "Miu Miu fall/winter 2026"],
    "MM6 Maison Margiela": ["MM6 Maison Margiela fw26", "MM6 Maison Margiela fall 2026", "MM6 Maison Margiela", "MM6 Maison Margiela fall/winter 2026"],
    "Moschino": ["Moschino fw26", "Moschino fall 2026", "Adrian Appiolaza Moschino", "Moschino fall/winter 2026"],
    "Mugler": ["Mugler fw26", "Mugler fall 2026", "Miguel Castro Freitas Mugler", "Mugler fall/winter 2026"],
    "Nina Ricci": ["Nina Ricci fw26", "Nina Ricci fall 2026", "Harris Reed Nina Ricci", "Nina Ricci fall/winter 2026"],
    "No. 21": ["No. 21 fw26", "No. 21 fall 2026", "Alessandro Dell'Acqua No. 21", "No. 21 fall/winter 2026"],
    "Patou": ["Patou fw26", "Patou fall 2026", "Guillaume Henry Patou", "Patou fall/winter 2026"],
    "Prabal Gurung": ["Prabal Gurung fw26", "Prabal Gurung fall 2026", "Prabal Gurung", "Prabal Gurung fall/winter 2026"],
    "Prada": ["Prada fw26", "Prada fall 2026", "Miuccia Prada Raf Simons", "Prada fall/winter 2026"],
    "Proenza Schouler": ["Proenza Schouler fw26", "Proenza Schouler fall 2026", "Rachel Scott Proenza Schouler", "Proenza Schouler fall/winter 2026"],
    "Rabanne": ["Rabanne fw26", "Rabanne fall 2026", "Julien Dossena Rabanne", "Rabanne fall/winter 2026"],
    "Ralph Lauren": ["Ralph Lauren fw26", "Ralph Lauren fall 2026", "Ralph Lauren", "Ralph Lauren fall/winter 2026"],
    "Rave Review": ["Rave Review fw26", "Rave Review fall 2026", "Josephine Bergquist Livia Schuck", "Rave Review fall/winter 2026"],
    "Richard Quinn": ["Richard Quinn fw26", "Richard Quinn fall 2026", "Richard Quinn", "Richard Quinn fall/winter 2026"],
    "Rick Owens": ["Rick Owens fw26", "Rick Owens fall 2026", "Rick Owens", "Rick Owens fall/winter 2026"],
    "Roberto Cavalli": ["Roberto Cavalli fw26", "Roberto Cavalli fall 2026", "Fausto Puglisi Roberto Cavalli", "Roberto Cavalli fall/winter 2026"],
    "Saint Laurent": ["saint laurent fw26", "ysl fall 2026", "Anthony vacarello saint laurent", "Saint Laurent fall/winter 2026"],
    "Sandy Liang": ["Sandy Liang fw26", "Sandy Liang fall 2026", "Sandy Liang", "Sandy Liang fall/winter 2026"],
    "Schiaparelli": ["Schiaparelli fw26", "Schiaparelli fall 2026", "Daniel Roseberry Schiaparelli", "Schiaparelli fall/winter 2026"],
    "Simone Rocha": ["Simone Rocha fw26", "Simone Rocha fall 2026", "Simone Rocha", "Simone Rocha fall/winter 2026"],
    "Skall Studio": ["Skall Studio fw26", "Skall Studio fall 2026", "Julie Skall Marie Skall", "Skall Studio fall/winter 2026"],
    "Sportmax": ["Sportmax fw26", "Sportmax fall 2026", "Sportmax", "Sportmax fall/winter 2026"],
    "Stella McCartney": ["Stella McCartney fw26", "Stella McCartney fall 2026", "Stella McCartney", "Stella McCartney fall/winter 2026"],
    "Tod's": ["Tod's fw26", "Tod's fall 2026", "Matteo Tamburini Tod's", "Tod's fall/winter 2026"],
    "Tom Ford": ["Tom Ford fw26", "Tom Ford fall 2026", "Haider Ackermann Tom Ford", "Tom Ford fall/winter 2026"],
    "Tory Burch": ["Tory Burch fw26", "Tory Burch fall 2026", "Tory Burch", "Tory Burch fall/winter 2026"],
    "Toteme": ["Toteme fw26", "Toteme fall 2026", "Elin Kling Karl Lindman Toteme", "Toteme fall/winter 2026"],
    "Ulla Johnson": ["Ulla Johnson fw26", "Ulla Johnson fall 2026", "Ulla Johnson", "Ulla Johnson fall/winter 2026"],
    "Undercover": ["Undercover fw26", "Undercover fall 2026", "Jun Takahashi Undercover", "Undercover fall/winter 2026"],
    "Valentino": ["valentino fw26", "valentino fall 2026", "Alessandro michele valentino", "Valentino fall/winter 2026"],
    "Victoria Beckham": ["Victoria Beckham fw26", "Victoria Beckham fall 2026", "Victoria Beckham", "Victoria Beckham fall/winter 2026"],
    "Yohji Yamamoto": ["Yohji Yamamoto fw26", "Yohji Yamamoto fall 2026", "Yohji Yamamoto", "Yohji Yamamoto fall/winter 2026"],
    "Zimmermann": ["zimmermann fw26", "zimmermann fall 2026", "Nicky Zimmermann", "Zimmermann fall/winter 2026"],
}


def search_google_news(query: str, days: int = 30) -> int:
    """Search Google News RSS and return article count for past N days."""
    try:
        encoded = quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        response = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; runwayfyi/1.0)"
        })
        if response.status_code != 200:
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
        print(f"[news_trends] Error for '{query}': {e}")
        return 0


def get_news_signal(keyword: str, days: int = 30) -> float:
    """
    Get a 0-100 news signal for a trend keyword.
    Searches the keyword itself plus any aliases.
    """
    try:
        count = search_google_news(f"{keyword} fashion", days)
        aliases = KEYWORD_ALIASES.get(keyword, [])
        for alias in aliases[:2]:
            count += search_google_news(alias, days)
        score = min(100.0, (count / 30) * 100)
        return round(score, 2)
    except Exception as e:
        print(f"[news_trends] Error for '{keyword}': {e}")
        return 0.0


def get_brand_news_signal(brand: str, days: int = 60) -> float:
    """Get news coverage score for a specific brand's FW26 show."""
    terms = BRAND_NEWS_TERMS.get(brand, [f"{brand} fall 2026", f"{brand} fw26"])
    count = 0
    for term in terms[:2]:
        count += search_google_news(term, days)
    return min(100.0, round((count / 20) * 100, 2))
