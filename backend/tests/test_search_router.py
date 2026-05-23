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
         patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Siva Tatvam", keywords=["Siva Tatvam"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Siva Tatvam Telugu"]
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.tracker.is_warning_threshold.return_value = False
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["video_id"] == "abc"
    assert data["budget_warning"] is False


def test_search_returns_cache_on_hit(client):
    with patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = VIDEO_RESULT
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["results"][0]["video_id"] == "abc"


def test_search_fallback_on_llm_none(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = None  # budget exceeded
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.tracker.is_warning_threshold.return_value = True
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["budget_warning"] is True


def test_search_includes_explanation(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache:
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
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    data = response.json()
    assert "explanation" in data
    assert data["explanation"] == "Siva Tatvam describes the nature of Lord Shiva."
    assert data["related_topics"] == ["Panchakshara", "Rudram", "Shiva Purana"]


def test_missing_query_returns_422(client):
    response = client.get("/api/search?lang=Telugu&type=video")
    assert response.status_code == 422
