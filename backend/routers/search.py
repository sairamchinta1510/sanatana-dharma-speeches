# backend/routers/search.py
import os
import dataclasses
import logging
from fastapi import APIRouter, Query, HTTPException
from services.llm_service import LLMService
from services.youtube_service import YouTubeService
from services.archive_service import ArchiveService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService
from services.local_content_service import LocalContentService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
yt_svc = YouTubeService()
archive_svc = ArchiveService()
cache_svc = CacheService()
local_content_svc = LocalContentService()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),
    type: str = Query("video"),
):
    if type not in ("video", "audio"):
        raise HTTPException(status_code=400, detail="type must be 'video' or 'audio'")

    # Always run local search fresh — presigned URLs expire after 1h
    parsed = llm_svc.parse_query(q, lang=lang)
    topic = parsed.topic if parsed and isinstance(parsed.topic, str) and parsed.topic else q
    local_results = local_content_svc.search(topic, q)

    cached = cache_svc.get(type, q, lang)
    if cached:  # only serve non-empty cached results
        explanation_data = llm_svc.explain_topic(parsed) if parsed else None
        return {
            "results": cached,
            "local_results": [dataclasses.asdict(r) for r in local_results],
            "explanation": explanation_data.get("explanation") if explanation_data else None,
            "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
            "budget_warning": False,
            "from_cache": True,
        }

    if parsed:
        canonical = parsed.topic if isinstance(parsed.topic, str) and parsed.topic else q
        raw_terms = ([canonical] if canonical.lower() != q.lower() else []) + [q] + llm_svc.generate_search_terms(parsed)
        seen_t: set[str] = set()
        terms: list[str] = []
        for t in raw_terms:
            if isinstance(t, str) and t and t not in seen_t:
                seen_t.add(t)
                terms.append(t)
    else:
        terms = [q]

    if type == "video":
        raw = yt_svc.search(terms, lang=lang)
    else:
        ascii_terms = [t for t in terms if isinstance(t, str) and any(c.isascii() and c.isalpha() for c in t)][:2]
        if not ascii_terms:
            ascii_terms = [q]
        raw = archive_svc.search(ascii_terms, lang=lang)
        if not raw:
            raw = archive_svc.search([q], lang=lang)

    results = llm_svc.rank_results(raw, parsed) if parsed else raw
    explanation_data = llm_svc.explain_topic(parsed) if parsed else None

    if results:
        cache_svc.set(type, q, lang, results)

    return {
        "results": results,
        "local_results": [dataclasses.asdict(r) for r in local_results],
        "explanation": explanation_data.get("explanation") if explanation_data else None,
        "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
        "budget_warning": llm_svc.tracker.is_warning_threshold(),
        "from_cache": False,
    }
