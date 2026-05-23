# LLM Search, Authentic Scholars, Multiline Search, Telugu Vyakhanams — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered topic explanation, filter YouTube results to authentic scholars only, replace the search bar with a large multiline textarea, and lock Vyakhanams to Telugu-only.

**Architecture:** Four focused, independent changes — two backend (youtube_service allowlist + llm_service explain_topic + scraper/vyakhanams Telugu lock), two frontend (SearchBar multiline + new ExplanationPanel). Backend changes are deployed to EC2 via git pull + systemd restart. Frontend changes are rebuilt with `npx expo export --platform web` and deployed to S3/CloudFront.

**Tech Stack:** Python/FastAPI (backend), React Native/Expo (frontend), AWS Bedrock Claude Haiku (LLM explanation), YouTube Data API v3, S3/CloudFront (hosting)

---

## File Map

| File | What changes |
|------|-------------|
| `backend/services/youtube_service.py` | Add `AUTHENTIC_CHANNELS` set; post-filter results after dedup; fallback to unfiltered if empty |
| `backend/services/llm_service.py` | Add `explain_topic(parsed) -> dict \| None` method using Claude Haiku |
| `backend/services/scraper_service.py` | Remove English sources; Telugu-only SOURCES list |
| `backend/routers/search.py` | Call `explain_topic`; include `explanation` + `related_topics` in response |
| `backend/routers/vyakhanams.py` | Ignore `lang` param; always use `lang="Telugu"` |
| `backend/tests/test_youtube_service.py` | Add 2 tests for allowlist filter + fallback |
| `backend/tests/test_llm_service.py` | Add 1 test for `explain_topic` |
| `backend/tests/test_search_router.py` | Add 1 test asserting `explanation` in response |
| `mobile/components/SearchBar.tsx` | Replace single-line TextInput with multiline textarea + full-width Search button |
| `mobile/components/ExplanationPanel.tsx` | New component: explanation text + related topic chips |
| `mobile/context/AppContext.tsx` | Add `explanation: string \| null` + `relatedTopics: string[]` state |
| `mobile/api/client.ts` | Add `explanation` + `related_topics` to `SearchResponse<T>` |
| `mobile/app/index.tsx` | Render `ExplanationPanel`; pass `lang="Telugu"` to `getVyakhanams` |

---

## Task 1: Authentic Scholars Allowlist in YouTubeService

**Files:**
- Modify: `backend/services/youtube_service.py`
- Test: `backend/tests/test_youtube_service.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_youtube_service.py`:

```python
def test_filters_to_authentic_channels(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        {
            "id": {"videoId": "vid1"},
            "snippet": {"title": "Siva Tatvam", "channelTitle": "Chaganti Official",
                        "description": "", "thumbnails": {"medium": {"url": ""}}}
        },
        {
            "id": {"videoId": "vid2"},
            "snippet": {"title": "Random video", "channelTitle": "SomeRandomChannel",
                        "description": "", "thumbnails": {"medium": {"url": ""}}}
        },
    ])
    results = svc.search(["Siva Tatvam Telugu"], lang="Telugu", max_results=5)
    speakers = [r["speaker"] for r in results]
    assert "Chaganti Official" in speakers
    assert "SomeRandomChannel" not in speakers


def test_falls_back_to_all_if_no_authentic_match(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        {
            "id": {"videoId": "vid3"},
            "snippet": {"title": "Niche topic", "channelTitle": "ObscureChannel",
                        "description": "", "thumbnails": {"medium": {"url": ""}}}
        },
    ])
    results = svc.search(["very niche query"], lang="Telugu", max_results=5)
    # fallback: should still return the result
    assert len(results) == 1
    assert results[0]["speaker"] == "ObscureChannel"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
.venv\Scripts\Activate.ps1
python -m pytest tests/test_youtube_service.py::test_filters_to_authentic_channels tests/test_youtube_service.py::test_falls_back_to_all_if_no_authentic_match -v
```

Expected: FAIL — `test_filters_to_authentic_channels` fails because filtering doesn't exist yet.

- [ ] **Step 3: Implement allowlist in `youtube_service.py`**

Replace the full file content:

```python
import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {"Telugu": "te", "English": "en", "Sanskrit": "sa", "Hindi": "hi"}

# Lowercase substrings matched against channelTitle. Add more as needed.
AUTHENTIC_CHANNELS = {
    "chaganti",
    "garikapati",
    "garikipati",
    "samavedam",
    "jeeyar",
    "chinnajeeyar",
    "bhakthi tv",
    "telugupuranam",
    "suman tv",
    "sumantvvijayawada",
    "iskcon",
    "tridandi",
    "pravachanam",
    "dharmasandehalu",
    "brahmasri",
}


def _is_authentic(channel_title: str) -> bool:
    lower = channel_title.lower()
    return any(keyword in lower for keyword in AUTHENTIC_CHANNELS)


class YouTubeService:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable not set")
        self._yt = build("youtube", "v3", developerKey=api_key)

    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        seen = set()
        results = []
        relevance_lang = LANG_CODE.get(lang, "te")
        for term in terms:
            try:
                resp = (
                    self._yt.search()
                    .list(
                        q=term,
                        part="snippet",
                        type="video",
                        maxResults=max_results,
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
                logger.error(f"YouTube search failed for term '{term}': {e}")

        authentic = [r for r in results if _is_authentic(r["speaker"])]
        return authentic if authentic else results
```

- [ ] **Step 4: Run all YouTube tests**

```
python -m pytest tests/test_youtube_service.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add backend/services/youtube_service.py backend/tests/test_youtube_service.py
git commit -m "feat: filter YouTube results to authentic Dharma scholars only"
```

---

## Task 2: LLM `explain_topic` Method

**Files:**
- Modify: `backend/services/llm_service.py`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_llm_service.py`:

```python
def test_explain_topic_returns_explanation_and_related(llm, mock_bedrock):
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=["శివ తత్వం", "Shiva Tattva"],
        language="Telugu", search_intent="conceptual discourse"
    )
    mock_bedrock.invoke_model.return_value = _haiku_response(json.dumps({
        "explanation": "Siva Tatvam describes the ultimate nature of Lord Shiva as the formless Absolute.",
        "related_topics": ["Panchakshara Mantra", "Rudra Abhishekam", "Shiva Purana"]
    }))
    result = llm.explain_topic(parsed)
    assert result is not None
    assert "Siva Tatvam" in result["explanation"] or len(result["explanation"]) > 10
    assert len(result["related_topics"]) == 3


def test_explain_topic_returns_none_on_budget_exceeded():
    import database; database.init_db()
    with database.db() as conn:
        conn.execute("DELETE FROM llm_cost_log")
    from services.cost_tracking_service import CostTrackingService
    tracker = CostTrackingService(daily_limit_usd=0.0)
    llm_exceeded = LLMService(tracker=tracker)
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=[], language="Telugu", search_intent="general"
    )
    assert llm_exceeded.explain_topic(parsed) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_llm_service.py::test_explain_topic_returns_explanation_and_related tests/test_llm_service.py::test_explain_topic_returns_none_on_budget_exceeded -v
```

Expected: FAIL — `AttributeError: 'LLMService' object has no attribute 'explain_topic'`

- [ ] **Step 3: Add `explain_topic` to `LLMService`**

Add after the `highlight_vyakhanams` method in `backend/services/llm_service.py`:

```python
    def explain_topic(self, parsed: "ParsedQuery") -> "dict | None":
        if self.tracker.is_budget_exceeded():
            logger.warning("LLM budget exceeded — skipping explain_topic")
            return None
        prompt = (
            f"You are a Sanatan Dharma scholar. "
            f"Explain the topic \"{parsed.topic}\" in 2-3 clear sentences suitable for a devotee. "
            f"Then suggest exactly 3 related topics they might want to explore next.\n\n"
            f"Return ONLY valid JSON with keys: explanation (string), related_topics (array of 3 strings).\n"
            f'Example: {{"explanation": "Siva Tatvam refers to...", "related_topics": ["Panchakshara", "Rudram", "Shiva Purana"]}}'
        )
        try:
            text = self._call_haiku(prompt)
            data = self._parse_json(text)
            return {
                "explanation": data.get("explanation", ""),
                "related_topics": data.get("related_topics", []),
            }
        except Exception as e:
            logger.error(f"explain_topic failed: {e}")
            return None
```

- [ ] **Step 4: Run all LLM tests**

```
python -m pytest tests/test_llm_service.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add backend/services/llm_service.py backend/tests/test_llm_service.py
git commit -m "feat: add explain_topic to LLMService (Haiku-powered topic explanation)"
```

---

## Task 3: Wire `explain_topic` into Search Router

**Files:**
- Modify: `backend/routers/search.py`
- Test: `backend/tests/test_search_router.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_search_router.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_search_router.py::test_search_includes_explanation -v
```

Expected: FAIL — `KeyError: 'explanation'`

- [ ] **Step 3: Update `search.py` to call `explain_topic` and include in response**

Replace `backend/routers/search.py` with:

```python
import os
import logging
from fastapi import APIRouter, Query, HTTPException
from services.llm_service import LLMService
from services.youtube_service import YouTubeService
from services.archive_service import ArchiveService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
yt_svc = YouTubeService()
archive_svc = ArchiveService()
cache_svc = CacheService()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),
    type: str = Query("video"),
):
    if type not in ("video", "audio"):
        raise HTTPException(status_code=400, detail="type must be 'video' or 'audio'")

    cached = cache_svc.get(type, q, lang)
    if cached is not None:
        # Explanation cached separately
        explanation_cache = cache_svc.get(f"{type}_explanation", q, lang)
        exp = explanation_cache[0] if explanation_cache else None
        return {
            "results": cached,
            "explanation": exp.get("explanation") if exp else None,
            "related_topics": exp.get("related_topics", []) if exp else [],
            "budget_warning": False,
            "from_cache": True,
        }

    parsed = llm_svc.parse_query(q, lang=lang)
    if parsed:
        terms = llm_svc.generate_search_terms(parsed)
    else:
        terms = [q]

    if type == "video":
        raw = yt_svc.search(terms, lang=lang)
    else:
        raw = archive_svc.search(terms, lang=lang)

    results = llm_svc.rank_results(raw, parsed) if parsed else raw

    explanation_data = llm_svc.explain_topic(parsed) if parsed else None

    cache_svc.set(type, q, lang, results)
    if explanation_data:
        cache_svc.set(f"{type}_explanation", q, lang, [explanation_data])

    return {
        "results": results,
        "explanation": explanation_data.get("explanation") if explanation_data else None,
        "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
        "budget_warning": llm_svc.tracker.is_warning_threshold(),
        "from_cache": False,
    }
```

- [ ] **Step 4: Run all search router tests**

```
python -m pytest tests/test_search_router.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add backend/routers/search.py backend/tests/test_search_router.py
git commit -m "feat: include LLM topic explanation in search API response"
```

---

## Task 4: Telugu-Only Vyakhanams (Backend)

**Files:**
- Modify: `backend/services/scraper_service.py`
- Modify: `backend/routers/vyakhanams.py`
- Test: `backend/tests/test_scraper_service.py` (verify)
- Test: `backend/tests/test_vyakhanams_router.py` (verify)

- [ ] **Step 1: Update `scraper_service.py` — Telugu sources only**

Replace `SOURCES` list in `backend/services/scraper_service.py`:

```python
SOURCES = [
    {
        "scholar": "Brahmasri Chaganti Koteswara Rao",
        "affiliation": "chaganti.net",
        "url_template": "https://www.chaganti.net/search?q={query}",
        "lang": "Telugu",
        "content_selector": "p",
    },
    {
        "scholar": "Brahmasri Garikapati Narasimha Rao",
        "affiliation": "speakingtree.in",
        "url_template": "https://www.speakingtree.in/search/{query}",
        "lang": "Telugu",
        "content_selector": "p",
    },
]
```

Also update `scrape` method signature to always use Telugu regardless of `lang` param:

```python
    def scrape(self, query: str, lang: str = "Telugu", min_text_len: int = 80) -> list[dict]:
        results = []
        for source in SOURCES:  # All sources are already Telugu-only
            time.sleep(1)
            ...
```

(Keep rest of method body identical — just remove English sources from `SOURCES`.)

- [ ] **Step 2: Update `vyakhanams.py` — always Telugu**

Replace `backend/routers/vyakhanams.py` with:

```python
import os
import logging
from fastapi import APIRouter, Query
from services.scraper_service import ScraperService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService
from services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
scraper_svc = ScraperService()
cache_svc = CacheService()


@router.get("/vyakhanams")
def vyakhanams(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),  # kept for API compat, always uses Telugu
):
    # Always Telugu regardless of requested language
    cache_key_lang = "Telugu"
    cached = cache_svc.get("vyakhanam", q, cache_key_lang)
    if cached is not None:
        return {"results": cached, "from_cache": True}

    raw = scraper_svc.scrape(q, lang="Telugu")
    parsed = llm_svc.parse_query(q, lang="Telugu")
    results = llm_svc.highlight_vyakhanams(raw, parsed) if parsed and raw else raw
    cache_svc.set("vyakhanam", q, cache_key_lang, results)

    return {"results": results, "from_cache": False}
```

- [ ] **Step 3: Run existing vyakhanams + scraper tests**

```
python -m pytest tests/test_scraper_service.py tests/test_vyakhanams_router.py -v
```

Expected: All tests PASS (no behaviour changes, just removed English sources).

- [ ] **Step 4: Commit**

```
git add backend/services/scraper_service.py backend/routers/vyakhanams.py
git commit -m "feat: lock Vyakhanams to Telugu-only sources"
```

---

## Task 5: Run Full Backend Test Suite + Deploy to EC2

- [ ] **Step 1: Run all 33+ backend tests**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
python -m pytest tests\ -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 2: Push to GitHub**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches
git push origin master
```

- [ ] **Step 3: Deploy to EC2 via SSM (no SSH key needed)**

```
aws ssm send-command `
  --instance-ids i-0dae33738624b349b `
  --document-name "AWS-RunShellScript" `
  --parameters '{"commands":["cd /home/ec2-user/sanatana-dharma-speeches && git pull origin master && source .venv/bin/activate && pip install -r backend/requirements.txt -q && sudo systemctl restart dharma-api && sleep 3 && systemctl is-active dharma-api"]}' `
  --query "Command.CommandId" --output text
```

Wait ~15s, then check the command output:
```
aws ssm list-command-invocations --command-id <CommandId> --details --query "CommandInvocations[0].CommandPlugins[0].Output"
```

Expected output ends with: `active`

- [ ] **Step 4: Verify backend health + explanation in response**

```
curl -s https://api.find.sanatanadharmas.com/health
curl -s "https://api.find.sanatanadharmas.com/api/search?q=Siva+Tatvam&lang=Telugu&type=video&limit=3" | python -c "import sys,json; d=json.load(sys.stdin); print('explanation:', bool(d.get('explanation'))); print('results:', len(d['results']))"
```

Expected:
```
{"status":"ok"}
explanation: True
results: 3
```

---

## Task 6: Multiline SearchBar (Frontend)

**Files:**
- Modify: `mobile/components/SearchBar.tsx`

- [ ] **Step 1: Replace `SearchBar.tsx` with multiline version**

Replace the full file:

```tsx
import React, { useState } from "react";
import {
  View, TextInput, TouchableOpacity, Text,
  ScrollView, StyleSheet, Platform,
} from "react-native";
import { COLORS } from "../constants/theme";

const TOPIC_CHIPS = [
  "Bhagavad Gita", "Siva Tatvam", "Upanishads", "Ramayanam", "Karma Yoga",
];

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [text, setText] = useState("");

  const submit = () => { if (text.trim()) onSearch(text.trim()); };

  return (
    <View style={styles.container}>
      <View style={styles.inputBox}>
        <Text style={styles.icon}>🔍</Text>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder={"Ask anything about Sanatan Dharma...\n\"Explain Bhagavad Gita Chapter 2 Sloka 47\"\n\"What is Siva Tatvam according to Chaganti?\""}
          placeholderTextColor={COLORS.textDim}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          autoCorrect={false}
        />
      </View>
      <TouchableOpacity
        style={[styles.searchBtn, loading && styles.searchBtnDisabled]}
        onPress={submit}
        disabled={loading}
      >
        <Text style={styles.searchBtnText}>{loading ? "Searching..." : "🔍 Search"}</Text>
      </TouchableOpacity>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
        {TOPIC_CHIPS.map((chip) => (
          <TouchableOpacity
            key={chip}
            style={styles.chip}
            onPress={() => { setText(chip); onSearch(chip); }}
          >
            <Text style={styles.chipText}>{chip}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingVertical: 12 },
  inputBox: {
    flexDirection: "row",
    backgroundColor: COLORS.bgLight,
    borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.gold,
    paddingHorizontal: 14, paddingVertical: 10,
    shadowColor: COLORS.gold, shadowOpacity: 0.15, shadowRadius: 12,
    elevation: 4, minHeight: 100,
  },
  icon: { fontSize: 16, marginRight: 8, marginTop: 2 },
  input: {
    flex: 1, color: COLORS.text, fontSize: 14,
    lineHeight: 22, minHeight: 80,
  },
  searchBtn: {
    backgroundColor: COLORS.gold, borderRadius: 10,
    paddingVertical: 12, marginTop: 8,
    alignItems: "center", justifyContent: "center",
  },
  searchBtnDisabled: { opacity: 0.5 },
  searchBtnText: { color: "#000", fontWeight: "700", fontSize: 14 },
  chips: { marginTop: 10 },
  chip: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: "#e2a84b33", borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 4, marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
```

- [ ] **Step 2: Commit**

```
git add mobile/components/SearchBar.tsx
git commit -m "feat: replace search input with always-large multiline textarea"
```

---

## Task 7: ExplanationPanel Component + AppContext + API Types

**Files:**
- Create: `mobile/components/ExplanationPanel.tsx`
- Modify: `mobile/context/AppContext.tsx`
- Modify: `mobile/api/client.ts`
- Modify: `mobile/app/index.tsx`

- [ ] **Step 1: Update API types in `mobile/api/client.ts`**

Replace the `SearchResponse` interface and `searchVideos`/`searchAudio` return types:

```ts
export interface SearchResponse<T> {
  results: T[];
  explanation: string | null;
  related_topics: string[];
  budget_warning: boolean;
  from_cache: boolean;
}
```

(No other changes to `client.ts` — the existing `apiFetch` and endpoint paths stay the same.)

- [ ] **Step 2: Update `AppContext.tsx` to store explanation + related topics**

Replace the full file:

```tsx
import React, { createContext, useContext, useState, useCallback } from "react";
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
  setQuery: (q: string) => void;
  setLanguage: (l: Language) => void;
  search: (q: string) => Promise<void>;
  setCurrentPlayer: (item: PlayerItem | null) => void;
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
  const [searchError, setSearchError] = useState<string | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearchError(null);
    try {
      const [videoRes, audioRes, vyakhanamRes] = await Promise.all([
        api.searchVideos(q, language),
        api.searchAudio(q, language),
        api.getVyakhanams(q, "Telugu"),  // always Telugu
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
      setQuery, setLanguage, search, setCurrentPlayer,
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

- [ ] **Step 3: Create `mobile/components/ExplanationPanel.tsx`**

```tsx
import React, { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { COLORS } from "../constants/theme";

interface Props {
  explanation: string | null;
  relatedTopics: string[];
  onTopicPress: (topic: string) => void;
}

export function ExplanationPanel({ explanation, relatedTopics, onTopicPress }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  if (!explanation) return null;

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.header} onPress={() => setCollapsed((c) => !c)}>
        <Text style={styles.title}>✨ Topic Insight</Text>
        <Text style={styles.toggle}>{collapsed ? "▼ Show" : "▲ Hide"}</Text>
      </TouchableOpacity>

      {!collapsed && (
        <View style={styles.body}>
          <Text style={styles.explanation}>{explanation}</Text>
          {relatedTopics.length > 0 && (
            <View style={styles.relatedRow}>
              <Text style={styles.relatedLabel}>Explore:</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {relatedTopics.map((topic) => (
                  <TouchableOpacity
                    key={topic}
                    style={styles.chip}
                    onPress={() => onTopicPress(topic)}
                  >
                    <Text style={styles.chipText}>{topic}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 16, marginBottom: 12,
    backgroundColor: COLORS.bgLight,
    borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.gold + "55",
    overflow: "hidden",
  },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: COLORS.goldDim,
  },
  title: { color: COLORS.gold, fontSize: 12, fontWeight: "700" },
  toggle: { color: COLORS.textMuted, fontSize: 11 },
  body: { padding: 14 },
  explanation: { color: COLORS.text, fontSize: 13, lineHeight: 20 },
  relatedRow: { marginTop: 10, flexDirection: "row", alignItems: "center", gap: 8 },
  relatedLabel: { color: COLORS.textMuted, fontSize: 11 },
  chip: {
    backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.gold + "44",
    borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, marginRight: 6,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
```

- [ ] **Step 4: Update `mobile/app/index.tsx` to render ExplanationPanel**

Add import at top of file (after existing imports):

```tsx
import { ExplanationPanel } from "../components/ExplanationPanel";
```

Update the destructured values from `useApp()`:

```tsx
  const { videos, audio, vyakhanams, loading, budgetWarning, searchError,
          explanation, relatedTopics, language, setLanguage, search } = useApp();
```

Add `ExplanationPanel` just before `{hasResults && (` block (after `{searchError && ...}` and `{budgetWarning && ...}` banners):

```tsx
      <ExplanationPanel
        explanation={explanation}
        relatedTopics={relatedTopics}
        onTopicPress={search}
      />
```

- [ ] **Step 5: Commit**

```
git add mobile/components/ExplanationPanel.tsx mobile/components/SearchBar.tsx mobile/context/AppContext.tsx mobile/api/client.ts mobile/app/index.tsx
git commit -m "feat: add ExplanationPanel with LLM topic insight and related topic chips"
```

---

## Task 8: Build, Deploy Frontend, Smoke-Test

- [ ] **Step 1: Build Expo web**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .expo -ErrorAction SilentlyContinue
$env:EXPO_PUBLIC_API_URL = "https://api.find.sanatanadharmas.com"
npx expo export --platform web
```

Expected: `Exported: dist` with a new JS bundle hash.

- [ ] **Step 2: Verify HTTPS URL baked into bundle**

```
Select-String "api.find.sanatanadharmas.com" "mobile\dist\_expo\static\js\web\index-*.js" | Select-Object -First 1 | ForEach-Object { $_.Line.Substring(0, 80) }
```

Expected: shows `https://api.find.sanatanadharmas.com`

- [ ] **Step 3: Deploy to S3 + invalidate CloudFront**

```
aws s3 sync dist/ s3://find.sanatanadharmas.com/ --delete --cache-control "public, max-age=31536000" --quiet
aws s3 cp dist/index.html s3://find.sanatanadharmas.com/index.html --cache-control "no-cache, no-store, must-revalidate" --content-type "text/html" --quiet
$inv = aws cloudfront create-invalidation --distribution-id E1VGFNYVAOH3JE --paths "/*" | ConvertFrom-Json
aws cloudfront wait invalidation-completed --distribution-id E1VGFNYVAOH3JE --id $inv.Invalidation.Id
Write-Host "Frontend deployed!"
```

- [ ] **Step 4: Smoke test — verify explanation + authentic speakers in API response**

```
$r = curl -s "https://api.find.sanatanadharmas.com/api/search?q=Siva+Tatvam&lang=Telugu&type=video&limit=5" | ConvertFrom-Json
Write-Host "Explanation present:" ($null -ne $r.explanation)
Write-Host "Related topics:" ($r.related_topics -join ", ")
Write-Host "Speakers:" ($r.results | ForEach-Object { $_.speaker } | Select-Object -First 5)
```

Expected:
```
Explanation present: True
Related topics: Panchakshara Mantra, Rudra Abhishekam, Shiva Purana
Speakers: (only Chaganti / Garikapati / Bhakthi TV / authentic channels)
```

- [ ] **Step 5: Verify new frontend bundle is served**

```
curl -s https://find.sanatanadharmas.com/ | Select-String "index-"
```

Expected: new bundle hash (different from `index-b521c2336a6f95b2a67435c0c72cc235.js`)

- [ ] **Step 6: Final commit**

```
cd C:\Users\schinta\SanatanaDharmaSpeeches
git push origin master
```

---

## Quick Reference

```
# Run all backend tests
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
.venv\Scripts\Activate.ps1
python -m pytest tests\ -v --tb=short

# Deploy backend (SSM)
aws ssm send-command --instance-ids i-0dae33738624b349b --document-name "AWS-RunShellScript" --parameters '{"commands":["cd /home/ec2-user/sanatana-dharma-speeches && git pull origin master && source .venv/bin/activate && pip install -r backend/requirements.txt -q && sudo systemctl restart dharma-api"]}'

# Build + deploy frontend
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
$env:EXPO_PUBLIC_API_URL = "https://api.find.sanatanadharmas.com"
npx expo export --platform web
aws s3 sync dist/ s3://find.sanatanadharmas.com/ --delete --quiet
aws cloudfront create-invalidation --distribution-id E1VGFNYVAOH3JE --paths "/*"
```
