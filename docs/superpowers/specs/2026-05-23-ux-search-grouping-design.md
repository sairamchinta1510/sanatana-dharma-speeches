# UX: Search Box Redesign + Grouping + Better Results

**Date:** 2026-05-23  
**Status:** Approved — ready for implementation

---

## Overview

Four improvements to the SanatanaDharmaSpeeches app:

1. **Search box redesign** — Conversational-card style (ChatGPT-style), approved as Option B
2. **LLM search always on** — Every query goes through AI interpretation; no separate mode
3. **Better search results** — YouTube/archive parity: always include raw query alongside LLM terms; multi-term parallel searches
4. **Group results by speaker** — Netflix-style horizontal scroll rows, one row per speaker, approved as Option B

---

## 1. Search Box Redesign (Option B — Conversational Card)

### What changes

Replace the current `SearchBar.tsx` with a card-style conversational input:

- **Card container**: slightly elevated card with subtle gold border, dark background
- **Placeholder text**: shows an example Telugu question in italics (e.g., `"చాగంటి గారి భగవద్గీత గురించి చెప్పండి..."`)
- **Submit button**: `↑` arrow button (gold, circular), positioned inside the card at bottom-right
- **Topic chips**: gold ✦-prefixed chips below the card (Bhagavad Gita, Siva Tatvam, etc.) in a horizontal scroll
- **Remove** the external "🔍 Search" button — replaced by the inline `↑` button
- **Keep** the glass/blur styling and gold color scheme

### Component: `SearchBar.tsx`

- Keep existing `Props` interface (`onSearch`, `loading`)
- Restructure layout: outer card `View` → inner `TextInput` (multiline) → bottom row with character count hint + `↑` button
- Submit on `↑` press or Enter key on web (`onKeyPress` with `e.nativeEvent.key === "Enter"` and Shift not held)

---

## 2. LLM Search Always On

### Current behavior (already mostly correct)

`search.py` already calls `llm_svc.parse_query()` → `llm_svc.generate_search_terms()` on every non-cached request. The LLM interprets the query and expands it to search terms.

### Gap: raw query not included

When the LLM generates search terms, the original user query is **not** always included as a search term. If LLM generates `["Karma Yoga", "Nishkama Karma Telugu"]`, a direct match for the user's exact words may be missed.

### Fix

In `search.py`, always prepend the raw query `q` to the terms list:

```python
terms = [q] + llm_svc.generate_search_terms(parsed)
```

This ensures the original query is always the first/primary search term used in YouTube and archive searches.

No new LLM mode or UI toggle needed — LLM is already always on.

---

## 3. Better YouTube Search Results

### Current behavior

`YouTubeService.search()` runs the first term (`terms[0]`) against each of the 5 `SCHOLAR_QUERIES` (Chaganti, Garikipati, etc.), collects 3 results each = up to 15 raw results, then filters by topic keywords.

### Problems

- Only `terms[0]` used — extra LLM terms ignored (logged as warning)
- Filter is strict: drops results that don't keyword-match, potentially empty result set
- 5 scholar-suffixed queries miss generic searches like raw "Bhagavad Gita Telugu"

### Fixes

**a) Use first 2 LLM terms** (not just 1): Run the SCHOLAR_QUERIES loop for `terms[0]` and `terms[1]` (if available), deduplicating by `video_id`. This at most doubles the API calls (still within YouTube quota).

**b) Add a no-suffix baseline query**: Run `f"{topic} Telugu pravachanam"` once without a scholar suffix, so broad content is captured.

**c) Relax topic filter**: Lower the threshold to `max(1, len(keywords) // 4)` from `// 3` so fewer relevant results get dropped.

**d) Increase `max_results` to 15** (from 10) so the user sees more options when many are available.

---

## 4. Group Results by Speaker (Option B — Netflix-style horizontal rows)

### Layout

For both videos and audio results:

```
[Speaker Name]  (N results)  →  [See all]
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  [+N more]
│      │  │      │  │      │  │      │
└──────┘  └──────┘  └──────┘  └──────┘
```

- Each speaker gets one horizontal scroll row
- Max 4 cards visible before "+N more" indicator
- "See all →" taps to expand that speaker's row to show all items as a vertical list
- Speakers are ordered by number of results (most results first)
- If only 1 speaker found, show a regular vertical list (no grouping needed)

### Components

**New: `GroupedVideoList.tsx`**
- Accepts `videos: VideoResult[]`
- Groups by `item.speaker`
- Renders a `SpeakerRow` for each group
- Falls back to `VideoPlaylist` if ≤1 unique speakers

**New: `GroupedAudioList.tsx`**
- Accepts `audio: AudioResult[]`
- Same structure as `GroupedVideoList`
- Falls back to `AudioPlaylist` if ≤1 unique speakers

**New: `SpeakerRow.tsx`** (shared by both)
- Props: `speaker: string`, `items: VideoResult[] | AudioResult[]`, `type: "video" | "audio"`
- Horizontal `FlatList` with `showsHorizontalScrollIndicator={false}`
- Card width: ~220px (video thumbnail) or ~180px (audio row card)
- "Expand" state: collapses to vertical list on "See all" tap
- "+N more" card at the end when items > 4 (taps to expand)

### Integration

Replace `<VideoPlaylist>` with `<GroupedVideoList>` in `App.tsx` / results screen.  
Replace `<AudioPlaylist>` with `<GroupedAudioList>` in results screen.

Existing `VideoPlaylist.tsx` and `AudioPlaylist.tsx` are kept unchanged and used as the single-speaker fallback + as the expanded view inside `SpeakerRow`.

---

## Data Flow

No backend changes needed for grouping — speaker is already returned in every result:
- `VideoResult.speaker` = YouTube channel title
- `AudioResult.speaker` = archive.org metadata speaker field

Grouping is entirely frontend.

---

## Files to Change

| File | Change |
|------|--------|
| `mobile/components/SearchBar.tsx` | Full redesign: conversational card layout |
| `backend/routers/search.py` | Prepend raw query `q` to terms list |
| `backend/services/youtube_service.py` | Use 2 terms, add baseline query, relax filter, max_results=15 |
| `mobile/components/GroupedVideoList.tsx` | **New**: groups VideoResult[] by speaker |
| `mobile/components/GroupedAudioList.tsx` | **New**: groups AudioResult[] by speaker |
| `mobile/components/SpeakerRow.tsx` | **New**: horizontal scroll row for one speaker |
| `mobile/App.tsx` (or results screen) | Use GroupedVideoList + GroupedAudioList |

---

## Out of Scope

- No "Ask AI" separate mode
- No new backend grouping endpoint
- No changes to vyakhanams panel
- No changes to audio proxy or playback logic
