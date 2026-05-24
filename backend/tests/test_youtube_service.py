import pytest
import os
from unittest.mock import MagicMock

os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

from services.youtube_service import YouTubeService, SCHOLAR_QUERIES


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


def _make_item(video_id, title, channel, description=""):
    return {
        "id": {"videoId": video_id},
        "snippet": {
            "title": title,
            "channelTitle": channel,
            "description": description,
            "thumbnails": {"medium": {"url": f"http://img/{video_id}.jpg"}},
        },
    }


def test_search_returns_normalized_results(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        _make_item("abc123", "Siva Tatvam Telugu", "Chaganti Official"),
    ])
    results = svc.search(["Siva Tatvam"], lang="Telugu")
    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"
    assert results[0]["speaker"] == "Chaganti Official"
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


def test_deduplicates_across_scholar_queries(svc, mock_youtube_build):
    # Same video returned by every scholar query — should deduplicate to 1
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        _make_item("dup123", "Bhagavad Gita disc", "SomeChannel"),
    ])
    results = svc.search(["Bhagavad Gita"], lang="Telugu")
    ids = [r["video_id"] for r in results]
    assert ids.count("dup123") == 1


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
        YouTubeService()


def test_uses_one_query_per_scholar_plus_baseline(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([])
    svc.search(["Rama Nama"], lang="Telugu")
    # 5 scholar queries + 1 baseline = 6 total for a single term
    assert mock_youtube_build.search().list().execute.call_count == len(SCHOLAR_QUERIES) + 1


def test_scholar_queries_include_topic(svc, mock_youtube_build):
    captured_queries = []

    def capture(*args, **kwargs):
        captured_queries.append(kwargs.get("q", ""))
        m = MagicMock()
        m.execute.return_value = _make_yt_response([])
        return m

    mock_youtube_build.search().list.side_effect = capture
    svc.search(["Bhagavad Gita"], lang="Telugu")
    # 5 scholar + 1 baseline
    assert len(captured_queries) == len(SCHOLAR_QUERIES) + 1
    for q in captured_queries:
        assert "Bhagavad Gita" in q


def test_title_filter_removes_irrelevant_results(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        _make_item("v1", "Bhagavad Gita Chapter 2", "Chaganti"),
        _make_item("v2", "Random cooking video", "FoodChannel"),
    ])
    results = svc.search(["Bhagavad Gita"], lang="Telugu")
    titles = [r["title"] for r in results]
    assert "Bhagavad Gita Chapter 2" in titles
    assert "Random cooking video" not in titles


def test_title_filter_falls_back_when_all_filtered(svc, mock_youtube_build):
    # If ALL results fail the keyword filter, return all (rather than empty)
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        _make_item("v1", "Niche discourse", "ObscureChannel"),
    ])
    results = svc.search(["xyzzy unique nonce"], lang="Telugu")
    assert len(results) == 1


def test_search_empty_terms_returns_empty(svc, mock_youtube_build):
    results = svc.search([], lang="Telugu")
    assert results == []
    mock_youtube_build.search().list().execute.assert_not_called()


def test_uses_second_term_when_provided(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([])
    svc.search(["Bhagavad Gita", "Karma Yoga Telugu"], lang="Telugu")
    # 5 scholars × 2 terms + 1 baseline = 11
    assert mock_youtube_build.search().list().execute.call_count == 2 * len(SCHOLAR_QUERIES) + 1


def test_baseline_query_does_not_use_scholar_suffix(svc, mock_youtube_build):
    captured_queries = []

    def capture(*args, **kwargs):
        captured_queries.append(kwargs.get("q", ""))
        m = MagicMock()
        m.execute.return_value = _make_yt_response([])
        return m

    mock_youtube_build.search().list.side_effect = capture
    svc.search(["Siva Tatvam"], lang="Telugu")
    # Last query should be the baseline (no scholar suffix like "Chaganti" etc.)
    baseline_q = captured_queries[-1]
    assert "Telugu pravachanam" in baseline_q
    # Should NOT contain a scholar name suffix
    scholar_names = ["Chaganti", "Garikipati", "Samavedam", "ISKCON", "Bhakthi TV"]
    assert not any(name in baseline_q for name in scholar_names)
