# Design: LLM Explanation, Authentic Scholars Filter, Multiline Search, Telugu-Only Vyakhanams

**Date:** 2026-05-23  
**Status:** Approved

---

## Overview

Four focused improvements to the SanatanaDharmaSpeeches app:

1. **LLM Explanation** — explain the topic and suggest related queries above results
2. **Authentic Scholars Allowlist** — filter YouTube results to trusted Dharma channels only
3. **Always-Large Multiline Search** — replace single-line input with a multiline textarea
4. **Vyakhanams Telugu Only** — discourses section always returns and displays Telugu only

---

## 1. Authentic Scholars Allowlist

### Backend (`backend/services/youtube_service.py`)

Add a module-level `AUTHENTIC_CHANNELS` set of lowercase channel name substrings. After fetching YouTube results, filter `results` to keep only videos where `channelTitle.lower()` contains at least one entry from the set.

Initial allowlist (case-insensitive substring match):

```python
AUTHENTIC_CHANNELS = {
    "chaganti",
    "garikapati",
    "samavedam",
    "jeeyar",
    "bhakthi tv",
    "telugupuranam",
    "suman tv",
    "sumantvvijayawada",
    "iskcon",
    "chinnajeeyar",
    "tridandi",
    "pravachanam",
    "dharmasandehalu",
    "garikipati",
}
```

Filtering happens **after** deduplication, **before** returning to the search router. If filtering leaves zero results (e.g. the topic is very niche), fall back to the unfiltered list to avoid empty responses.

No new API parameter needed — this is always on.

---

## 2. LLM Explanation

### Backend (`backend/routers/search.py` + `backend/services/llm_service.py`)

Add `explain_topic(parsed: ParsedQuery) -> dict` method to `LLMService`:

- Calls Claude Haiku (cheaper, better at summaries than Llama)
- Prompt asks: given topic + scripture + keywords, explain in 2-3 sentences what this topic means in Sanatan Dharma, then list 3 related topics
- Returns: `{"explanation": str, "related_topics": list[str]}`
- Budget-gated: if `tracker.is_budget_exceeded()`, returns `None`

Update `/api/search` response to include:
```json
{
  "results": [...],
  "explanation": "Siva Tatvam refers to...",
  "related_topics": ["Panchakshara Mantra", "Rudra Abhishekam", "Shiva Purana"],
  "budget_warning": false,
  "from_cache": true
}
```

Explanation is cached alongside results (same `CacheService` key).

### Frontend (`mobile/app/index.tsx` + new `mobile/components/ExplanationPanel.tsx`)

New `ExplanationPanel` component:
- Shown only when `explanation` is non-null and results exist
- Gold border card, collapsible (expanded by default)
- Shows 2-3 sentence explanation in white text
- Shows related topic chips — tapping a chip calls `search(chip)`
- Positioned between search bar and results section

---

## 3. Always-Large Multiline Search

### Frontend (`mobile/components/SearchBar.tsx`)

Replace `TextInput` with `multiline={true}`, `numberOfLines={4}`, `textAlignVertical="top"`.

- Remove `returnKeyType="search"` (not valid on multiline)
- Add an explicit "Search" button below the text area (full-width, gold)
- Keep topic chips below the button
- Adjust styles: fixed height of ~100px, scrollable internally

---

## 4. Vyakhanams Telugu Only

### Backend (`backend/services/scraper_service.py`)

- Filter `SOURCES` to only include sources where `lang == "Telugu"` before scraping
- Remove `Sri Sri Ravishankar` (artofliving.org) and `Swami Sarvapriyananda` (vedantany.org) from SOURCES — both are English
- Keep only `Brahmasri Chaganti Koteswara Rao` (Telugu)
- Add more Telugu scholars to SOURCES:
  - Garikapati Narasimha Rao — `https://www.speakingtree.in/search/{query}`
  - Samavedam Shanmukha Sarma — search via YouTube transcript data (already in video results)

### Backend (`backend/routers/vyakhanams.py`)

- Ignore the `lang` query parameter — always scrape with `lang="Telugu"`

### Frontend (`mobile/app/index.tsx`)

- Remove Vyakhanams from language-dependent search — always fetch vyakhanams with `lang=Telugu` regardless of `AppContext.language`

---

## Data Flow

```
User types long query → SearchBar (multiline)
  ↓ submit
AppContext.search(q)
  ↓ parallel
  ├─ GET /api/search?type=video  → parse_query → generate_terms → YouTube (filtered to authentic) → rank → explain_topic
  ├─ GET /api/search?type=audio  → parse_query → archive.org
  └─ GET /api/vyakhanams?lang=Telugu → Telugu sources only → highlight

  ↓
ExplanationPanel (topic explanation + related chips)
VideoPlaylist (authentic channels only)
AudioPlaylist
VyakhanamsPanel (Telugu only)
```

---

## Files Changed

| File | Change |
|------|--------|
| `backend/services/youtube_service.py` | Add `AUTHENTIC_CHANNELS` allowlist + post-filter |
| `backend/services/llm_service.py` | Add `explain_topic()` method |
| `backend/services/scraper_service.py` | Telugu-only sources, remove English scholars |
| `backend/routers/search.py` | Call `explain_topic`, include in response |
| `backend/routers/vyakhanams.py` | Ignore `lang` param, always use Telugu |
| `mobile/components/SearchBar.tsx` | Multiline textarea |
| `mobile/components/ExplanationPanel.tsx` | New component |
| `mobile/app/index.tsx` | Show ExplanationPanel, pass lang=Telugu for vyakhanams |
| `mobile/context/AppContext.tsx` | Add `explanation` + `relatedTopics` state |
| `mobile/api/client.ts` | Update response types |

---

## Testing

- All existing 33 backend tests must still pass
- New unit tests for `explain_topic` (mocked Bedrock call)
- New unit test for YouTube allowlist filter (verify unfiltered fallback)
- Manual browser test: search "Siva Tatvam" → see explanation + authentic channel videos + Telugu vyakhanams
