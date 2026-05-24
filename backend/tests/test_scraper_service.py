import pytest
from unittest.mock import patch, MagicMock
from services.scraper_service import ScraperService, _telugu_ratio, SOURCES


@pytest.fixture
def svc():
    return ScraperService()


def _html(body: str) -> MagicMock:
    m = MagicMock()
    m.text = f"<html><body>{body}</body></html>"
    m.raise_for_status = MagicMock()
    return m


# ── Unit tests for _telugu_ratio helper ──────────────────────────────────────

def test_telugu_ratio_pure_telugu():
    ratio = _telugu_ratio("శివ తత్వం అంటే నిత్య సత్యం")
    assert ratio > 0.5


def test_telugu_ratio_pure_english():
    ratio = _telugu_ratio("This is an English sentence about dharma")
    assert ratio == 0.0


def test_telugu_ratio_empty():
    assert _telugu_ratio("") == 0.0


def test_telugu_ratio_mixed():
    ratio = _telugu_ratio("శివ tatvam means")  # ~30% Telugu
    assert 0.0 < ratio < 1.0


# ── Integration tests for ScraperService ─────────────────────────────────────

def test_scrape_returns_scholar_entries(svc):
    telugu_para = "శివ తత్వం అంటే నిత్య సత్యం అని చెప్పారు. ఇది చాలా ముఖ్యమైన విషయం ఇందులో చాలా అర్థం ఉంది ఇంకా మరిన్ని వివరాలు."
    html = _html(f"<p>{telugu_para}</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep"):
            results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert isinstance(results, list)
    assert len(results) > 0


def test_scrape_includes_source_url(svc):
    telugu_para = "శివ తత్వం అంటే నిత్య సత్యం అని చెప్పారు. ఇది చాలా ముఖ్యమైన విషయం ఇందులో చాలా అర్థం ఉంది ఇంకా మరిన్ని వివరాలు."
    html = _html(f"<p>{telugu_para}</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep"):
            results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert all("source_url" in r for r in results)
    assert all(r["source_url"].startswith("http") for r in results)


def test_respects_rate_limit(svc):
    html = _html("<p>శివ తత్వం అంటే నిత్య సత్యం అని చెప్పారు. ఇది చాలా ముఖ్యమైన విషయం ఇందులో చాలా అర్థం ఉంది ఇంకా మరిన్ని వివరాలు.</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep") as mock_sleep:
            svc.scrape("test", lang="Telugu")
    assert mock_sleep.call_count == len(SOURCES)


def test_failed_request_skipped(svc):
    with patch("requests.get", side_effect=Exception("timeout")):
        results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert results == []


def test_english_only_paragraphs_filtered_out(svc):
    # Paragraph is entirely English — must be filtered by Telugu ratio check
    html = _html("<p>This is completely English text that should be filtered away because it has no Telugu characters at all and is long enough.</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep"):
            results = svc.scrape("Siva Tatvam", lang="Telugu")
    # All paragraphs fail the Telugu ratio threshold, so no results
    assert results == []


def test_sources_are_authentic_telugu_sites(svc):
    from services.scraper_service import SOURCES
    affiliations = {s["affiliation"] for s in SOURCES}
    assert "chaganti.net" in affiliations
    assert "samavedam.org" in affiliations
    assert "chinnajeeyar.org" in affiliations
    # speakingtree.in (English site) must be gone
    assert "speakingtree.in" not in affiliations
