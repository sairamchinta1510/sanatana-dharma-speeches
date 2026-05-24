# UX: Search Box Redesign + Grouping + Better Results — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the search box as a conversational card, ensure raw queries are always used alongside LLM-generated terms, improve YouTube search quality, and group results by speaker in Netflix-style horizontal rows.

**Architecture:** Backend receives a one-liner fix (prepend raw query) and a YouTube service overhaul (2 terms + baseline query + relaxed filter). Frontend gets a new `SearchBar` layout, a `SpeakerRow` component that handles horizontal preview + expand, and two thin wrapper components (`GroupedVideoList`, `GroupedAudioList`) that delegate to `SpeakerRow` when multiple speakers exist.

**Tech Stack:** FastAPI (Python 3.11), pytest, React Native Web (Expo), TypeScript, React Native ScrollView/FlatList.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routers/search.py` | Modify | Prepend raw query `q` to LLM-generated terms |
| `backend/services/youtube_service.py` | Modify | Use first 2 terms, add baseline query, relax filter, max 15 results |
| `backend/tests/test_search_router.py` | Modify | Add test for raw-query prepend |
| `backend/tests/test_youtube_service.py` | Modify | Update call-count expectations; add 2-term + baseline tests |
| `mobile/components/SearchBar.tsx` | Modify | Conversational-card layout with inline ↑ button and gold chips |
| `mobile/components/SpeakerRow.tsx` | Create | Horizontal preview cards + expand toggle for one speaker |
| `mobile/components/GroupedVideoList.tsx` | Create | Groups VideoResult[] by speaker; renders SpeakerRow per group |
| `mobile/components/GroupedAudioList.tsx` | Create | Groups AudioResult[] by speaker; renders SpeakerRow per group |
| `mobile/app/index.tsx` | Modify | Use GroupedVideoList + GroupedAudioList instead of VideoPlaylist + AudioPlaylist |

---

## Task 1: Backend — Prepend raw query to LLM terms

**Files:**
- Modify: `backend/routers/search.py` (lines ~41–45)
- Test: `backend/tests/test_search_router.py`

### Context

`search.py` currently builds `terms` from LLM only: `terms = llm_svc.generate_search_terms(parsed)`. If the user types "Karma Yoga" and the LLM generates `["Nishkama Karma Telugu"]`, the literal string "Karma Yoga" is never searched. Fix: prepend `q` to the terms list.

- [ ] **Step 1: Write the failing test**

Add this test to `backend/tests/test_search_router.py` (after the last existing test):

```python
def test_raw_query_prepended_to_llm_terms(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Karma Yoga", keywords=["Karma"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Nishkama Karma"]
        mock_yt.search.return_value = []
        mock_llm.rank_results.return_value = []
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False

        response = client.get("/api/search?q=Karma+Yoga&lang=Telugu&type=video")

    assert response.status_code == 200
    terms_used = mock_yt.search.call_args[0][0]  # first positional arg to yt_svc.search
    assert terms_used[0] == "Karma Yoga", "raw query must be first term"
    assert "Nishkama Karma" in terms_used, "LLM terms must also be included"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\backend
.venv\Scripts\Activate.ps1
python -m pytest tests/test_search_router.py::test_raw_query_prepended_to_llm_terms -v
```

Expected: `FAILED` — `terms_used[0] == "Karma Yoga"` assertion fails because raw query is not currently prepended.

- [ ] **Step 3: Apply the fix in `backend/routers/search.py`**

Find this block (around line 41):

```python
    parsed = llm_svc.parse_query(q, lang=lang)
    if parsed:
        terms = llm_svc.generate_search_terms(parsed)
    else:
        terms = [q]
```

Replace with:

```python
    parsed = llm_svc.parse_query(q, lang=lang)
    if parsed:
        terms = [q] + llm_svc.generate_search_terms(parsed)
    else:
        terms = [q]
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_search_router.py -v
```

Expected: all 5 tests pass including `test_raw_query_prepended_to_llm_terms`.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/search.py backend/tests/test_search_router.py
git commit -m "fix: prepend raw query to LLM-generated search terms"
```

---

## Task 2: Backend — YouTube service improvements

**Files:**
- Modify: `backend/services/youtube_service.py`
- Test: `backend/tests/test_youtube_service.py`

### What changes

1. Use first 2 LLM terms (not just 1)
2. Add one baseline query (`"{primary} Telugu pravachanam"`) without a scholar suffix
3. Relax topic filter from `// 3` to `// 4` threshold
4. Default `max_results` = 15 (was 10)

After changes, call count for a single term = `len(SCHOLAR_QUERIES) + 1` = 6; for 2 terms = `2 * len(SCHOLAR_QUERIES) + 1` = 11.

- [ ] **Step 1: Update existing tests that check call count**

In `backend/tests/test_youtube_service.py`, replace `test_uses_one_query_per_scholar`:

```python
def test_uses_one_query_per_scholar_plus_baseline(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([])
    svc.search(["Rama Nama"], lang="Telugu")
    # 5 scholar queries + 1 baseline = 6 total for a single term
    assert mock_youtube_build.search().list().execute.call_count == len(SCHOLAR_QUERIES) + 1
```

And replace `test_scholar_queries_include_topic`:

```python
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
```

Add two new tests after the existing ones:

```python
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
```

- [ ] **Step 2: Run updated tests to confirm they now fail**

```bash
python -m pytest tests/test_youtube_service.py -v
```

Expected: `test_uses_one_query_per_scholar_plus_baseline`, `test_uses_second_term_when_provided`, `test_baseline_query_does_not_use_scholar_suffix` all FAIL (old code still runs 5 calls, not 6/11).

- [ ] **Step 3: Rewrite `YouTubeService.search()` in `backend/services/youtube_service.py`**

Replace the entire `search` method (lines 27–69):

```python
    def search(self, terms: list[str], lang: str, max_results: int = 15) -> list[dict]:
        if not terms:
            return []
        primary = terms[0] if isinstance(terms[0], str) else str(terms[0])
        secondary = terms[1] if len(terms) > 1 and isinstance(terms[1], str) else None

        relevance_lang = LANG_CODE.get(lang, "te")
        seen: set[str] = set()
        results: list[dict] = []

        # Build query list: scholar-suffixed queries for primary (and secondary if present)
        query_topics = [primary] + ([secondary] if secondary else [])
        queries: list[str] = []
        for topic in query_topics:
            for suffix in SCHOLAR_QUERIES:
                queries.append(f"{topic} {suffix}")
        # Baseline: primary topic with generic Telugu suffix (no scholar bias)
        queries.append(f"{primary} Telugu pravachanam")

        for query in queries:
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

        return self._filter_by_topic(results, primary)[:max_results]
```

Also update `_filter_by_topic` — lower the threshold from `// 3` to `// 4`:

```python
    @staticmethod
    def _filter_by_topic(results: list[dict], topic: str) -> list[dict]:
        keywords = YouTubeService._extract_keywords(topic)
        if not keywords:
            return results
        threshold = max(1, len(keywords) // 4)   # relaxed from // 3

        def passes(r: dict) -> bool:
            text = (r.get("title", "") + " " + r.get("description", "")).lower()
            return sum(1 for kw in keywords if kw in text) >= threshold

        filtered = [r for r in results if passes(r)]
        return filtered if filtered else results
```

- [ ] **Step 4: Run all YouTube tests to confirm they pass**

```bash
python -m pytest tests/test_youtube_service.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Run the full backend test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: all tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add backend/services/youtube_service.py backend/tests/test_youtube_service.py
git commit -m "feat: improve YouTube search — use 2 terms, baseline query, relaxed filter, max 15"
```

---

## Task 3: Backend — Deploy to EC2

**Context:** `git push` hangs in this repo. All backend changes must be applied directly on EC2 instance `i-0dae33738624b349b` via AWS SSM `AWS-RunShellScript`. Frontend is deployed separately (Task 8).

- [ ] **Step 1: Apply `search.py` change on EC2 via SSM**

Run the following AWS CLI command from your local machine (PowerShell):

```powershell
aws ssm send-command `
  --instance-ids "i-0dae33738624b349b" `
  --document-name "AWS-RunShellScript" `
  --parameters commands=["python3 - <<'PYEOF'
import re

path = '/home/ec2-user/app/backend/routers/search.py'
with open(path) as f:
    src = f.read()

old = '''    if parsed:
        terms = llm_svc.generate_search_terms(parsed)'''
new = '''    if parsed:
        terms = [q] + llm_svc.generate_search_terms(parsed)'''

assert old in src, 'Pattern not found — check file manually'
src = src.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(src)
print('search.py patched OK')
PYEOF"] `
  --region us-east-1
```

Poll for result with the returned `CommandId`:
```powershell
aws ssm get-command-invocation --command-id <CommandId> --instance-id i-0dae33738624b349b --region us-east-1
```

Expected `Status`: `"Success"`, `StandardOutputContent`: `"search.py patched OK"`.

- [ ] **Step 2: Apply `youtube_service.py` change on EC2 via SSM**

```powershell
aws ssm send-command `
  --instance-ids "i-0dae33738624b349b" `
  --document-name "AWS-RunShellScript" `
  --parameters commands=["python3 /home/ec2-user/app/backend/scripts/patch_youtube.py"] `
  --region us-east-1
```

Since the YouTube service rewrite is large, create the script file first via SSM:

```powershell
aws ssm send-command `
  --instance-ids "i-0dae33738624b349b" `
  --document-name "AWS-RunShellScript" `
  --parameters commands=["cat > /home/ec2-user/app/backend/services/youtube_service.py <<'PYEOF'
import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {\"Telugu\": \"te\", \"English\": \"en\", \"Sanskrit\": \"sa\", \"Hindi\": \"hi\"}

SCHOLAR_QUERIES = [
    \"Chaganti Koteswara Rao Telugu\",
    \"Garikipati Narasimha Rao Telugu\",
    \"Samavedam Shanmukha Sharma Telugu\",
    \"ISKCON Telugu pravachanam\",
    \"Bhakthi TV Telugu pravachanam\",
]

_STOP_WORDS = {\"the\", \"a\", \"an\", \"of\", \"in\", \"and\", \"or\", \"to\", \"for\", \"on\", \"by\", \"with\", \"at\", \"from\", \"is\", \"are\", \"was\", \"be\"}


class YouTubeService:
    def __init__(self):
        api_key = os.getenv(\"YOUTUBE_API_KEY\")
        if not api_key:
            raise ValueError(\"YOUTUBE_API_KEY environment variable not set\")
        self._yt = build(\"youtube\", \"v3\", developerKey=api_key)

    def search(self, terms: list[str], lang: str, max_results: int = 15) -> list[dict]:
        if not terms:
            return []
        primary = terms[0] if isinstance(terms[0], str) else str(terms[0])
        secondary = terms[1] if len(terms) > 1 and isinstance(terms[1], str) else None

        relevance_lang = LANG_CODE.get(lang, \"te\")
        seen: set[str] = set()
        results: list[dict] = []

        query_topics = [primary] + ([secondary] if secondary else [])
        queries: list[str] = []
        for topic in query_topics:
            for suffix in SCHOLAR_QUERIES:
                queries.append(f\"{topic} {suffix}\")
        queries.append(f\"{primary} Telugu pravachanam\")

        for query in queries:
            try:
                resp = (
                    self._yt.search()
                    .list(
                        q=query,
                        part=\"snippet\",
                        type=\"video\",
                        maxResults=3,
                        relevanceLanguage=relevance_lang,
                    )
                    .execute()
                )
                for item in resp.get(\"items\", []):
                    vid = item[\"id\"][\"videoId\"]
                    if vid in seen:
                        continue
                    seen.add(vid)
                    s = item[\"snippet\"]
                    results.append({
                        \"video_id\": vid,
                        \"title\": s[\"title\"],
                        \"speaker\": s[\"channelTitle\"],
                        \"description\": s.get(\"description\", \"\"),
                        \"thumbnail\": s.get(\"thumbnails\", {}).get(\"medium\", {}).get(\"url\", \"\"),
                        \"url\": f\"https://www.youtube.com/watch?v={vid}\",
                        \"lang\": lang,
                    })
            except Exception as e:
                logger.error(f\"YouTube search failed for query '{query}': {e}\")

        return self._filter_by_topic(results, primary)[:max_results]

    @staticmethod
    def _extract_keywords(topic: str) -> list[str]:
        if not isinstance(topic, str):
            topic = \" \".join(topic) if isinstance(topic, list) else str(topic)
        result = []
        for w in topic.lower().split():
            cleaned = w.strip(\".,!?()\")
            if cleaned not in _STOP_WORDS and len(cleaned) > 1:
                result.append(cleaned)
        return result

    @staticmethod
    def _filter_by_topic(results: list[dict], topic: str) -> list[dict]:
        keywords = YouTubeService._extract_keywords(topic)
        if not keywords:
            return results
        threshold = max(1, len(keywords) // 4)

        def passes(r: dict) -> bool:
            text = (r.get(\"title\", \"\") + \" \" + r.get(\"description\", \"\")).lower()
            return sum(1 for kw in keywords if kw in text) >= threshold

        filtered = [r for r in results if passes(r)]
        return filtered if filtered else results
PYEOF
echo 'youtube_service.py written OK'"] `
  --region us-east-1
```

- [ ] **Step 3: Restart the API service on EC2**

```powershell
aws ssm send-command `
  --instance-ids "i-0dae33738624b349b" `
  --document-name "AWS-RunShellScript" `
  --parameters commands=["sudo systemctl restart dharma-api && sleep 3 && sudo systemctl is-active dharma-api"] `
  --region us-east-1
```

Expected output: `active`

- [ ] **Step 4: Clear search cache and smoke-test the API**

```powershell
# Clear cache so new search logic runs fresh
aws ssm send-command `
  --instance-ids "i-0dae33738624b349b" `
  --document-name "AWS-RunShellScript" `
  --parameters commands=["sqlite3 /home/ec2-user/app/backend/dharma.db 'DELETE FROM audio_cache; DELETE FROM video_cache;' && echo 'Cache cleared'"] `
  --region us-east-1

# Smoke test: search API should return 200 and results
curl "https://api.find.sanatanadharmas.com/api/search?q=Bhagavad+Gita&lang=Telugu&type=video" | python3 -m json.tool | head -30
```

Expected: JSON with `"results"` array containing video objects, `"from_cache": false`.

---

## Task 4: Frontend — SearchBar redesign

**Files:**
- Modify: `mobile/components/SearchBar.tsx`

### Design (approved Option B — Conversational Card)

- Outer card: dark background (`COLORS.bgLight`), gold border `rgba(226,168,75,0.3)`, rounded 20px, shadow
- Inside: multiline `TextInput` (no border, no icon prefix), placeholder in Telugu
- Bottom row inside the card: faint char-count hint on left, circular gold `↑` button on right
- Below the card: horizontal `ScrollView` of chips with `✦` prefix, gold color
- On web: submit on Enter (without Shift); on all platforms: tap `↑` button
- No external "Search" button

- [ ] **Step 1: Replace `mobile/components/SearchBar.tsx` entirely**

```tsx
import React, { useState } from "react";
import {
  View, TextInput, TouchableOpacity, Text,
  ScrollView, StyleSheet, Platform,
} from "react-native";
import { COLORS } from "../constants/theme";

const TOPIC_CHIPS = [
  "✦ Bhagavad Gita",
  "✦ Siva Tatvam",
  "✦ Upanishads",
  "✦ Ramayanam",
  "✦ Karma Yoga",
  "✦ Chaganti Pravachanam",
];

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (text.trim() && !loading) onSearch(text.trim());
  };

  const handleKeyPress = (e: any) => {
    if (Platform.OS === "web" && e.nativeEvent.key === "Enter" && !e.nativeEvent.shiftKey) {
      e.preventDefault?.();
      submit();
    }
  };

  const glassStyle = Platform.OS === "web"
    ? { backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)" } as any
    : {};

  return (
    <View style={styles.container}>
      {/* Card */}
      <View style={[styles.card, glassStyle]}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          onKeyPress={handleKeyPress}
          placeholder={"చాగంటి గారి భగవద్గీత గురించి చెప్పండి...\n\"What is Nishkama Karma?\"\n\"Explain Siva Tatvam in Telugu\""}
          placeholderTextColor={COLORS.textDim}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
          autoCorrect={false}
        />
        {/* Card footer */}
        <View style={styles.cardFooter}>
          <Text style={styles.hint}>
            {text.length > 0 ? `${text.length} chars` : "AI-powered · Telugu · English"}
          </Text>
          <TouchableOpacity
            style={[styles.submitBtn, (loading || !text.trim()) && styles.submitBtnDisabled]}
            onPress={submit}
            disabled={loading || !text.trim()}
          >
            {/* @ts-ignore — native button for reliable press on web */}
            <Text style={styles.submitIcon}>{loading ? "…" : "↑"}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Topic chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chips}
        contentContainerStyle={styles.chipsContent}
      >
        {TOPIC_CHIPS.map((chip) => {
          const label = chip.replace("✦ ", "");
          return (
            <TouchableOpacity
              key={chip}
              style={[styles.chip, glassStyle]}
              onPress={() => { setText(label); onSearch(label); }}
            >
              <Text style={styles.chipText}>{chip}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingVertical: 12 },
  card: {
    backgroundColor: "rgba(22, 27, 34, 0.95)",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(226, 168, 75, 0.30)",
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    shadowColor: "#000",
    shadowOpacity: 0.5,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  input: {
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 22,
    minHeight: 72,
    outlineWidth: 0,
  },
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    paddingTop: 8,
  },
  hint: { color: COLORS.textDim, fontSize: 10 },
  submitBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.gold,
    alignItems: "center",
    justifyContent: "center",
  },
  submitBtnDisabled: { opacity: 0.35 },
  submitIcon: { color: "#0d1117", fontSize: 16, fontWeight: "800", lineHeight: 18 },
  chips: { marginTop: 10 },
  chipsContent: { paddingRight: 16 },
  chip: {
    backgroundColor: "rgba(226, 168, 75, 0.08)",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(226, 168, 75, 0.20)",
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11, opacity: 0.85 },
});
```

- [ ] **Step 2: Verify the app builds without TypeScript errors**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/components/SearchBar.tsx
git commit -m "feat: redesign SearchBar as conversational card with inline submit button"
```

---

## Task 5: Frontend — SpeakerRow component

**Files:**
- Create: `mobile/components/SpeakerRow.tsx`

### Design

- Collapsed (default): horizontal `ScrollView` of preview cards (max 4 visible), "+N more" card if overflow
- Expanded: full vertical list using existing `VideoPlaylist` or `AudioPlaylist`
- Header: speaker name + item count + "See all →" / "▲ Less" toggle
- Video preview card: 160×130px, thumbnail image (or icon fallback), title 2 lines
- Audio preview card: 150×100px, music icon, title 3 lines
- Tapping any preview card triggers expand

- [ ] **Step 1: Create `mobile/components/SpeakerRow.tsx`**

```tsx
import React, { useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity,
  Image, StyleSheet,
} from "react-native";
import { VideoResult, AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { VideoPlaylist } from "./VideoPlaylist";
import { AudioPlaylist } from "./AudioPlaylist";

const PREVIEW_COUNT = 4;

type SpeakerRowProps =
  | { type: "video"; speaker: string; items: VideoResult[] }
  | { type: "audio"; speaker: string; items: AudioResult[] };

function VideoPreviewCard({ item, onExpand }: { item: VideoResult; onExpand: () => void }) {
  return (
    <TouchableOpacity style={styles.videoCard} onPress={onExpand} activeOpacity={0.75}>
      {item.thumbnail ? (
        <Image source={{ uri: item.thumbnail }} style={styles.thumbnail} resizeMode="cover" />
      ) : (
        <View style={[styles.thumbnail, styles.thumbPlaceholder]}>
          <Text style={styles.thumbIcon}>▶</Text>
        </View>
      )}
      <View style={styles.cardInfo}>
        <Text style={styles.cardTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.cardSub} numberOfLines={1}>{item.speaker}</Text>
      </View>
    </TouchableOpacity>
  );
}

function AudioPreviewCard({ item, onExpand }: { item: AudioResult; onExpand: () => void }) {
  return (
    <TouchableOpacity style={styles.audioCard} onPress={onExpand} activeOpacity={0.75}>
      <Text style={styles.audioIcon}>🎵</Text>
      <Text style={styles.cardTitle} numberOfLines={3}>{item.title}</Text>
      <Text style={styles.cardSub} numberOfLines={1}>{item.lang}</Text>
    </TouchableOpacity>
  );
}

export function SpeakerRow(props: SpeakerRowProps) {
  const { type, speaker, items } = props;
  const [expanded, setExpanded] = useState(false);
  const overflow = items.length - PREVIEW_COUNT;
  const previewItems = items.slice(0, PREVIEW_COUNT);

  return (
    <View style={styles.section}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.speakerName} numberOfLines={1}>{speaker}</Text>
        <Text style={styles.count}>{items.length}</Text>
        <TouchableOpacity onPress={() => setExpanded((e) => !e)} style={styles.toggleBtn}>
          <Text style={styles.toggleText}>{expanded ? "▲ Less" : "See all →"}</Text>
        </TouchableOpacity>
      </View>

      {expanded ? (
        <View style={styles.expandedList}>
          {type === "video"
            ? <VideoPlaylist videos={items as VideoResult[]} />
            : <AudioPlaylist audio={items as AudioResult[]} />}
        </View>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
        >
          {type === "video"
            ? (previewItems as VideoResult[]).map((item) => (
                <VideoPreviewCard
                  key={item.video_id}
                  item={item}
                  onExpand={() => setExpanded(true)}
                />
              ))
            : (previewItems as AudioResult[]).map((item) => (
                <AudioPreviewCard
                  key={item.identifier}
                  item={item}
                  onExpand={() => setExpanded(true)}
                />
              ))}
          {overflow > 0 && (
            <TouchableOpacity style={styles.moreCard} onPress={() => setExpanded(true)}>
              <Text style={styles.moreCount}>+{overflow}</Text>
              <Text style={styles.moreLabel}>more</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    marginBottom: 16,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
    paddingHorizontal: 2,
  },
  speakerName: {
    flex: 1,
    color: COLORS.text,
    fontSize: 12,
    fontWeight: "700",
  },
  count: {
    color: COLORS.textMuted,
    fontSize: 10,
    marginRight: 8,
  },
  toggleBtn: { paddingVertical: 2, paddingHorizontal: 4 },
  toggleText: { color: COLORS.gold, fontSize: 11 },
  scroll: {},
  scrollContent: { paddingRight: 8 },
  expandedList: { marginTop: 4 },
  // Video preview card
  videoCard: {
    width: 160,
    backgroundColor: COLORS.bgLight,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginRight: 8,
    overflow: "hidden",
  },
  thumbnail: {
    width: 160,
    height: 90,
    backgroundColor: COLORS.bgLighter,
  },
  thumbPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  thumbIcon: { color: COLORS.textMuted, fontSize: 20 },
  cardInfo: { padding: 6 },
  cardTitle: { color: COLORS.text, fontSize: 11, fontWeight: "600", lineHeight: 15 },
  cardSub: { color: COLORS.textMuted, fontSize: 9, marginTop: 2 },
  // Audio preview card
  audioCard: {
    width: 150,
    backgroundColor: COLORS.bgLight,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginRight: 8,
    padding: 10,
    justifyContent: "flex-start",
  },
  audioIcon: { fontSize: 20, marginBottom: 6 },
  // "+N more" card
  moreCard: {
    width: 70,
    backgroundColor: "rgba(226,168,75,0.08)",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(226,168,75,0.25)",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
  },
  moreCount: { color: COLORS.gold, fontSize: 18, fontWeight: "700" },
  moreLabel: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
});
```

- [ ] **Step 2: Verify no TypeScript errors**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/components/SpeakerRow.tsx
git commit -m "feat: add SpeakerRow component — horizontal preview + expand toggle"
```

---

## Task 6: Frontend — GroupedVideoList component

**Files:**
- Create: `mobile/components/GroupedVideoList.tsx`

- [ ] **Step 1: Create `mobile/components/GroupedVideoList.tsx`**

```tsx
import React from "react";
import { View } from "react-native";
import { VideoResult } from "../api/client";
import { SpeakerRow } from "./SpeakerRow";
import { VideoPlaylist } from "./VideoPlaylist";

function groupBySpeaker(items: VideoResult[]): [string, VideoResult[]][] {
  const map = new Map<string, VideoResult[]>();
  for (const item of items) {
    const key = item.speaker || "Unknown";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  // Sort: most results first
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

interface Props {
  videos: VideoResult[];
}

export function GroupedVideoList({ videos }: Props) {
  if (videos.length === 0) return <VideoPlaylist videos={videos} />;
  const groups = groupBySpeaker(videos);
  // If every result is from the same speaker, no grouping needed
  if (groups.length <= 1) return <VideoPlaylist videos={videos} />;

  return (
    <View>
      {groups.map(([speaker, items]) => (
        <SpeakerRow key={speaker} type="video" speaker={speaker} items={items} />
      ))}
    </View>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/components/GroupedVideoList.tsx
git commit -m "feat: add GroupedVideoList — Netflix-style speaker rows for videos"
```

---

## Task 7: Frontend — GroupedAudioList component

**Files:**
- Create: `mobile/components/GroupedAudioList.tsx`

- [ ] **Step 1: Create `mobile/components/GroupedAudioList.tsx`**

```tsx
import React from "react";
import { View } from "react-native";
import { AudioResult } from "../api/client";
import { SpeakerRow } from "./SpeakerRow";
import { AudioPlaylist } from "./AudioPlaylist";

function groupBySpeaker(items: AudioResult[]): [string, AudioResult[]][] {
  const map = new Map<string, AudioResult[]>();
  for (const item of items) {
    const key = item.speaker || "Unknown";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

interface Props {
  audio: AudioResult[];
}

export function GroupedAudioList({ audio }: Props) {
  if (audio.length === 0) return <AudioPlaylist audio={audio} />;
  const groups = groupBySpeaker(audio);
  if (groups.length <= 1) return <AudioPlaylist audio={audio} />;

  return (
    <View>
      {groups.map(([speaker, items]) => (
        <SpeakerRow key={speaker} type="audio" speaker={speaker} items={items} />
      ))}
    </View>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/components/GroupedAudioList.tsx
git commit -m "feat: add GroupedAudioList — Netflix-style speaker rows for audio"
```

---

## Task 8: Frontend — Wire grouped lists into the main screen

**Files:**
- Modify: `mobile/app/index.tsx`

- [ ] **Step 1: Update imports in `mobile/app/index.tsx`**

Replace these two import lines:

```tsx
import { VideoPlaylist } from "../components/VideoPlaylist";
import { AudioPlaylist } from "../components/AudioPlaylist";
```

With:

```tsx
import { GroupedVideoList } from "../components/GroupedVideoList";
import { GroupedAudioList } from "../components/GroupedAudioList";
```

- [ ] **Step 2: Replace playlist usages in the JSX**

Find:

```tsx
                {tab === "video" ? (
                  <VideoPlaylist videos={videos} />
                ) : (
                  <AudioPlaylist audio={audio} />
                )}
```

Replace with:

```tsx
                {tab === "video" ? (
                  <GroupedVideoList videos={videos} />
                ) : (
                  <GroupedAudioList audio={audio} />
                )}
```

- [ ] **Step 3: Verify no TypeScript errors and build succeeds**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx tsc --noEmit
npx expo export --platform web --output-dir dist 2>&1 | tail -20
```

Expected: `tsc` exits 0, expo export finishes with "Export was successful".

- [ ] **Step 4: Commit**

```bash
git add mobile/app/index.tsx
git commit -m "feat: use GroupedVideoList and GroupedAudioList in home screen"
```

---

## Task 9: Frontend — Deploy to S3 / CloudFront

- [ ] **Step 1: Build the web app**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches\mobile
npx expo export --platform web --output-dir dist
```

Expected: `dist/` folder populated with `index.html` and hashed assets.

- [ ] **Step 2: Sync to S3**

```bash
aws s3 sync dist s3://find.sanatanadharmas.com --delete --cache-control "no-cache"
```

Expected: files uploaded, deletions of stale files.

- [ ] **Step 3: Invalidate CloudFront cache**

```powershell
$distId = aws cloudfront list-distributions --query "DistributionList.Items[?contains(Aliases.Items,'find.sanatanadharmas.com')].Id" --output text
aws cloudfront create-invalidation --distribution-id $distId --paths "/*"
```

Expected: invalidation `Status: InProgress`.

- [ ] **Step 4: Smoke-test the live app**

Open https://find.sanatanadharmas.com in a browser and verify:

1. **Search box** — card layout with gold border, placeholder in Telugu, inline `↑` button, gold topic chips visible below
2. **Search "Bhagavad Gita"** — results load; if multiple YouTube channels return results, videos are grouped into speaker rows with horizontal scroll
3. **Audio tab** — if archive.org returns results from different sources, speaker rows appear with horizontal scroll
4. **"See all →"** — tapping expands to vertical list; "▲ Less" collapses it back
5. **Play audio** — still works after deploy (proxy endpoint unchanged)

---

## Self-Review Checklist

**Spec coverage:**
- [x] Search box redesign → Task 4
- [x] LLM search always on (raw query prepend) → Task 1
- [x] Better YouTube search results → Task 2
- [x] Group by speaker (Netflix-style) → Tasks 5, 6, 7, 8
- [x] Deploy backend → Task 3
- [x] Deploy frontend → Task 9

**Type consistency:**
- `SpeakerRow` props: `type`, `speaker`, `items` — used consistently in Tasks 5, 6, 7
- `GroupedVideoList` prop: `videos: VideoResult[]` — matches `VideoPlaylist` interface
- `GroupedAudioList` prop: `audio: AudioResult[]` — matches `AudioPlaylist` interface
- `VideoResult.video_id` used as `key` in `VideoPreviewCard` ✓
- `AudioResult.identifier` used as `key` in `AudioPreviewCard` ✓

**No placeholders:** All code blocks are complete and executable.
