import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

SCHOLAR_RESULT = [{
    "scholar": "Chaganti", "affiliation": "chaganti.net",
    "text": "శివ తత్వం అంటే నిత్య సత్యం.", "highlight": "నిత్య సత్యం",
    "lang": "Telugu", "source_url": "https://chaganti.net"
}]


@pytest.fixture
def client():
    import database; database.init_db()
    from main import app
    return TestClient(app)


def test_vyakhanams_returns_results(client):
    with patch("routers.vyakhanams.scraper_svc") as mock_scraper, \
         patch("routers.vyakhanams.llm_svc") as mock_llm, \
         patch("routers.vyakhanams.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_scraper.scrape.return_value = SCHOLAR_RESULT
        mock_llm.parse_query.return_value = MagicMock(topic="Siva Tatvam")
        mock_llm.highlight_vyakhanams.return_value = SCHOLAR_RESULT
        response = client.get("/api/vyakhanams?q=Siva+Tatvam&lang=Telugu")
    assert response.status_code == 200
    assert response.json()["results"][0]["scholar"] == "Chaganti"


def test_vyakhanams_cache_hit(client):
    with patch("routers.vyakhanams.cache_svc") as mock_cache:
        mock_cache.get.return_value = SCHOLAR_RESULT
        response = client.get("/api/vyakhanams?q=Siva+Tatvam&lang=Telugu")
    assert response.status_code == 200
    assert response.json()["from_cache"] is True
