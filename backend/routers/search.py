import os
import logging
from fastapi import APIRouter, Query, HTTPException
from services.llm_service import LLMService
from services.youtube_service import YouTubeService
from services.archive_service import ArchiveService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
yt_svc = YouTubeService()
archive_svc = ArchiveService()
cache_svc = CacheService()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),
    type: str = Query("video"),
):
    if type not in ("video", "audio"):
        raise HTTPException(status_code=400, detail="type must be 'video' or 'audio'")

    cached = cache_svc.get(type, q, lang)
    if cached is not None:
        explanation_cache = cache_svc.get(f"{type}_explanation", q, lang)
        exp = explanation_cache[0] if explanation_cache else None
        return {
            "results": cached,
            "explanation": exp.get("explanation") if exp else None,
            "related_topics": exp.get("related_topics", []) if exp else [],
            "budget_warning": False,
            "from_cache": True,
        }

    parsed = llm_svc.parse_query(q, lang=lang)
    if parsed:
        terms = llm_svc.generate_search_terms(parsed)
    else:
        terms = [q]

    if type == "video":
        raw = yt_svc.search(terms, lang=lang)
    else:
        raw = archive_svc.search(terms, lang=lang)

    results = llm_svc.rank_results(raw, parsed) if parsed else raw

    explanation_data = llm_svc.explain_topic(parsed) if parsed else None

    cache_svc.set(type, q, lang, results)
    if explanation_data:
        cache_svc.set(f"{type}_explanation", q, lang, [explanation_data])

    return {
        "results": results,
        "explanation": explanation_data.get("explanation") if explanation_data else None,
        "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
        "budget_warning": llm_svc.tracker.is_warning_threshold(),
        "from_cache": False,
    }
