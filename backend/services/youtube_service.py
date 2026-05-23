import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {"Telugu": "te", "English": "en", "Sanskrit": "sa", "Hindi": "hi"}

AUTHENTIC_CHANNELS = {
    "chaganti",
    "garikapati",
    "garikipati",
    "samavedam",
    "jeeyar",
    "chinnajeeyar",
    "bhakthi tv",
    "telugupuranam",
    "suman tv",
    "sumantvvijayawada",
    "iskcon",
    "tridandi",
    "pravachanam",
    "dharmasandehalu",
    "brahmasri",
}


def _is_authentic(channel_title: str) -> bool:
    lower = channel_title.lower()
    return any(keyword in lower for keyword in AUTHENTIC_CHANNELS)


class YouTubeService:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable not set")
        self._yt = build("youtube", "v3", developerKey=api_key)

    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        seen = set()
        results = []
        relevance_lang = LANG_CODE.get(lang, "te")
        for term in terms:
            try:
                resp = (
                    self._yt.search()
                    .list(
                        q=term,
                        part="snippet",
                        type="video",
                        maxResults=max_results,
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
                logger.error(f"YouTube search failed for term '{term}': {e}")

        authentic = [r for r in results if _is_authentic(r["speaker"])]
        return authentic if authentic else results
