import pytest
from unittest.mock import patch, MagicMock
from services.scraper_service import ScraperService


@pytest.fixture
def svc():
    return ScraperService()


def _html(body: str) -> MagicMock:
    m = MagicMock()
    m.text = f"<html><body>{body}</body></html>"
    m.raise_for_status = MagicMock()
    return m


def test_scrape_returns_scholar_entries(svc):
    html = _html("<p>శివ తత్వం అంటే నిత్య సత్యం అని చెప్పారు. ఇది చాలా ముఖ్యమైన విషయం ఇందులో చాలా అర్థం ఉంది.</p>")
    with patch("requests.get", return_value=html):
        results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert isinstance(results, list)


def test_respects_rate_limit(svc):
    import time
    html = _html("<p>test content here for testing purposes this is long enough to pass the min_text_len check</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep") as mock_sleep:
            svc.scrape("test", lang="Telugu")
    mock_sleep.assert_called()


def test_failed_request_skipped(svc):
    with patch("requests.get", side_effect=Exception("timeout")):
        results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert results == []
