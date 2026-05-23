import logging
import requests

logger = logging.getLogger(__name__)
ARCHIVE_SEARCH_URL = "https://archive.org/advancedsearch.php"


class ArchiveService:
    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        seen = set()
        results = []
        for term in terms:
            try:
                resp = requests.get(
                    ARCHIVE_SEARCH_URL,
                    params={
                        "q": f"({term}) AND mediatype:audio",
                        "fl[]": ["identifier", "title", "creator", "description", "avg_rating"],
                        "output": "json",
                        "rows": max_results,
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
                        "audio_url": f"https://archive.org/download/{ident}",
                        "page_url": f"https://archive.org/details/{ident}",
                        "rating": doc.get("avg_rating"),
                        "lang": lang,
                    })
            except Exception as e:
                logger.error(f"archive.org search failed for '{term}': {e}")
        return results
