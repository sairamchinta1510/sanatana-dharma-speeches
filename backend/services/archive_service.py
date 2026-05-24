import logging
import requests
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
ARCHIVE_SEARCH_URL = "https://archive.org/advancedsearch.php"
_AUDIO_FORMATS = {"mp3", "vbr mp3", "128kbps mp3", "64kbps mp3", "ogg vorbis"}
API_BASE = "https://api.find.sanatanadharmas.com"


def _resolve_mp3_url(identifier: str) -> str:
    """Resolve the direct archive.org MP3 URL and wrap it in our proxy endpoint.

    The proxy is needed because archive.org CDN nodes reject direct browser
    requests intermittently, while server-side requests always succeed.
    """
    try:
        meta = requests.get(
            f"https://archive.org/metadata/{identifier}",
            timeout=8,
        ).json()
        for f in meta.get("files", []):
            if f.get("format", "").lower() in _AUDIO_FORMATS:
                filename = quote(f['name'], safe='')
                direct_url = f"https://archive.org/download/{identifier}/{filename}"
                return f"{API_BASE}/api/audio-proxy?url={quote(direct_url, safe='')}"
    except Exception as e:
        logger.warning("Metadata lookup failed for %s: %s", identifier, e)
    # Fallback: proxy the item download page
    direct_url = f"https://archive.org/download/{identifier}"
    return f"{API_BASE}/api/audio-proxy?url={quote(direct_url, safe='')}"


class ArchiveService:
    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        seen = set()
        results = []
        for term in terms:
            try:
                resp = requests.get(
                    ARCHIVE_SEARCH_URL,
                    params={
                        # downloads:[50 TO *] filters out private/restricted items;
                        # sort by downloads ensures popular public items come first.
                        "q": f"({term}) AND mediatype:audio AND downloads:[50 TO *]",
                        "fl[]": ["identifier", "title", "creator", "description", "avg_rating"],
                        "output": "json",
                        "rows": max_results,
                        "sort[]": "downloads desc",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                for doc in resp.json().get("response", {}).get("docs", []):
                    ident = doc.get("identifier", "")
                    if ident in seen:
                        continue
                    seen.add(ident)
                    results.append({
                        "identifier": ident,
                        "title": doc.get("title", ident),
                        "speaker": doc.get("creator", "Unknown"),
                        "description": doc.get("description", ""),
                        "audio_url": None,  # resolved below
                        "page_url": f"https://archive.org/details/{ident}",
                        "rating": doc.get("avg_rating"),
                        "lang": lang,
                    })
            except Exception as e:
                logger.error(f"archive.org search failed for '{term}': {e}")

        # Resolve actual MP3 URLs in parallel (max 5 workers to be polite)
        with ThreadPoolExecutor(max_workers=5) as ex:
            future_map = {ex.submit(_resolve_mp3_url, r["identifier"]): i for i, r in enumerate(results)}
            for future in as_completed(future_map):
                results[future_map[future]]["audio_url"] = future.result()

        return results
