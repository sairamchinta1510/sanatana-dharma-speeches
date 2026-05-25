import dataclasses
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import database; database.init_db()
    from main import app
    return TestClient(app)


VIDEO_RESULT = [{"video_id": "abc", "title": "Siva Tatvam", "speaker": "Chaganti",
                 "url": "https://youtube.com/watch?v=abc", "lang": "Telugu",
                 "description": "", "thumbnail": ""}]


def test_search_video_returns_results(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Siva Tatvam", keywords=["Siva Tatvam"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Siva Tatvam Telugu"]
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = []
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["video_id"] == "abc"
    assert data["budget_warning"] is False


def test_search_returns_cache_on_hit(client):
    with patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = VIDEO_RESULT
        mock_llm.parse_query.return_value = MagicMock(
            topic="Siva Tatvam", keywords=["Siva Tatvam"], language="Telugu"
        )
        mock_llm.explain_topic.return_value = None
        mock_local.search.return_value = []
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["results"][0]["video_id"] == "abc"


def test_search_fallback_on_llm_none(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = None  # budget exceeded
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.tracker.is_warning_threshold.return_value = True
        mock_local.search.return_value = []
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["budget_warning"] is True


def test_search_includes_explanation(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Siva Tatvam", keywords=["Siva Tatvam"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Siva Tatvam Telugu"]
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.explain_topic.return_value = {
            "explanation": "Siva Tatvam describes the nature of Lord Shiva.",
            "related_topics": ["Panchakshara", "Rudram", "Shiva Purana"],
        }
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = []
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    data = response.json()
    assert "explanation" in data
    assert data["explanation"] == "Siva Tatvam describes the nature of Lord Shiva."
    assert data["related_topics"] == ["Panchakshara", "Rudram", "Shiva Purana"]


def test_missing_query_returns_422(client):
    response = client.get("/api/search?lang=Telugu&type=video")
    assert response.status_code == 422


def test_raw_query_prepended_to_llm_terms(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Karma Yoga", keywords=["Karma"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Nishkama Karma"]
        mock_yt.search.return_value = []
        mock_llm.rank_results.return_value = []
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = []

        response = client.get("/api/search?q=Karma+Yoga&lang=Telugu&type=video")

    assert response.status_code == 200
    terms_used = mock_yt.search.call_args[0][0]  # first positional arg to yt_svc.search
    assert terms_used[0] == "Karma Yoga", "raw query must be first term"
    assert "Nishkama Karma" in terms_used, "LLM terms must also be included"


LOCAL_RESULT = {
    "title": "Rigveda",
    "category": "Veda",
    "page_number": 1,
    "excerpt": "ఋగ్వేద సంహిత",
    "pdf_url": "https://s3.example.com/presigned",
    "pdf_key": "pdfs/Veda/Rigveda.pdf",
}


def test_search_includes_local_results(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Rigveda", keywords=["Rigveda"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Rigveda Telugu"]
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = [
            MagicMock(**LOCAL_RESULT, __class__=object)
        ]
        # Use dataclasses mock to avoid asdict issues

        @dataclasses.dataclass
        class FakeLocalResult:
            title: str = LOCAL_RESULT["title"]
            category: str = LOCAL_RESULT["category"]
            page_number: int = LOCAL_RESULT["page_number"]
            excerpt: str = LOCAL_RESULT["excerpt"]
            pdf_url: str = LOCAL_RESULT["pdf_url"]
            pdf_key: str = LOCAL_RESULT["pdf_key"]

        mock_local.search.return_value = [FakeLocalResult()]

        response = client.get("/api/search?q=Rigveda&lang=Telugu&type=video")

    assert response.status_code == 200
    data = response.json()
    assert "local_results" in data
    assert len(data["local_results"]) == 1
    assert data["local_results"][0]["title"] == "Rigveda"
    assert data["local_results"][0]["category"] == "Veda"


def test_search_local_results_empty_when_no_match(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Unknown", keywords=[], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = []
        mock_yt.search.return_value = []
        mock_llm.rank_results.return_value = []
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = []

        response = client.get("/api/search?q=unknown&lang=Telugu&type=video")

    assert response.status_code == 200
    assert response.json()["local_results"] == []


def test_search_cache_hit_includes_local_results(client):
    """Even on cache hit, local_results must be returned (presigned URLs are time-sensitive)."""
    with patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = VIDEO_RESULT
        mock_llm.parse_query.return_value = MagicMock(
            topic="Rigveda", keywords=["Rigveda"], language="Telugu"
        )
        mock_llm.explain_topic.return_value = None

        @dataclasses.dataclass
        class FakeLocalResult:
            title: str = "Rigveda"
            category: str = "Veda"
            page_number: int = 1
            excerpt: str = "ఋగ్వేద"
            pdf_url: str = "https://s3.example.com/presigned"
            pdf_key: str = "pdfs/Veda/Rigveda.pdf"

        mock_local.search.return_value = [FakeLocalResult()]

        response = client.get("/api/search?q=Rigveda&lang=Telugu&type=video")

    assert response.status_code == 200
    data = response.json()
    assert data["from_cache"] is True
    assert "local_results" in data
    assert len(data["local_results"]) == 1
