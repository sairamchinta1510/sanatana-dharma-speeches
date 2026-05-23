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
        "content_selector": "p",
    },
    {
        "scholar": "Brahmasri Garikapati Narasimha Rao",
        "affiliation": "speakingtree.in",
        "url_template": "https://www.speakingtree.in/search/{query}",
        "lang": "Telugu",
        "content_selector": "p",
    },
]

HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}


class ScraperService:
    def scrape(self, query: str, lang: str, min_text_len: int = 80) -> list[dict]:
        results = []
        for source in SOURCES:
            time.sleep(1)  # respectful rate limiting
            url = source["url_template"].format(query=requests.utils.quote(query))
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [
                    p.get_text(strip=True)
                    for p in soup.select(source["content_selector"])
                    if len(p.get_text(strip=True)) > min_text_len
                ]
                if not paragraphs:
                    continue
                results.append({
                    "scholar": source["scholar"],
                    "affiliation": source["affiliation"],
                    "source_url": url,
                    "lang": source["lang"],
                    "text": " ".join(paragraphs[:3]),
                    "highlight": None,  # filled by LLMService.highlight_vyakhanams
                })
            except Exception as e:
                logger.error(f"Scrape failed for {source['scholar']}: {e}")
        return results
