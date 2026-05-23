import pytest
from unittest.mock import patch, MagicMock
import json
from services.archive_service import ArchiveService


@pytest.fixture
def svc():
    return ArchiveService()


def _mock_response(docs):
    m = MagicMock()
    m.json.return_value = {"response": {"docs": docs}}
    m.raise_for_status = MagicMock()
    return m


def test_search_returns_normalized_results(svc):
    doc = {
        "identifier": "siva-tatvam-telugu",
        "title": "Siva Tatvam Full",
        "creator": "Chaganti",
        "description": "Pravachanam",
        "avg_rating": 4.5,
    }
    with patch("requests.get", return_value=_mock_response([doc])):
        results = svc.search(["Siva Tatvam Telugu audio"], lang="Telugu")
    assert len(results) == 1
    assert results[0]["audio_url"].startswith("https://archive.org/download/")
    assert results[0]["speaker"] == "Chaganti"


def test_empty_docs_returns_empty(svc):
    with patch("requests.get", return_value=_mock_response([])):
        assert svc.search(["nothing"], lang="Telugu") == []


def test_deduplicates_across_terms(svc):
    doc = {"identifier": "dup", "title": "T", "creator": "X", "description": ""}
    with patch("requests.get", return_value=_mock_response([doc])):
        results = svc.search(["term1", "term2"], lang="Telugu")
    assert len(results) == 1
