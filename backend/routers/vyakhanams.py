import os
import logging
from fastapi import APIRouter, Query
from services.scraper_service import ScraperService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService
from services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
scraper_svc = ScraperService()
cache_svc = CacheService()


@router.get("/vyakhanams")
def vyakhanams(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),  # kept for API compat, always uses Telugu
):
    # Always Telugu regardless of requested language
    cache_key_lang = "Telugu"
    cached = cache_svc.get("vyakhanam", q, cache_key_lang)
    if cached is not None:
        return {"results": cached, "from_cache": True}

    raw = scraper_svc.scrape(q, lang="Telugu")
    parsed = llm_svc.parse_query(q, lang="Telugu")
    results = llm_svc.highlight_vyakhanams(raw, parsed) if parsed and raw else raw
    cache_svc.set("vyakhanam", q, cache_key_lang, results)

    return {"results": results, "from_cache": False}
