# SanatanaDharmaSpeeches — Design Document
**Date:** 2026-05-23  
**Status:** Approved

---

## 1. Overview

A public community website for devotees to search and explore Sanatan Dharma speeches, discourses, and scholarly commentary. Users can search by topic, scripture, chapter, or sloka (e.g., "Siva Tatvam" or "Bhagavad Gita Chapter 2 Sloka 5"), discover video and audio content from YouTube and public archives, read text-based scholarly Vyakhanams (వ్యాఖ్యానాలు), and play all content without leaving the page.

**Target audience:** Small community — devotees and temple members.  
**Access:** Fully public, no login required.  
**Initial language:** Telugu (expandable to English, Sanskrit, Hindi).

---

## 2. Core Features

### 2.1 LLM-Powered Search
- Large Copilot-style search bar with placeholder: *"Ask anything — 'Siva Tatvam', 'Bhagavad Gita Chapter 2 Sloka 5', 'Karma Yoga'..."*
- Supports natural language and highly specific queries (topic, scripture, chapter, sloka number)
- Every search is processed by an LLM **before** hitting any external API:
  1. **Query parsing** — LLM extracts structured intent from the raw query:
     ```json
     {
       "topic": "Siva Tatvam",
       "scripture": null,
       "chapter": null,
       "sloka": null,
       "keywords": ["శివ తత్వం", "Shiva Tattva", "Shiva principle", "Siva philosophy"],
       "language": "Telugu",
       "search_intent": "conceptual discourse"
     }
     ```
  2. **Search term generation** — LLM generates 3–5 optimized search query strings for YouTube and archive.org, covering Telugu transliterations, English equivalents, and alternate spellings
  3. **Result ranking** — after fetching raw results, LLM scores each result (0–1) for relevance to the original query and re-orders the list
  4. **Vyakhanams synthesis** — LLM reads scraped text excerpts and highlights the most relevant passages to the specific query
- Quick-topic suggestion chips below search: Bhagavad Gita, Siva Tatvam, Upanishads, Ramayanam, Karma Yoga
- Language filter pills: **Telugu (default)**, English, Sanskrit, Hindi

### 2.2 Section 1 — Videos & Audio (Playlist)
- Two tabs: **▶ Videos** | **🎵 Audio**
- Each result shows:
  - Title (in Telugu script where applicable)
  - Speaker/orator name
  - Language • Duration • View count (videos) or play count (audio)
- In-page YouTube embed player (video tab)
- In-page HTML5 audio player (audio tab)
- Sticky bottom player bar — persists while scrolling, never navigates away

### 2.3 Section 2 — 📖 Vyakhanams (వ్యాఖ్యానాలు)
- Completely separate section below the Videos & Audio section
- Separated by a decorative divider
- Scrollable text panel aggregating scholarly commentary from multiple scholars
- Each entry shows:
  - Scholar name
  - Affiliation / source website
  - Language badge
  - Text excerpt (color-coded left border per scholar)
- Expandable to full-screen for deep reading

---

## 3. Architecture

```
┌─────────────────────────────────────────┐
│            React Frontend               │
│  SearchBar · LanguageFilter · TopicChips│
│  VideoPlaylist · AudioPlaylist          │
│  VyakhanamsPanel · StickyPlayer         │
└────────────────┬────────────────────────┘
                 │ HTTP (REST)
┌────────────────▼────────────────────────┐
│           FastAPI Backend               │
│  /api/search  /api/vyakhanams           │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │      LLMService (Bedrock)        │   │
│  │  parse_query()                   │   │
│  │  generate_search_terms()         │   │
│  │  rank_results()                  │   │
│  │  highlight_vyakhanams()          │   │
│  └──────────────────────────────────┘   │
│  CacheService · YouTubeService          │
│  ArchiveService · ScraperService        │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────────────────┐
      │                                 │
┌─────▼──────┐    ┌──────────────────────▼──────┐
│  SQLite DB │    │     External Services        │
│  (cache)   │    │  Amazon Bedrock (LLM)        │
└────────────┘    │  YouTube Data API v3         │
                  │  archive.org Metadata API    │
                  │  chaganti.net (scraped)      │
                  └──────────────────────────────┘
```

### 3.1 Frontend (React + TypeScript)
- **Vite** build tool for fast dev/build
- **Components:**
  - `SearchBar` — large rounded input, search button, suggestion chips
  - `LanguageFilter` — pill buttons, Telugu selected by default
  - `VideoPlaylist` — playlist rows with YouTube embed on play
  - `AudioPlaylist` — playlist rows with HTML5 `<audio>` on play
  - `VyakhanamsPanel` — separate scrollable text section, color-coded per scholar
  - `StickyPlayer` — fixed bottom bar with playback controls, progress bar
- **State management:** React Context (lightweight, no Redux needed)
- **Styling:** Tailwind CSS with custom dark theme (navy/gold)

### 3.2 Backend (Python + FastAPI)
- **Endpoints:**

| Endpoint | Description |
|---|---|
| `GET /api/search?q=&lang=&type=video` | Search YouTube videos |
| `GET /api/search?q=&lang=&type=audio` | Search archive.org audio |
| `GET /api/vyakhanams?q=&lang=` | Fetch Vyakhanams text results |

- **Services:**
  - `LLMService` — wraps Amazon Bedrock; `llm_service.py`
  - `YouTubeService` — wraps YouTube Data API v3 using LLM-generated search terms
  - `ArchiveService` — wraps archive.org Metadata API for audio files using LLM-generated terms
  - `ScraperService` — BeautifulSoup scraper for known Telugu Dharma sites (chaganti.net, etc.)
  - `CacheService` — SQLite-backed cache with 24-hour TTL; cache key is the LLM-parsed structured query (not raw text), so "Siva Tatvam" and "శివ తత్వం" hit the same cache entry
  - `CostTrackingService` — tracks daily Bedrock spend in SQLite, enforces $1/day cap, triggers keyword fallback

### 3.3 Database (SQLite)
- Three tables: `video_cache`, `audio_cache`, `vyakhanam_cache`
- Each row: `query_key`, `lang`, `results_json`, `cached_at`
- Cache invalidated after 24 hours

## 4. LLM Search Flow (Amazon Bedrock)

### Step-by-step for query: *"Bhagavad Gita Chapter 2 Sloka 5"*

```
User query
    │
    ▼
LLMService.parse_query()
    → { topic: "Bhagavad Gita", scripture: "Bhagavad Gita",
        chapter: 2, sloka: 5, language: "Telugu",
        keywords: ["భగవద్గీత 2వ అధ్యాయం 5వ శ్లోకం", "BG 2.5", ...] }
    │
    ▼
LLMService.generate_search_terms()
    → YouTube queries: ["Bhagavad Gita chapter 2 sloka 5 Telugu discourse",
                        "భగవద్గీత 2వ అధ్యాయం 5వ శ్లోకం ప్రవచనం",
                        "BG 2.5 Telugu pravachanam"]
    → archive.org queries: ["bhagavad gita chapter 2 verse 5 telugu",
                             "gita 2.5 telugu audio"]
    │
    ▼
Parallel fetch: YouTubeService + ArchiveService + ScraperService
    │
    ▼
LLMService.rank_results(raw_results, parsed_query)
    → Scores each result 0.0–1.0 for relevance, re-orders list
    │
    ▼
LLMService.highlight_vyakhanams(scraped_texts, parsed_query)
    → Returns most relevant passages highlighted per scholar
    │
    ▼
Cache in SQLite (key = normalized parsed query)
    │
    ▼
Return to frontend
```

### LLM Model Selection (Amazon Bedrock)
| Use case | Model | Why |
|---|---|---|
| Query parsing + term generation | **Llama 3.1 8B Instruct** | Fast (~1s), cheap ($0.0002/1k tokens), multilingual |
| Result ranking | **Llama 3.1 8B Instruct** | Short prompts, batch scoring |
| Vyakhanams highlighting | **Claude Haiku 3** | Better at nuanced Sanskrit/Telugu text comprehension |

**Estimated cost per search:** ~$0.001–0.003 (fractions of a cent). 10,000 searches ≈ $10–30/month.

---

## 5. Data Flow

1. User types query + selects language → clicks Search
2. Frontend sends parallel requests to `/api/search?type=video`, `/api/search?type=audio`, `/api/vyakhanams`
3. Backend checks SQLite cache (key = normalized structured query from LLM)
4. **Cache hit:** return cached JSON immediately (no LLM call needed)
5. **Cache miss:**
   - LLM parses query → structured intent
   - LLM generates optimized search terms for each source
   - YouTube API + archive.org API + scrapers called in parallel using LLM-generated terms
   - LLM ranks/scores returned results for relevance
   - LLM highlights relevant Vyakhanams passages
   - Store all results in SQLite cache
6. Frontend renders:
   - Section 1: Videos tab (default) + Audio tab — LLM-ranked results
   - Section 2: Vyakhanams panel — LLM-highlighted passages per scholar

---

## 5. External Sources

| Content Type | Source | Method |
|---|---|---|
| Videos | YouTube Data API v3 | API key (free tier: 10k units/day) |
| Audio | archive.org Metadata API | Free, no key needed |
| Vyakhanams | chaganti.net, artofliving.org, vedantany.org | HTTP scraping (BeautifulSoup) |

> **Note:** Scraping is limited to publicly available text content. Rate limiting (1 req/sec per domain) is enforced to be a respectful consumer.

---

## 6. UI Design

- **Theme:** Dark spiritual — deep navy (#0d1117) background, golden/saffron (#e2a84b) accents
- **Language:** Telugu script supported via system fonts (no custom font loading needed for Telugu)
- **Search bar:** Large, rounded (border-radius 28px), glowing gold border on focus
- **Language filter:** Pill buttons below search, Telugu highlighted by default
- **Divider between sections:** Decorative `✦ ✦ ✦` with gradient lines
- **Vyakhanams scholars:** Color-coded left border per scholar (gold, blue, green...)
- **Sticky player:** Fixed bottom bar, 60px height, always visible during playback

---

## 7. Project Structure

```
SanatanaDharmaSpeeches/
├── frontend/                  # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── LanguageFilter.tsx
│   │   │   ├── VideoPlaylist.tsx
│   │   │   ├── AudioPlaylist.tsx
│   │   │   ├── VyakhanamsPanel.tsx
│   │   │   └── StickyPlayer.tsx
│   │   ├── context/AppContext.tsx
│   │   ├── api/client.ts
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                   # Python FastAPI
│   ├── main.py
│   ├── services/
│   │   ├── llm_service.py        # Amazon Bedrock (parse, rank, highlight)
│   │   ├── youtube_service.py
│   │   ├── archive_service.py
│   │   ├── scraper_service.py
│   │   └── cache_service.py
│   ├── routers/
│   │   ├── search.py
│   │   └── vyakhanams.py
│   ├── database.py
│   └── requirements.txt
└── docs/
```

---

## 8. Cost Controls

### Daily LLM Budget: $1.00 USD/day

A `CostTrackingService` runs in the backend to enforce the daily Bedrock budget.

**How it works:**
- Every Bedrock API call records estimated token cost in SQLite (`llm_cost_log` table: `date`, `tokens_in`, `tokens_out`, `model`, `cost_usd`)
- Before each LLM call, the service checks today's accumulated cost
- If accumulated cost ≥ **$0.95** → serve a warning banner: *"Search accuracy reduced — daily budget nearly reached"*
- If accumulated cost ≥ **$1.00** → **skip LLM entirely**, fall back to raw keyword search for the rest of the day
- Counter resets at **midnight UTC** daily

**Cost per search estimate:**

| Step | Model | Avg tokens | Cost/search |
|---|---|---|---|
| parse_query | Llama 3.1 8B | ~300 in / 150 out | ~$0.00009 |
| generate_search_terms | Llama 3.1 8B | ~400 in / 200 out | ~$0.00012 |
| rank_results | Llama 3.1 8B | ~800 in / 100 out | ~$0.00018 |
| highlight_vyakhanams | Claude Haiku | ~600 in / 200 out | ~$0.00035 |
| **Total per search** | | | **~$0.00074** |

At $0.00074/search and a $1/day cap → **~1,350 LLM-powered searches/day** before fallback. Well above expected community usage.

**Fallback behaviour (budget exhausted):**
- Search still works — uses raw user query string directly on YouTube API and archive.org
- Vyakhanams still shown — returns cached results or raw scraped text without LLM highlighting
- No error shown to user beyond a subtle notice: *"Enhanced search paused — results shown as-is"*

---

## 9. Error Handling

- **LLM call fails (Bedrock timeout):** Fall back to raw keyword search using the original query text directly
- **YouTube API quota exceeded:** Return cached results; show "Results may be limited" banner
- **Scraper fails for a site:** Skip that source silently, show results from remaining sources
- **No results found:** Show friendly message with suggested alternative search terms
- **Audio source unavailable:** Show disabled play button with tooltip "Source unavailable"

---

## 10. Out of Scope (v1)

- User accounts / favorites / playlists
- Admin panel for curating content
- Mobile app
- Notifications or subscriptions
- Full transcript/subtitle search
