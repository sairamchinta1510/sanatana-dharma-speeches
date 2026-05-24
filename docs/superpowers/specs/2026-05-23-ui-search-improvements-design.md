# SanatanaDharmaSpeeches — UI/UX & Search Quality Improvements Design

> **Status:** Approved by user — ready for implementation planning

## Summary

Four improvements to the live app at https://find.sanatanadharmas.com:

1. **Video Series Grouping** — group same-channel YouTube results into collapsible series cards with episode strip
2. **Inline Audio Player + Sticky Bar** — HTML5 audio playback with persistent now-playing bar
3. **Authentic Telugu Vyakhanams** — fix scrapers to target real Telugu scholar sites + link to source
4. **Scholar-Targeted Search** — generate one query per authentic scholar + hard title-keyword filter

---

## 1. Video Series Grouping

### Problem
When YouTube returns 10+ videos from the same playlist/series (e.g. a 50-part Bhagavad Gita lecture by Chaganti), every episode shows as its own row — creating an overwhelming list of near-duplicates.

### Design

**Grouping logic (backend — `youtube_service.py`):**
- Group results by `channel_title` (speaker). Within each group, sort by publish date.
- Return a new `SeriesResult` shape alongside `VideoResult`:

```python
{
  "type": "series",
  "speaker": "Chaganti Koteswara Rao",
  "channel": "Bhakthi TV",
  "series_title": "Bhagavad Gita",   # inferred from common title prefix
  "episode_count": 47,
  "episodes": [                       # max 20 returned
    { "video_id": "...", "title": "Ep 1 — ...", "thumbnail": "..." },
    ...
  ],
  "lang": "Telugu"
}
```

Groups with 3+ videos from same channel → `SeriesResult`. Singletons remain `VideoResult`.

**`mobile/api/client.ts` — new type:**
```ts
export interface SeriesResult {
  type: "series";
  speaker: string;
  channel: string;
  series_title: string;
  episode_count: number;
  episodes: { video_id: string; title: string; thumbnail: string }[];
  lang: string;
}
```

**`mobile/components/SeriesCard.tsx` — new component:**
- Header row: series title, speaker, episode count badge
- First episode plays inline via YouTube iframe on tap
- Episode strip: horizontal `ScrollView` of episode chips below the player
- Tapping a chip swaps the active iframe `video_id`
- Collapsed by default on mobile; expanded on first tap

**`mobile/components/VideoPlaylist.web.tsx` — updated:**
- Accepts `items: (VideoResult | SeriesResult)[]`
- Renders `SeriesCard` for `type === "series"`, existing row for `VideoResult`

**`mobile/context/AppContext.tsx`:**
- `videos` type updated to `(VideoResult | SeriesResult)[]`

---

## 2. Inline Audio Player + Sticky Bar

### Problem
`expo-av` doesn't stream from archive.org on web — the current implementation silently fails. There is no visible audio player UI.

### Design

**`mobile/components/AudioPlaylist.tsx` — rewrite (web-first):**
- Each audio row renders an HTML5 `<audio>` element (hidden) on web via `Platform.OS === "web"` check
- `play(item)` calls `audioRef.currentTime = 0; audioRef.play()` via `ref`
- Row shows: play/pause icon button, title, speaker, progress bar (updates via `ontimeupdate`), time elapsed
- Only one track plays at a time — switching rows stops the previous

**`mobile/components/StickyAudioBar.tsx` — new component:**
- Rendered in `mobile/app/index.tsx` above the bottom edge, always visible when audio is playing
- Shows: ⏸/▶ toggle, track title (truncated), progress bar (tap to seek), ⏭ next track button
- Hidden when `currentAudio === null`
- Tapping the bar scrolls the audio list into view (using a `ref`)

**`mobile/context/AppContext.tsx`:**
- Add `currentAudio: AudioResult | null` and `setCurrentAudio` to state
- Add `audioQueue: AudioResult[]` — the full list of audio results, for next-track support

**Web implementation detail:**
```tsx
// AudioPlaylist.tsx — web audio playback
const audioRef = useRef<HTMLAudioElement | null>(null);

const play = (item: AudioResult) => {
  if (audioRef.current) audioRef.current.pause();
  const el = document.getElementById(`audio-${item.identifier}`) as HTMLAudioElement;
  el.play();
  audioRef.current = el;
  setCurrentAudio(item);
};
```

Each row contains: `<audio id={`audio-${item.identifier}`} src={item.audio_url} preload="none" />`

---

## 3. Authentic Telugu Vyakhanams

### Problem
`ScraperService` currently scrapes:
- `chaganti.net/search?q=...` — returns English page structure, `p` selector grabs navigation/footer text
- `speakingtree.in/search/...` — English-language platform, not Telugu

Results are generic, not query-specific, not in Telugu.

### Design

**New SOURCES in `backend/services/scraper_service.py`:**

```python
SOURCES = [
    {
        "scholar": "Brahmasri Chaganti Koteswara Rao",
        "affiliation": "chaganti.net",
        "url_template": "https://www.chaganti.net/search?q={query}&lang=te",
        "lang": "Telugu",
        "content_selector": ".search-result-text, .pravachanam-text, article p",
        "min_telugu_ratio": 0.3,   # at least 30% Telugu script chars
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
        "content_selector": ".entry-content p",
        "min_telugu_ratio": 0.2,
    },
]
```

**Telugu script detection helper:**
```python
def _telugu_ratio(text: str) -> float:
    if not text:
        return 0.0
    telugu_chars = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
    return telugu_chars / len(text)
```

**Filtering:**
- Paragraphs must pass `_telugu_ratio(p) >= source["min_telugu_ratio"]` OR be longer than 150 chars (for English transliteration)
- Each result includes `"source_url": url` for "Read original →" link in UI

**`mobile/components/VyakhanamsPanel.tsx`:**
- Add "Read original →" link below each entry using `Linking.openURL(v.source_url)`

---

## 4. Scholar-Targeted Search with Title Filter

### Problem
LLM `generate_search_terms` returns 4 generic/Telugu-script terms. YouTube/archive.org returns broad results. No hard filter exists — irrelevant results appear.

### Design

**`backend/services/youtube_service.py` — `search()` rewrite:**

Instead of one broad search, run **one query per authenticated scholar**:

```python
SCHOLAR_QUERIES = [
    "Chaganti Koteswara Rao Telugu",
    "Garikipati Narasimha Rao Telugu",
    "Samavedam Shanmukha Sharma Telugu",
    "ISKCON Telugu pravachanam",
    "Bhakthi TV Telugu",
]

def search(self, terms: list[str], lang: str) -> list[dict]:
    topic = terms[0]  # primary topic term (first from LLM)
    results = []
    for scholar_suffix in SCHOLAR_QUERIES:
        query = f"{topic} {scholar_suffix}"
        hits = self._search_youtube(query, max_results=3)
        results.extend(hits)
    return self._filter_by_topic(results, topic)
```

**Title filter `_filter_by_topic(results, topic)`:**
```python
def _filter_by_topic(self, results: list[dict], topic: str) -> list[dict]:
    keywords = self._extract_keywords(topic)  # ["bhagavad", "gita", "chapter", "2", "47"]
    def passes(r: dict) -> bool:
        text = (r.get("title", "") + " " + r.get("description", "")).lower()
        return sum(1 for kw in keywords if kw in text) >= max(1, len(keywords) // 3)
    return [r for r in results if passes(r)]
```

**`_extract_keywords(topic)`** — strip stop words, return lowercase tokens.

**Archive search (`search.py`):**
- Same pattern: pass `terms[0]` (primary ASCII term) directly as archive.org query
- Apply same keyword filter on title+description

**Net effect:** Searching "Bhagavad Gita Chapter 2 Sloka 47" returns only videos with "Bhagavad", "Gita", "Chapter 2", or "47" in the title — from authenticated channels only.

---

## File Map

| File | Change |
|------|--------|
| `backend/services/youtube_service.py` | Scholar-query loop + title filter |
| `backend/services/scraper_service.py` | New SOURCES, Telugu ratio filter, source_url |
| `mobile/api/client.ts` | Add `SeriesResult` type |
| `mobile/components/VideoPlaylist.web.tsx` | Accept `SeriesResult`, render `SeriesCard` |
| `mobile/components/SeriesCard.tsx` | **NEW** — collapsible series with episode strip |
| `mobile/components/AudioPlaylist.tsx` | Full rewrite — HTML5 audio, progress bar |
| `mobile/components/StickyAudioBar.tsx` | **NEW** — persistent now-playing bar |
| `mobile/components/VyakhanamsPanel.tsx` | Add "Read original →" link |
| `mobile/context/AppContext.tsx` | Add `currentAudio`, `audioQueue`, update `videos` type |
| `mobile/app/index.tsx` | Render `StickyAudioBar` |
| `backend/tests/test_youtube_service.py` | Tests for scholar-query + title filter |
| `backend/tests/test_scraper_service.py` | Tests for Telugu ratio filter |

---

## Testing

- **Backend:** `python -m pytest tests\ -v --tb=short` from `backend/`
- **Frontend:** `npx expo export --platform web` — zero build errors
- **Smoke test:** Search "Bhagavad Gita Chapter 2" → verify: (a) videos are grouped by series, (b) audio plays inline with sticky bar, (c) Vyakhanams show Telugu text with source links, (d) all results relevant to query

---

## Out of Scope

- Mobile native audio (iOS/Android) — this app is web-first
- Transcripts or subtitles
- User playlists / saved searches
- pravachanam.com integration (separate plan already written)
