import logging
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCES = [
    {
        "scholar": "Brahmasri Chaganti Koteswara Rao",
        "affiliation": "chaganti.net",
        "url_template": "https://www.chaganti.net/search?q={query}",
        "lang": "Telugu",
        "content_selector": ".search-result-text, article p, .entry-content p, p",
        "min_telugu_ratio": 0.3,
    },
    {
        "scholar": "Brahmasri Samavedam Shanmukha Sharma",
        "affiliation": "samavedam.org",
        "url_template": "https://www.samavedam.org/?s={query}",
        "lang": "Telugu",
        "content_selector": ".entry-content p, .post-content p, p",
        "min_telugu_ratio": 0.3,
    },
    {
        "scholar": "Sri Sri Tridandi Chinna Jeeyar Swami",
        "affiliation": "chinnajeeyar.org",
        "url_template": "https://www.chinnajeeyar.org/?s={query}",
        "lang": "Telugu",
        "content_selector": ".entry-content p, .post-body p, p",
        "min_telugu_ratio": 0.2,
    },
]

HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}


def _telugu_ratio(text: str) -> float:
    """Return the fraction of characters in text that are Telugu Unicode (U+0C00–U+0C7F)."""
    if not text:
        return 0.0
    telugu_chars = sum(1 for c in text if "\u0C00" <= c <= "\u0C7F")
    return telugu_chars / len(text)


class ScraperService:
    def scrape(self, query: str, lang: str, min_text_len: int = 80) -> list[dict]:
        results = []
        for source in SOURCES:
            time.sleep(1)
            url = source["url_template"].format(query=requests.utils.quote(query))
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [
                    p.get_text(strip=True)
                    for p in soup.select(source["content_selector"])
                    if len(p.get_text(strip=True)) > min_text_len
                    and _telugu_ratio(p.get_text(strip=True)) >= source["min_telugu_ratio"]
                ]
                if not paragraphs:
                    continue
                results.append({
                    "scholar": source["scholar"],
                    "affiliation": source["affiliation"],
                    "source_url": url,
                    "lang": source["lang"],
                    "text": " ".join(paragraphs[:3]),
                    "highlight": None,
                })
            except Exception as e:
                logger.error(f"Scrape failed for {source['scholar']}: {e}")
        return results
