import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {"Telugu": "te", "English": "en", "Sanskrit": "sa", "Hindi": "hi"}

SCHOLAR_QUERIES = [
    "Chaganti Koteswara Rao Telugu",
    "Garikipati Narasimha Rao Telugu",
    "Samavedam Shanmukha Sharma Telugu",
    "ISKCON Telugu pravachanam",
    "Bhakthi TV Telugu pravachanam",
]

_STOP_WORDS = {"the", "a", "an", "of", "in", "and", "or", "to", "for", "on", "by", "with", "at", "from", "is", "are", "was", "be"}


class YouTubeService:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable not set")
        self._yt = build("youtube", "v3", developerKey=api_key)

    def search(self, terms: list[str], lang: str, max_results: int = 15) -> list[dict]:
        if not terms:
            return []
        primary = terms[0] if isinstance(terms[0], str) else str(terms[0])
        secondary = terms[1] if len(terms) > 1 and isinstance(terms[1], str) else None

        relevance_lang = LANG_CODE.get(lang, "te")
        seen: set[str] = set()
        results: list[dict] = []

        # Build query list: scholar-suffixed queries for primary (and secondary if present)
        query_topics = [primary] + ([secondary] if secondary else [])
        queries: list[str] = []
        for topic in query_topics:
            for suffix in SCHOLAR_QUERIES:
                queries.append(f"{topic} {suffix}")
        # Baseline: direct topic search (no scholar bias) — lets YouTube handle spelling variants
        queries.append(f"{primary} Telugu pravachanam")
        queries.append(f"{primary} Telugu")

        # Bare queries for LLM-generated terms (terms[2+]) — often contain better spellings,
        # Telugu script variants (e.g. "భృగువల్లి"), and more specific formulations.
        for extra in terms[2:4]:
            if isinstance(extra, str) and extra.strip():
                queries.append(extra)

        for query in queries:
            try:
                resp = (
                    self._yt.search()
                    .list(
                        q=query,
                        part="snippet",
                        type="video",
                        maxResults=3,
                        relevanceLanguage=relevance_lang,
                    )
                    .execute()
                )
                for item in resp.get("items", []):
                    vid = item["id"]["videoId"]
                    if vid in seen:
                        continue
                    seen.add(vid)
                    s = item["snippet"]
                    results.append({
                        "video_id": vid,
                        "title": s["title"],
                        "speaker": s["channelTitle"],
                        "description": s.get("description", ""),
                        "thumbnail": s.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "lang": lang,
                    })
            except Exception as e:
                logger.error(f"YouTube search failed for query '{query}': {e}")

        return self._filter_by_topic(results, primary)[:max_results]

    @staticmethod
    def _extract_keywords(topic: str) -> list[str]:
        if not isinstance(topic, str):
            topic = " ".join(topic) if isinstance(topic, list) else str(topic)
        result = []
        for w in topic.lower().split():
            cleaned = w.strip(".,!?()")
            if cleaned not in _STOP_WORDS and len(cleaned) > 1:
                result.append(cleaned)
        return result

    @staticmethod
    def _filter_by_topic(results: list[dict], topic: str) -> list[dict]:
        keywords = YouTubeService._extract_keywords(topic)
        if not keywords:
            return results
        threshold = max(1, len(keywords) // 4)

        def passes(r: dict) -> bool:
            text = (r.get("title", "") + " " + r.get("description", "")).lower()
            return sum(1 for kw in keywords if kw in text) >= threshold

        filtered = [r for r in results if passes(r)]
        return filtered if filtered else results
