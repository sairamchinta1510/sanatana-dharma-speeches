import pytest
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

from services.youtube_service import YouTubeService


@pytest.fixture
def mock_youtube_build(monkeypatch):
    mock_service = MagicMock()
    monkeypatch.setattr("services.youtube_service.build", lambda *a, **kw: mock_service)
    return mock_service


@pytest.fixture
def svc(mock_youtube_build):
    return YouTubeService()


def _make_yt_response(items):
    return {"items": items}


def test_search_returns_normalized_results(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "Siva Tatvam Telugu",
                "channelTitle": "Chaganti Official",
                "description": "Full discourse",
                "thumbnails": {"medium": {"url": "http://img.jpg"}},
            }
        }
    ])
    results = svc.search(["Siva Tatvam Telugu"], lang="Telugu", max_results=5)
    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"
    assert results[0]["speaker"] == "Chaganti Official"
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


def test_deduplicates_across_terms(svc, mock_youtube_build):
    item = {
        "id": {"videoId": "dup123"},
        "snippet": {"title": "Test", "channelTitle": "X",
                    "description": "", "thumbnails": {"medium": {"url": ""}}}
    }
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([item])
    results = svc.search(["term1", "term2"], lang="Telugu", max_results=10)
    ids = [r["video_id"] for r in results]
    assert ids.count("dup123") == 1


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
        YouTubeService()
