import re
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://pravachanam.com"
LANG_ID = 20  # Telugu
HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}

# Maps lowercase query keywords → pravachanam.com topic_id (Telugu)
TOPIC_MAP: dict[str, int] = {
    "bhagavad gita": 12,
    "bhagavadgita": 12,
    "gita": 12,
    "dharma nidhi": 442,
    "ramayanam": 37,
    "ramayana": 37,
    "bhagavatham": 22,
    "bhagavatam": 22,
    "bhagavata": 22,
    "thiruppavai": 167,
    "devi": 14,
    "vishnu": 110,
    "lord vishnu": 110,
    "upanishad": 171,
    "upanishads": 171,
    "shiva": 107,
    "siva": 107,
    "lord shiva": 107,
    "mahabharatham": 28,
    "mahabharata": 28,
    "sanathana": 123,
    "sanatan": 123,
    "harikatha": 43,
    "ramanuja": 722,
    "shankaracharya": 89,
    "shankara": 89,
    "adi shankara": 89,
    "adi shankaracharya": 89,
    "vedas": 195,
    "veda": 195,
    "puranas": 343,
    "purana": 343,
    "ramana maharshi": 114,
    "ganesh": 634,
    "ganesha": 634,
    "srivaishnava": 164,
    "vaishnava": 164,
}

# Max speakers per topic to scrape (keeps latency reasonable)
MAX_SPEAKERS = 5


def _find_topic_id(query: str) -> int | None:
    """Return the best matching topic_id for a free-text query, or None."""
    q = query.lower()
    # Try longest keyword match first (most specific)
    for keyword in sorted(TOPIC_MAP, key=len, reverse=True):
        if keyword in q:
            return TOPIC_MAP[keyword]
    return None


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        time.sleep(1)  # respectful rate limiting
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.error(f"pravachanam fetch failed for {url}: {e}")
        return None


def _parse_speakers(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Return list of (speaker_name, pravachana_list_url) from a speaker list page."""
    speakers = []
    for td in soup.select("td.views-field-nothing"):
        a = td.find("a")
        if a and a.get("href"):
            name = a.get_text(strip=True)
            href = a["href"].split("?")[0]  # drop query params
            url = f"{BASE_URL}{href}"
            speakers.append((name, url))
    return speakers[:MAX_SPEAKERS]


def _parse_pravachanams(soup: BeautifulSoup, speaker_url: str) -> list[dict]:
    """Return list of pravachana dicts from a speaker's pravachana list page."""
    results = []
    for td in soup.select("td.views-field-views-conditional-field-1"):
        text = td.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        title = lines[0].rstrip(":")

        artist_m = re.search(r"Artist:\s*(.+)", text)
        duration_m = re.search(r"Duration:\s*(.+)", text)
        files_m = re.search(r"No\.of Files:\s*(\d+)", text)
        category_m = re.search(r"Category:\s*\[(.+?)\]", text)

        results.append({
            "scholar": artist_m.group(1).strip() if artist_m else "",
            "title": title,
            "category": category_m.group(1).strip() if category_m else "",
            "duration": duration_m.group(1).strip() if duration_m else "",
            "files_count": int(files_m.group(1)) if files_m else 0,
            "url": speaker_url,
            "lang": "Telugu",
            "source": "pravachanam.com",
        })
    return results


class PravachanamService:
    def search(self, query: str, lang: str = "Telugu") -> list[dict]:
        topic_id = _find_topic_id(query)
        if topic_id is None:
            return []

        speaker_list_url = f"{BASE_URL}/speakerbrowselist/{topic_id}/{LANG_ID}"
        soup = _fetch(speaker_list_url)
        if soup is None:
            return []

        speakers = _parse_speakers(soup)
        results = []
        for _name, pravachana_url in speakers:
            p_soup = _fetch(pravachana_url)
            if p_soup is None:
                continue
            results.extend(_parse_pravachanams(p_soup, pravachana_url))

        return results
