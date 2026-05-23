import pytest
import json
import os
from unittest.mock import MagicMock, patch

os.environ["DB_PATH"] = ":memory:"
os.environ["AWS_REGION"] = "us-east-1"

from services.llm_service import LLMService, ParsedQuery


@pytest.fixture
def mock_bedrock(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("boto3.client", lambda *a, **kw: mock_client)
    return mock_client


@pytest.fixture
def llm(mock_bedrock):
    import database; database.init_db()
    with database.db() as conn:
        conn.execute("DELETE FROM llm_cost_log")
    from services.cost_tracking_service import CostTrackingService
    tracker = CostTrackingService(daily_limit_usd=1.0)
    return LLMService(tracker=tracker)


def _llama_response(text: str):
    return {"body": MagicMock(read=lambda: json.dumps({"generation": text}).encode())}


def _haiku_response(text: str):
    return {"body": MagicMock(read=lambda: json.dumps(
        {"content": [{"text": text}]}
    ).encode())}


def test_parse_query_siva_tatvam(llm, mock_bedrock):
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps({
        "topic": "Siva Tatvam",
        "scripture": None,
        "chapter": None,
        "sloka": None,
        "keywords": ["శివ తత్వం", "Shiva Tattva", "Siva philosophy"],
        "language": "Telugu",
        "search_intent": "conceptual discourse"
    }))
    result = llm.parse_query("Siva Tatvam", lang="Telugu")
    assert isinstance(result, ParsedQuery)
    assert result.topic == "Siva Tatvam"
    assert "శివ తత్వం" in result.keywords


def test_parse_query_specific_sloka(llm, mock_bedrock):
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps({
        "topic": "Bhagavad Gita",
        "scripture": "Bhagavad Gita",
        "chapter": 2,
        "sloka": 5,
        "keywords": ["BG 2.5", "భగవద్గీత 2వ అధ్యాయం 5వ శ్లోకం"],
        "language": "Telugu",
        "search_intent": "specific sloka"
    }))
    result = llm.parse_query("Bhagavad Gita Chapter 2 Sloka 5", lang="Telugu")
    assert result.chapter == 2
    assert result.sloka == 5


def test_generate_search_terms_returns_list(llm, mock_bedrock):
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=["శివ తత్వం", "Shiva Tattva"],
        language="Telugu", search_intent="conceptual discourse"
    )
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps([
        "Siva Tatvam Telugu discourse",
        "శివ తత్వం ప్రవచనం",
        "Shiva Tattva Telugu pravachanam"
    ]))
    terms = llm.generate_search_terms(parsed)
    assert len(terms) >= 2
    assert all(isinstance(t, str) for t in terms)


def test_rank_results_orders_by_score(llm, mock_bedrock):
    results = [
        {"title": "Random video", "speaker": "Unknown"},
        {"title": "Siva Tatvam discourse", "speaker": "Chaganti"},
    ]
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=["Siva Tatvam"], language="Telugu", search_intent="discourse"
    )
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps([
        {"index": 0, "score": 0.2},
        {"index": 1, "score": 0.95},
    ]))
    ranked = llm.rank_results(results, parsed)
    assert ranked[0]["title"] == "Siva Tatvam discourse"


def test_fallback_on_budget_exceeded(llm, mock_bedrock):
    from services.cost_tracking_service import CostTrackingService
    import database; database.init_db()
    with database.db() as conn:
        conn.execute("DELETE FROM llm_cost_log")
    tracker = CostTrackingService(daily_limit_usd=0.0)  # already exceeded
    llm_exceeded = LLMService(tracker=tracker)
    result = llm_exceeded.parse_query("Siva Tatvam", lang="Telugu")
    assert result is None
    mock_bedrock.invoke_model.assert_not_called()
