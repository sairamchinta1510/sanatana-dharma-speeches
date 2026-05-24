# UX & Search Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four approved UX and search quality improvements: scholar-targeted YouTube search, authentic Telugu vyakhanams with source links, video series grouping, and a working inline HTML5 audio player with sticky bar.

**Architecture:** Backend changes (Tasks 1–2) improve search result quality by targeting authenticated scholars and filtering by topic relevance. Frontend changes (Tasks 3–5) improve display and playback. Video series grouping is done on the frontend to avoid API contract changes. Deploy in two stages: backend first (Task 6), then frontend (Task 7).

**Tech Stack:** Python/FastAPI (backend), React Native Web / Expo (frontend), YouTube Data API v3, BeautifulSoup4, HTML5 Audio API, TypeScript

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/youtube_service.py` | Modify | Scholar-prefixed queries + title keyword filter |
| `backend/tests/test_youtube_service.py` | Modify | Update + add tests for new search behavior |
| `backend/services/scraper_service.py` | Modify | New Telugu sources, Telugu ratio filter, source_url |
| `backend/tests/test_scraper_service.py` | Modify | Update + add tests for new sources and filter |
| `mobile/components/VyakhanamsPanel.tsx` | Modify | Add "Read original →" link per entry |
| `mobile/api/client.ts` | Modify | Add `SeriesResult` type |
| `mobile/context/AppContext.tsx` | Modify | Add `currentAudio`, `audioQueue`, update `videos` type |
| `mobile/components/SeriesCard.tsx` | Create | Collapsible series card with horizontal episode strip |
| `mobile/components/VideoPlaylist.web.tsx` | Modify | Group results by speaker → `SeriesCard` or flat row |
| `mobile/components/AudioPlaylist.tsx` | Rewrite | HTML5 `<audio>` on web, progress bar, per-row play button |
| `mobile/components/StickyAudioBar.tsx` | Create | Sticky now-playing bar at bottom of page |
| `mobile/app/index.tsx` | Modify | Render `StickyAudioBar`, pass `audioListRef` |

---

## Task 1: Scholar-Targeted YouTube Search + Title Filter

**Files:**
- Modify: `backend/services/youtube_service.py`
- Modify: `backend/tests/test_youtube_service.py`

---

- [ ] **Step 1: Update existing tests to match new behavior**

The new `search()` runs one query per scholar (5 total) using `terms[0]` as the topic. Existing tests mock `mock_youtube_build.search().list().execute` — with 5 scholar queries the mock returns the same response for each call. Deduplication handles repeated video_ids. Tests for "filters to authentic channels" now rely on the title keyword filter rather than channel name.

Replace `backend/tests/test_youtube_service.py` with:

```python
import pytest
import os
from unittest.mock import MagicMock, patch, call

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


def test_uses_one_query_per_scholar(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([])
    svc.search(["Rama Nama"], lang="Telugu")
    assert mock_youtube_build.search().list().execute.call_count == len(SCHOLAR_QUERIES)


def test_scholar_queries_include_topic(svc, mock_youtube_build):
    captured_queries = []

    def capture(*args, **kwargs):
        captured_queries.append(kwargs.get("q", ""))
        m = MagicMock()
        m.execute.return_value = _make_yt_response([])
        return m

    mock_youtube_build.search().list.side_effect = capture
    svc.search(["Bhagavad Gita"], lang="Telugu")
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
```

- [ ] **Step 2: Run tests to verify they fail (new tests for scholar queries/title filter)**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
python -m pytest tests\test_youtube_service.py -v --tb=short
```

Expected: `test_uses_one_query_per_scholar`, `test_scholar_queries_include_topic`, `test_title_filter_removes_irrelevant_results`, `test_title_filter_falls_back_when_all_filtered` all FAIL because the new behavior doesn't exist yet.

- [ ] **Step 3: Rewrite `youtube_service.py` with scholar queries + title filter**

Replace `backend/services/youtube_service.py` with:

```python
import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {"Telugu": "te", "English": "en", "Sanskrit": "sa", "Hindi": "hi"}

SCHOLAR_QUERIES = [
    "Chaganti Koteswara Rao Telugu",
    "Garikipati Narasimha Rao Telugu",
    "Samavedam Shanmukha Sharma Telugu",
    "ISKCON Telugu pravachanam",
    "Bhakthi TV Telugu pravachanam",
]

_STOP_WORDS = {"the", "a", "an", "of", "in", "and", "or", "to", "for", "on", "by", "with", "at", "from", "is", "are", "was", "be"}


class YouTubeService:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable not set")
        self._yt = build("youtube", "v3", developerKey=api_key)

    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        if not terms:
            return []
        topic = terms[0]
        relevance_lang = LANG_CODE.get(lang, "te")
        seen: set[str] = set()
        results: list[dict] = []

        for suffix in SCHOLAR_QUERIES:
            query = f"{topic} {suffix}"
            try:
                resp = (
                    self._yt.search()
                    .list(
                        q=query,
                        part="snippet",
                        type="video",
                        maxResults=3,
                        relevanceLanguage=relevance_lang,
                    )
                    .execute()
                )
                for item in resp.get("items", []):
                    vid = item["id"]["videoId"]
                    if vid in seen:
                        continue
                    seen.add(vid)
                    s = item["snippet"]
                    results.append({
                        "video_id": vid,
                        "title": s["title"],
                        "speaker": s["channelTitle"],
                        "description": s.get("description", ""),
                        "thumbnail": s.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "lang": lang,
                    })
            except Exception as e:
                logger.error(f"YouTube search failed for query '{query}': {e}")

        return self._filter_by_topic(results, topic)

    def _extract_keywords(self, topic: str) -> list[str]:
        words = topic.lower().split()
        return [w.strip(".,!?()") for w in words
                if w.strip(".,!?()") not in _STOP_WORDS and len(w.strip(".,!?()")) > 1]

    def _filter_by_topic(self, results: list[dict], topic: str) -> list[dict]:
        keywords = self._extract_keywords(topic)
        if not keywords:
            return results
        threshold = max(1, len(keywords) // 3)

        def passes(r: dict) -> bool:
            text = (r.get("title", "") + " " + r.get("description", "")).lower()
            return sum(1 for kw in keywords if kw in text) >= threshold

        filtered = [r for r in results if passes(r)]
        return filtered if filtered else results
```

- [ ] **Step 4: Run tests — all pass**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
python -m pytest tests\test_youtube_service.py -v --tb=short
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add backend/services/youtube_service.py backend/tests/test_youtube_service.py
git commit -m "feat: scholar-targeted YouTube search with title keyword filter

- Run one query per authenticated scholar (5 scholars × topic)
- Filter results: at least ⅓ of topic keywords must appear in title/description
- Fallback to all results if filter is too strict
- Remove generic channel-name filter (scholar queries guarantee authenticity)"
```

---

## Task 2: Fix Scraper Service — Authentic Telugu Sources

**Files:**
- Modify: `backend/services/scraper_service.py`
- Modify: `backend/tests/test_scraper_service.py`

---

- [ ] **Step 1: Update tests to match new sources and Telugu ratio filter**

Replace `backend/tests/test_scraper_service.py` with:

```python
import pytest
from unittest.mock import patch, MagicMock
from services.scraper_service import ScraperService, _telugu_ratio


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
    mock_sleep.assert_called()


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
    # Results may be returned but text should not contain the English paragraph
    for r in results:
        assert "This is completely English" not in r.get("text", "")


def test_sources_are_authentic_telugu_sites(svc):
    from services.scraper_service import SOURCES
    affiliations = {s["affiliation"] for s in SOURCES}
    assert "chaganti.net" in affiliations
    assert "samavedam.org" in affiliations
    # speakingtree.in (English site) must be gone
    assert "speakingtree.in" not in affiliations
```

- [ ] **Step 2: Run tests to verify new tests fail**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
python -m pytest tests\test_scraper_service.py -v --tb=short
```

Expected: `test_telugu_ratio_*`, `test_sources_are_authentic_telugu_sites`, `test_english_only_paragraphs_filtered_out` FAIL.

- [ ] **Step 3: Rewrite `scraper_service.py` with correct sources and Telugu filter**

Replace `backend/services/scraper_service.py` with:

```python
import logging
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCES = [
    {
        "scholar": "Brahmasri Chaganti Koteswara Rao",
        "affiliation": "chaganti.net",
        "url_template": "https://www.chaganti.net/search?q={query}",
        "lang": "Telugu",
        "content_selector": ".search-result-text, article p, .entry-content p",
        "min_telugu_ratio": 0.3,
    },
    {
        "scholar": "Brahmasri Samavedam Shanmukha Sharma",
        "affiliation": "samavedam.org",
        "url_template": "https://www.samavedam.org/?s={query}",
        "lang": "Telugu",
        "content_selector": ".entry-content p, .post-content p",
        "min_telugu_ratio": 0.3,
    },
    {
        "scholar": "Sri Sri Tridandi Chinna Jeeyar Swami",
        "affiliation": "chinnajeeyar.org",
        "url_template": "https://www.chinnajeeyar.org/?s={query}",
        "lang": "Telugu",
        "content_selector": ".entry-content p, .post-body p",
        "min_telugu_ratio": 0.2,
    },
]

HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}


def _telugu_ratio(text: str) -> float:
    """Return the fraction of characters in text that are Telugu Unicode (U+0C00–U+0C7F)."""
    if not text:
        return 0.0
    telugu_chars = sum(1 for c in text if "\u0C00" <= c <= "\u0C7F")
    return telugu_chars / len(text)


class ScraperService:
    def scrape(self, query: str, lang: str, min_text_len: int = 80) -> list[dict]:
        results = []
        for source in SOURCES:
            time.sleep(1)
            url = source["url_template"].format(query=requests.utils.quote(query))
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [
                    p.get_text(strip=True)
                    for p in soup.select(source["content_selector"])
                    if len(p.get_text(strip=True)) > min_text_len
                    and _telugu_ratio(p.get_text(strip=True)) >= source["min_telugu_ratio"]
                ]
                if not paragraphs:
                    continue
                results.append({
                    "scholar": source["scholar"],
                    "affiliation": source["affiliation"],
                    "source_url": url,
                    "lang": source["lang"],
                    "text": " ".join(paragraphs[:3]),
                    "highlight": None,
                })
            except Exception as e:
                logger.error(f"Scrape failed for {source['scholar']}: {e}")
        return results
```

- [ ] **Step 4: Run all backend tests — all pass**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
python -m pytest tests\ -v --tb=short
```

Expected: All tests PASS. Note: `test_sources_list_contains_only_telugu_sources` was removed — it's been replaced by `test_sources_are_authentic_telugu_sites`.

- [ ] **Step 5: Commit**

```
git add backend/services/scraper_service.py backend/tests/test_scraper_service.py
git commit -m "feat: fix scraper sources to authentic Telugu scholar sites

- Replace speakingtree.in (English) with samavedam.org + chinnajeeyar.org
- Add _telugu_ratio() helper: filters out English/navigation paragraphs
- min_telugu_ratio 0.3 for chaganti/samavedam, 0.2 for chinnajeeyar
- source_url included in every result for 'Read original →' link"
```

---

## Task 3: Add Source Link to VyakhanamsPanel

**Files:**
- Modify: `mobile/components/VyakhanamsPanel.tsx`

---

- [ ] **Step 1: Add `Linking` import and "Read original →" button**

In `mobile/components/VyakhanamsPanel.tsx`, add `Linking` to the React Native imports and add a touchable link after the text:

```tsx
import React, { useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity,
  Modal, StyleSheet, SafeAreaView, Linking,
} from "react-native";
import { VyakhanamResult } from "../api/client";
import { COLORS, SCHOLAR_COLORS } from "../constants/theme";

interface Props { vyakhanams: VyakhanamResult[] }

export function VyakhanamsPanel({ vyakhanams }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (vyakhanams.length === 0) return null;

  const content = (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      {vyakhanams.map((v, i) => (
        <View key={v.scholar} style={[styles.entry,
          { borderLeftColor: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
          <View style={styles.header}>
            <Text style={[styles.scholar,
              { color: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
              {v.scholar}
            </Text>
            <View style={[styles.badge,
              { backgroundColor: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] + "22" }]}>
              <Text style={[styles.badgeText,
                { color: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
                {v.lang} • {v.affiliation}
              </Text>
            </View>
          </View>
          <Text style={styles.text}>{v.highlight ?? v.text}</Text>
          {v.source_url ? (
            <TouchableOpacity
              onPress={() => Linking.openURL(v.source_url)}
              style={styles.sourceLink}
            >
              <Text style={styles.sourceLinkText}>📖 Read original →</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );

  return (
    <View style={styles.container}>
      <View style={styles.sectionHeader}>
        <View style={styles.titleRow}>
          <Text style={styles.sectionTitle}>📖 వ్యాఖ్యానాలు — Vyakhanams</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{vyakhanams.length} scholars</Text>
          </View>
        </View>
        <TouchableOpacity onPress={() => setExpanded(true)}>
          <Text style={styles.expandText}>⤢ Expand</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.panel}>{content}</View>

      <Modal visible={expanded} animationType="slide" onRequestClose={() => setExpanded(false)}>
        <SafeAreaView style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>📖 Vyakhanams</Text>
            <TouchableOpacity onPress={() => setExpanded(false)}>
              <Text style={styles.closeText}>✕ Close</Text>
            </TouchableOpacity>
          </View>
          {content}
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginHorizontal: 16, marginBottom: 100 },
  sectionHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: 8,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { color: COLORS.text, fontSize: 13, fontWeight: "700" },
  countBadge: {
    backgroundColor: COLORS.goldDim, borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 2,
  },
  countText: { color: COLORS.gold, fontSize: 9 },
  expandText: { color: COLORS.textMuted, fontSize: 11 },
  panel: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderTopWidth: 2,
    borderColor: COLORS.border, borderTopColor: COLORS.gold + "66",
    maxHeight: 280, overflow: "hidden",
  },
  scroll: {},
  scrollContent: { padding: 12, gap: 12 },
  entry: { borderLeftWidth: 3, paddingLeft: 10 },
  header: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  scholar: { fontSize: 11, fontWeight: "700" },
  badge: { borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1 },
  badgeText: { fontSize: 8 },
  text: { color: COLORS.textMuted, fontSize: 11, lineHeight: 18 },
  sourceLink: { marginTop: 6 },
  sourceLinkText: { color: COLORS.gold, fontSize: 10, opacity: 0.85 },
  modal: { flex: 1, backgroundColor: COLORS.bg },
  modalHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  modalTitle: { color: COLORS.text, fontSize: 16, fontWeight: "700" },
  closeText: { color: COLORS.gold, fontSize: 13 },
});
```

- [ ] **Step 2: Verify build succeeds**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx expo export --platform web 2>&1 | tail -5
```

Expected: `Export was successful` with no TypeScript errors.

- [ ] **Step 3: Commit**

```
git add mobile/components/VyakhanamsPanel.tsx
git commit -m "feat: add 'Read original' source link to vyakhanams entries"
```

---

## Task 4: Video Series Grouping — SeriesCard + Updated VideoPlaylist

**Files:**
- Modify: `mobile/api/client.ts` (add `SeriesResult` type)
- Create: `mobile/components/SeriesCard.tsx`
- Modify: `mobile/components/VideoPlaylist.web.tsx`

Grouping is done on the frontend by grouping `VideoResult[]` by `speaker`. Groups of 3+ become `SeriesCard`; singletons/pairs remain flat rows. No backend API change.

---

- [ ] **Step 1: Add `SeriesResult` type to `client.ts`**

In `mobile/api/client.ts`, add after the `VideoResult` interface:

```ts
export interface SeriesEpisode {
  video_id: string;
  title: string;
  thumbnail: string;
}

export interface SeriesResult {
  type: "series";
  speaker: string;
  series_title: string;
  episode_count: number;
  episodes: SeriesEpisode[];
  lang: string;
}
```

Full updated `mobile/api/client.ts`:

```ts
const BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  (typeof window !== "undefined" && window.location?.hostname !== "localhost"
    ? "https://api.find.sanatanadharmas.com"
    : "http://localhost:8000");

export interface VideoResult {
  video_id: string;
  title: string;
  speaker: string;
  description: string;
  thumbnail: string;
  url: string;
  lang: string;
}

export interface SeriesEpisode {
  video_id: string;
  title: string;
  thumbnail: string;
}

export interface SeriesResult {
  type: "series";
  speaker: string;
  series_title: string;
  episode_count: number;
  episodes: SeriesEpisode[];
  lang: string;
}

export interface AudioResult {
  identifier: string;
  title: string;
  speaker: string;
  description: string;
  audio_url: string;
  page_url: string;
  lang: string;
}

export interface VyakhanamResult {
  scholar: string;
  affiliation: string;
  text: string;
  highlight: string | null;
  lang: string;
  source_url: string;
}

export interface SearchResponse<T> {
  results: T[];
  explanation: string | null;
  related_topics: string[];
  budget_warning: boolean;
  from_cache: boolean;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  searchVideos: (q: string, lang: string) =>
    apiFetch<SearchResponse<VideoResult>>(
      `/api/search?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}&type=video`
    ),
  searchAudio: (q: string, lang: string) =>
    apiFetch<SearchResponse<AudioResult>>(
      `/api/search?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}&type=audio`
    ),
  getVyakhanams: (q: string, lang: string) =>
    apiFetch<{ results: VyakhanamResult[]; from_cache: boolean }>(
      `/api/vyakhanams?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}`
    ),
};
```

- [ ] **Step 2: Create `SeriesCard.tsx`**

Create `mobile/components/SeriesCard.tsx`:

```tsx
import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
} from "react-native";
import { SeriesResult } from "../api/client";
import { COLORS } from "../constants/theme";

interface Props { series: SeriesResult }

export function SeriesCard({ series }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const playingEpisode = series.episodes.find((e) => e.video_id === activeId);

  return (
    <View style={styles.card}>
      {/* Series header */}
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.seriesTitle} numberOfLines={1}>{series.series_title}</Text>
          <Text style={styles.sub}>{series.speaker} • {series.episode_count} episodes</Text>
        </View>
        <View style={styles.badge}><Text style={styles.badgeText}>Series</Text></View>
      </View>

      {/* Inline player — shown when an episode is selected */}
      {activeId && (
        // @ts-ignore — iframe is not in RN types but works on web
        <iframe
          key={activeId}
          width="100%"
          height="200"
          src={`https://www.youtube.com/embed/${activeId}?autoplay=1`}
          allow="autoplay; encrypted-media"
          allowFullScreen
          style={{ border: "none", borderRadius: 0 } as React.CSSProperties}
        />
      )}

      {/* Episode strip */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.strip}
        contentContainerStyle={styles.stripContent}
      >
        {series.episodes.map((ep) => {
          const isActive = ep.video_id === activeId;
          return (
            <TouchableOpacity
              key={ep.video_id}
              style={[styles.chip, isActive && styles.chipActive]}
              onPress={() => setActiveId(isActive ? null : ep.video_id)}
            >
              <Text style={styles.chipPlay}>{isActive ? "⏸" : "▶"}</Text>
              <Text style={[styles.chipTitle, isActive && styles.chipTitleActive]} numberOfLines={2}>
                {ep.title}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Now playing label */}
      {playingEpisode && (
        <View style={styles.nowPlaying}>
          <Text style={styles.nowPlayingText} numberOfLines={1}>
            ▶ {playingEpisode.title}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    marginBottom: 6, overflow: "hidden",
  },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    padding: 10, gap: 8,
  },
  headerText: { flex: 1 },
  seriesTitle: { color: COLORS.text, fontSize: 12, fontWeight: "700" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  badge: {
    backgroundColor: COLORS.goldDim, borderRadius: 4,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { color: COLORS.gold, fontSize: 9, fontWeight: "600" },
  strip: { borderTopWidth: 1, borderTopColor: COLORS.border },
  stripContent: { padding: 8, gap: 6, flexDirection: "row" },
  chip: {
    backgroundColor: COLORS.bgLighter, borderRadius: 6,
    borderWidth: 1, borderColor: COLORS.border,
    padding: 6, maxWidth: 120, alignItems: "center", gap: 4,
  },
  chipActive: { borderColor: COLORS.gold + "88", backgroundColor: COLORS.bgLighter },
  chipPlay: { color: COLORS.textMuted, fontSize: 10 },
  chipTitle: { color: COLORS.textMuted, fontSize: 9, textAlign: "center" },
  chipTitleActive: { color: COLORS.gold },
  nowPlaying: {
    backgroundColor: COLORS.goldDim, borderTopWidth: 1,
    borderTopColor: COLORS.gold + "33", padding: 6,
  },
  nowPlayingText: { color: COLORS.gold, fontSize: 9, fontWeight: "600" },
});
```

- [ ] **Step 3: Rewrite `VideoPlaylist.web.tsx` to group by speaker**

Replace `mobile/components/VideoPlaylist.web.tsx` with:

```tsx
import React, { useState } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { VideoResult, SeriesResult } from "../api/client";
import { SeriesCard } from "./SeriesCard";
import { COLORS } from "../constants/theme";

interface Props { videos: VideoResult[] }

/** Group videos by speaker. Groups of 3+ → SeriesResult. Fewer → flat VideoResult rows. */
function groupVideos(videos: VideoResult[]): (VideoResult | SeriesResult)[] {
  const byChannel = new Map<string, VideoResult[]>();
  for (const v of videos) {
    const group = byChannel.get(v.speaker) ?? [];
    group.push(v);
    byChannel.set(v.speaker, group);
  }

  const items: (VideoResult | SeriesResult)[] = [];
  for (const [speaker, group] of byChannel) {
    if (group.length >= 3) {
      // Infer series title from common prefix of video titles
      const titles = group.map((v) => v.title);
      const firstWords = titles[0].split(" ").slice(0, 4).join(" ");
      const seriesTitle = firstWords || titles[0];

      items.push({
        type: "series",
        speaker,
        series_title: seriesTitle,
        episode_count: group.length,
        episodes: group.slice(0, 20).map((v) => ({
          video_id: v.video_id,
          title: v.title,
          thumbnail: v.thumbnail,
        })),
        lang: group[0].lang,
      });
    } else {
      items.push(...group);
    }
  }
  return items;
}

export function VideoPlaylist({ videos }: Props) {
  const [playingId, setPlayingId] = useState<string | null>(null);

  if (videos.length === 0) {
    return <Text style={styles.empty}>No videos found</Text>;
  }

  const items = groupVideos(videos);

  return (
    <FlatList
      data={items}
      keyExtractor={(item) =>
        "type" in item ? `series-${item.speaker}` : item.video_id
      }
      scrollEnabled={false}
      renderItem={({ item }) => {
        if ("type" in item) {
          return <SeriesCard series={item} />;
        }
        // Flat single-video row
        const active = playingId === item.video_id;
        return (
          <View style={[styles.row, active && styles.rowActive]}>
            {active && (
              // @ts-ignore
              <iframe
                width="100%"
                height="200"
                src={`https://www.youtube.com/embed/${item.video_id}?autoplay=1`}
                allow="autoplay; encrypted-media"
                allowFullScreen
                style={{ border: "none", borderRadius: 0 } as React.CSSProperties}
              />
            )}
            <TouchableOpacity style={styles.meta} onPress={() => setPlayingId(active ? null : item.video_id)}>
              <View style={styles.playBtn}>
                <Text style={styles.playIcon}>{active ? "⏸" : "▶"}</Text>
              </View>
              <View style={styles.info}>
                <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
                <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
              </View>
              {active && (
                <View style={styles.badge}><Text style={styles.badgeText}>Playing</Text></View>
              )}
            </TouchableOpacity>
          </View>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  empty: { color: COLORS.textMuted, textAlign: "center", padding: 16 },
  row: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    marginBottom: 6, overflow: "hidden",
  },
  rowActive: { borderColor: COLORS.gold + "88" },
  meta: { flexDirection: "row", alignItems: "center", padding: 10, gap: 10 },
  playBtn: {
    width: 36, height: 28, backgroundColor: COLORS.bgLighter,
    borderRadius: 4, alignItems: "center", justifyContent: "center",
  },
  playIcon: { color: COLORS.textMuted, fontSize: 12 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  badge: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: COLORS.gold + "44", borderRadius: 4,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { color: COLORS.gold, fontSize: 8 },
});
```

- [ ] **Step 4: Verify build**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx expo export --platform web 2>&1 | tail -5
```

Expected: `Export was successful` — no TypeScript errors.

- [ ] **Step 5: Commit**

```
git add mobile/api/client.ts mobile/components/SeriesCard.tsx mobile/components/VideoPlaylist.web.tsx
git commit -m "feat: group video results into series cards with episode strip

- Add SeriesResult + SeriesEpisode types to client.ts
- groupVideos() groups VideoResult[] by speaker: 3+ episodes → SeriesCard
- SeriesCard: collapsible series header, YouTube inline iframe, horizontal episode strip
- Single/pair videos remain as flat rows"
```

---

## Task 5: HTML5 Audio Player + Sticky Now-Playing Bar

**Files:**
- Modify: `mobile/context/AppContext.tsx` (add `currentAudio`, `audioQueue`)
- Rewrite: `mobile/components/AudioPlaylist.tsx` (HTML5 audio on web)
- Create: `mobile/components/StickyAudioBar.tsx`
- Modify: `mobile/app/index.tsx` (render `StickyAudioBar`)

---

- [ ] **Step 1: Update `AppContext.tsx` — add audio state**

Replace `mobile/context/AppContext.tsx` with:

```tsx
import React, { createContext, useContext, useState, useCallback, useRef } from "react";
import { api, VideoResult, AudioResult, VyakhanamResult } from "../api/client";

export type Language = "Telugu" | "English" | "Sanskrit" | "Hindi";
export type PlayerItem =
  | { type: "video"; item: VideoResult }
  | { type: "audio"; item: AudioResult };

interface AppState {
  query: string;
  language: Language;
  videos: VideoResult[];
  audio: AudioResult[];
  vyakhanams: VyakhanamResult[];
  explanation: string | null;
  relatedTopics: string[];
  loading: boolean;
  budgetWarning: boolean;
  searchError: string | null;
  currentPlayer: PlayerItem | null;
  currentAudio: AudioResult | null;
  audioQueue: AudioResult[];
  audioListRef: React.MutableRefObject<{ scrollToTop: () => void } | null>;
  setQuery: (q: string) => void;
  setLanguage: (l: Language) => void;
  search: (q: string) => Promise<void>;
  setCurrentPlayer: (item: PlayerItem | null) => void;
  setCurrentAudio: (item: AudioResult | null) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<Language>("Telugu");
  const [videos, setVideos] = useState<VideoResult[]>([]);
  const [audio, setAudio] = useState<AudioResult[]>([]);
  const [vyakhanams, setVyakhanams] = useState<VyakhanamResult[]>([]);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [relatedTopics, setRelatedTopics] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [budgetWarning, setBudgetWarning] = useState(false);
  const [currentPlayer, setCurrentPlayer] = useState<PlayerItem | null>(null);
  const [currentAudio, setCurrentAudio] = useState<AudioResult | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const audioListRef = useRef<{ scrollToTop: () => void } | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearchError(null);
    try {
      const [videoRes, audioRes, vyakhanamRes] = await Promise.all([
        api.searchVideos(q, language),
        api.searchAudio(q, language),
        api.getVyakhanams(q, "Telugu"),
      ]);
      setVideos(videoRes.results);
      setAudio(audioRes.results);
      setVyakhanams(vyakhanamRes.results);
      setExplanation(videoRes.explanation ?? null);
      setRelatedTopics(videoRes.related_topics ?? []);
      setBudgetWarning(videoRes.budget_warning || audioRes.budget_warning);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("Search failed:", msg);
      setSearchError(msg);
    } finally {
      setLoading(false);
    }
  }, [language]);

  return (
    <AppContext.Provider value={{
      query, language, videos, audio, vyakhanams,
      explanation, relatedTopics,
      loading, budgetWarning, searchError, currentPlayer,
      currentAudio, audioQueue: audio, audioListRef,
      setQuery, setLanguage, search, setCurrentPlayer, setCurrentAudio,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
```

- [ ] **Step 2: Rewrite `AudioPlaylist.tsx` with HTML5 audio**

Replace `mobile/components/AudioPlaylist.tsx` with:

```tsx
import React, { useState, useRef, useEffect } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, Platform,
} from "react-native";
import { AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

interface Props { audio: AudioResult[] }

/** Formatted mm:ss from seconds */
function fmtTime(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function AudioRow({ item, isActive, onPlay }: {
  item: AudioResult;
  isActive: boolean;
  onPlay: (item: AudioResult, el: HTMLAudioElement) => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (isActive) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [isActive]);

  const handleTimeUpdate = (e: React.SyntheticEvent<HTMLAudioElement>) => {
    const el = e.currentTarget;
    setCurrentTime(el.currentTime);
    setDuration(el.duration || 0);
    setProgress(el.duration ? (el.currentTime / el.duration) * 100 : 0);
  };

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLAudioElement>) => {
    setDuration(e.currentTarget.duration || 0);
  };

  const handleClick = () => {
    if (audioRef.current) {
      onPlay(item, audioRef.current);
    }
  };

  if (Platform.OS !== "web") {
    // Native stub — audio only works on web
    return (
      <View style={styles.row}>
        <View style={styles.iconBox}><Text style={styles.icon}>🎵</Text></View>
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.row, isActive && styles.rowActive]}>
      {/* Hidden HTML5 audio element */}
      {/* @ts-ignore */}
      <audio
        ref={audioRef}
        src={item.audio_url}
        preload="none"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        style={{ display: "none" }}
      />

      <TouchableOpacity style={[styles.iconBox, isActive && styles.iconBoxActive]} onPress={handleClick}>
        <Text style={styles.icon}>{isActive ? "⏸" : "▶"}</Text>
      </TouchableOpacity>

      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
        {isActive && (
          <View style={styles.progressRow}>
            <View style={styles.progressBg}>
              <View style={[styles.progressFill, { width: `${progress}%` as any }]} />
            </View>
            <Text style={styles.timeText}>{fmtTime(currentTime)} / {fmtTime(duration)}</Text>
          </View>
        )}
      </View>
    </View>
  );
}

export function AudioPlaylist({ audio }: Props) {
  const { setCurrentAudio } = useApp();
  const [playingId, setPlayingId] = useState<string | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);

  const play = (item: AudioResult, el: HTMLAudioElement) => {
    if (playingId === item.identifier) {
      // Toggle pause
      el.paused ? el.play() : el.pause();
      if (!el.paused) {
        setCurrentAudio(item);
      } else {
        setCurrentAudio(null);
        setPlayingId(null);
      }
      return;
    }
    // Stop previous
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current.currentTime = 0;
    }
    activeAudioRef.current = el;
    setPlayingId(item.identifier);
    setCurrentAudio(item);
  };

  if (audio.length === 0) {
    return <Text style={styles.empty}>No audio found</Text>;
  }

  return (
    <FlatList
      data={audio}
      keyExtractor={(item) => item.identifier}
      scrollEnabled={false}
      renderItem={({ item }) => (
        <AudioRow
          item={item}
          isActive={playingId === item.identifier}
          onPlay={play}
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { color: COLORS.textMuted, textAlign: "center", padding: 16 },
  row: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    flexDirection: "row", alignItems: "flex-start",
    padding: 10, marginBottom: 6, gap: 10,
  },
  rowActive: { borderColor: COLORS.gold + "88", backgroundColor: COLORS.bgLighter },
  iconBox: {
    width: 36, height: 28, borderRadius: 4,
    backgroundColor: COLORS.bgLighter,
    alignItems: "center", justifyContent: "center",
  },
  iconBoxActive: { backgroundColor: COLORS.gold },
  icon: { fontSize: 12 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  progressRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 6 },
  progressBg: {
    flex: 1, height: 3, backgroundColor: COLORS.border, borderRadius: 2,
    overflow: "hidden",
  },
  progressFill: { height: 3, backgroundColor: COLORS.gold, borderRadius: 2 },
  timeText: { color: COLORS.textMuted, fontSize: 9, minWidth: 70 },
});
```

- [ ] **Step 3: Create `StickyAudioBar.tsx`**

Create `mobile/components/StickyAudioBar.tsx`:

```tsx
import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, Platform } from "react-native";
import { useApp } from "../context/AppContext";
import { COLORS } from "../constants/theme";
import { AudioResult } from "../api/client";

export function StickyAudioBar() {
  const { currentAudio, audioQueue, setCurrentAudio } = useApp();

  if (!currentAudio || Platform.OS !== "web") return null;

  const currentIndex = audioQueue.findIndex((a) => a.identifier === currentAudio.identifier);
  const nextTrack = currentIndex >= 0 && currentIndex < audioQueue.length - 1
    ? audioQueue[currentIndex + 1]
    : null;

  const handleNext = () => {
    if (!nextTrack) return;
    // Find and trigger the next audio element
    if (typeof document !== "undefined") {
      const currentEl = document.querySelector(`audio[src="${currentAudio.audio_url}"]`) as HTMLAudioElement | null;
      if (currentEl) {
        currentEl.pause();
        currentEl.currentTime = 0;
      }
      const nextEl = document.querySelector(`audio[src="${nextTrack.audio_url}"]`) as HTMLAudioElement | null;
      if (nextEl) nextEl.play().catch(() => {});
    }
    setCurrentAudio(nextTrack);
  };

  return (
    <View style={styles.bar}>
      <View style={styles.info}>
        <Text style={styles.label}>▶ NOW PLAYING</Text>
        <Text style={styles.title} numberOfLines={1}>{currentAudio.title}</Text>
        <Text style={styles.sub}>{currentAudio.speaker}</Text>
      </View>
      {nextTrack && (
        <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
          <Text style={styles.nextText}>⏭ Next</Text>
        </TouchableOpacity>
      )}
      <TouchableOpacity style={styles.closeBtn} onPress={() => {
        if (typeof document !== "undefined") {
          const el = document.querySelector(`audio[src="${currentAudio.audio_url}"]`) as HTMLAudioElement | null;
          if (el) { el.pause(); el.currentTime = 0; }
        }
        setCurrentAudio(null);
      }}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: "absolute" as any,
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: COLORS.bgLighter,
    borderTopWidth: 1,
    borderTopColor: COLORS.gold + "44",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
  },
  info: { flex: 1 },
  label: { color: COLORS.gold, fontSize: 8, letterSpacing: 1, fontWeight: "700", opacity: 0.8 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600", marginTop: 2 },
  sub: { color: COLORS.textMuted, fontSize: 10 },
  nextBtn: {
    backgroundColor: COLORS.bgLight, borderRadius: 4,
    borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 8, paddingVertical: 4,
  },
  nextText: { color: COLORS.textMuted, fontSize: 11 },
  closeBtn: { padding: 4 },
  closeText: { color: COLORS.textMuted, fontSize: 14 },
});
```

- [ ] **Step 4: Add `StickyAudioBar` to `index.tsx`**

In `mobile/app/index.tsx`, add the `StickyAudioBar` import and render it. The outer `ScrollView` must be wrapped in a `View` with `style={{ flex: 1 }}` so the bar anchors to the bottom.

Replace `mobile/app/index.tsx` with:

```tsx
import React, { useState } from "react";
import {
  View, ScrollView, Text, TouchableOpacity, StyleSheet,
} from "react-native";
import { useApp } from "../context/AppContext";
import { SearchBar } from "../components/SearchBar";
import { LanguageFilter } from "../components/LanguageFilter";
import { VideoPlaylist } from "../components/VideoPlaylist";
import { AudioPlaylist } from "../components/AudioPlaylist";
import { VyakhanamsPanel } from "../components/VyakhanamsPanel";
import { StickyAudioBar } from "../components/StickyAudioBar";
import { COLORS } from "../constants/theme";
import { ExplanationPanel } from "../components/ExplanationPanel";

type ResultTab = "video" | "audio";

export default function HomeScreen() {
  const { videos, audio, vyakhanams, loading, budgetWarning, searchError,
          explanation, relatedTopics, language, setLanguage, search } =
    useApp();
  const [tab, setTab] = useState<ResultTab>("video");
  const hasResults = videos.length > 0 || audio.length > 0;

  return (
    <View style={styles.wrapper}>
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <Text style={styles.subtitle}>EXPLORE DHARMIC KNOWLEDGE</Text>
          <SearchBar onSearch={search} loading={loading} />
          <LanguageFilter selected={language} onSelect={setLanguage} />
        </View>

        {searchError && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>⚠️ Search error: {searchError}</Text>
          </View>
        )}

        {budgetWarning && (
          <View style={styles.warningBanner}>
            <Text style={styles.warningText}>
              ⚠️ Enhanced search paused — results shown as-is
            </Text>
          </View>
        )}

        <ExplanationPanel
          explanation={explanation}
          relatedTopics={relatedTopics}
          onTopicPress={search}
        />

        {hasResults && (
          <>
            <View style={styles.sectionBox}>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionLabel}>🎬 Videos &amp; Audio</Text>
                <View style={styles.tabs}>
                  <TouchableOpacity
                    style={[styles.tab, tab === "video" && styles.tabActive]}
                    onPress={() => setTab("video")}
                  >
                    <Text style={[styles.tabText, tab === "video" && styles.tabTextActive]}>
                      ▶ Videos ({videos.length})
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.tab, tab === "audio" && styles.tabActive]}
                    onPress={() => setTab("audio")}
                  >
                    <Text style={[styles.tabText, tab === "audio" && styles.tabTextActive]}>
                      🎵 Audio ({audio.length})
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
              <View style={styles.playlistArea}>
                {tab === "video" ? (
                  <VideoPlaylist videos={videos} />
                ) : (
                  <AudioPlaylist audio={audio} />
                )}
              </View>
            </View>

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerSymbol}>✦ ✦ ✦</Text>
              <View style={styles.dividerLine} />
            </View>

            <VyakhanamsPanel vyakhanams={vyakhanams} />
          </>
        )}
      </ScrollView>
      <StickyAudioBar />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: COLORS.bg },
  screen: { flex: 1 },
  content: { paddingBottom: 120 },
  hero: { paddingTop: 16 },
  subtitle: {
    textAlign: "center", color: COLORS.gold, fontSize: 10,
    letterSpacing: 2, opacity: 0.7, marginBottom: 8,
  },
  errorBanner: {
    marginHorizontal: 16, marginBottom: 8,
    backgroundColor: "#4a000022",
    borderWidth: 1, borderColor: "#cc4444",
    borderRadius: 8, padding: 8,
  },
  errorText: { color: "#ff6666", fontSize: 11, textAlign: "center" },
  warningBanner: {
    marginHorizontal: 16, marginBottom: 8,
    backgroundColor: "#7d4e0022",
    borderWidth: 1, borderColor: "#7d4e00",
    borderRadius: 8, padding: 8,
  },
  warningText: { color: "#f0a050", fontSize: 11, textAlign: "center" },
  sectionBox: {
    marginHorizontal: 16, backgroundColor: COLORS.bgLight,
    borderRadius: 8, borderWidth: 1, borderColor: COLORS.border,
    overflow: "hidden", marginBottom: 4,
  },
  sectionHeader: {
    backgroundColor: COLORS.bgLighter, paddingHorizontal: 14, paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
  },
  sectionLabel: { color: COLORS.text, fontSize: 12, fontWeight: "700" },
  tabs: { flexDirection: "row" },
  tab: { paddingHorizontal: 10, paddingVertical: 4 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.gold },
  tabText: { color: COLORS.textMuted, fontSize: 11 },
  tabTextActive: { color: COLORS.gold, fontWeight: "600" },
  playlistArea: { padding: 10 },
  divider: {
    flexDirection: "row", alignItems: "center",
    marginHorizontal: 16, marginVertical: 12,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: COLORS.gold + "22" },
  dividerSymbol: { color: COLORS.gold + "55", fontSize: 12, marginHorizontal: 10 },
});
```

- [ ] **Step 5: Verify build**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx expo export --platform web 2>&1 | tail -5
```

Expected: `Export was successful` — no TypeScript errors.

- [ ] **Step 6: Commit**

```
git add mobile/context/AppContext.tsx mobile/components/AudioPlaylist.tsx mobile/components/StickyAudioBar.tsx mobile/app/index.tsx
git commit -m "feat: HTML5 inline audio player with sticky now-playing bar

- AudioPlaylist: replace expo-av with HTML5 <audio> element (web-only)
- Per-row play/pause button + progress bar + elapsed/duration timer
- StickyAudioBar: persistent now-playing strip at page bottom, ⏭ next-track
- AppContext: add currentAudio + audioQueue state
- index.tsx: wrap in View, render StickyAudioBar below ScrollView"
```

---

## Task 6: Deploy Backend Changes

**Files:** EC2 instance `i-0dae33738624b349b`

---

- [ ] **Step 1: Push to GitHub**

```
git push origin master
```

- [ ] **Step 2: Deploy to EC2 via SSM**

```
aws ssm send-command \
  --instance-ids i-0dae33738624b349b \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["export HOME=/root","cd /home/ubuntu/SanatanaDharmaSpeeches","git pull origin master","sudo systemctl restart dharma-api"]}' \
  --output text --query "Command.CommandId"
```

- [ ] **Step 3: Verify API is healthy**

```
curl https://api.find.sanatanadharmas.com/health
```

Expected: `{"status":"ok"}` or similar.

- [ ] **Step 4: Smoke test YouTube search**

```
curl "https://api.find.sanatanadharmas.com/api/search?q=Bhagavad+Gita+Chapter+2&lang=Telugu&type=video"
```

Expected: JSON with `results` array containing videos from authenticated channels (Chaganti, Garikipati, ISKCON, etc.), all with "Bhagavad" or "Gita" in titles.

---

## Task 7: Deploy Frontend Changes

---

- [ ] **Step 1: Build web bundle**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx expo export --platform web
```

Expected: `Export was successful`. Bundle written to `dist/`.

- [ ] **Step 2: Sync to S3**

```
aws s3 sync dist/ s3://find.sanatanadharmas.com/ --delete
```

Expected: Files uploaded, old files deleted.

- [ ] **Step 3: Invalidate CloudFront**

```
aws cloudfront create-invalidation --distribution-id E1VGFNYVAOH3JE --paths "/*"
```

Expected: Invalidation ID returned.

- [ ] **Step 4: Smoke test live site**

Open https://find.sanatanadharmas.com — search "Bhagavad Gita Chapter 2" and verify:
- Videos tab: series from same speaker grouped into a SeriesCard with episode strip
- Audio tab: play button works, progress bar appears, sticky bar shows at bottom
- Vyakhanams section: Telugu text appears with "📖 Read original →" link per entry

---

## Self-Review

**Spec coverage check:**
- ✅ Issue 1 (video series): Task 4 — `SeriesCard`, `VideoPlaylist.web.tsx`, grouping logic
- ✅ Issue 2 (audio player): Task 5 — HTML5 audio, progress bar, `StickyAudioBar`
- ✅ Issue 3 (vyakhanams): Task 2 (new sources + Telugu filter) + Task 3 (source link)
- ✅ Issue 4 (search specificity): Task 1 — scholar-prefixed queries + title filter

**Type consistency check:**
- `SeriesResult` defined in Task 4 Step 1 (`client.ts`), used in `SeriesCard` (Task 4 Step 2) and `VideoPlaylist.web.tsx` (Task 4 Step 3) ✅
- `currentAudio: AudioResult | null` added in `AppContext` (Task 5 Step 1), used in `AudioPlaylist` and `StickyAudioBar` ✅
- `audioQueue: AudioResult[]` = `audio` array from state — `StickyAudioBar` uses it for next-track ✅
- `SCHOLAR_QUERIES` exported from `youtube_service.py` (Task 1 Step 3), imported in test (Task 1 Step 1) ✅

**No placeholders:** All steps contain complete code. ✅
