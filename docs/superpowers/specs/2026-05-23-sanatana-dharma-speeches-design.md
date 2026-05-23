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

### 2.1 Search
- Large Copilot-style search bar with placeholder: *"Ask anything — 'Siva Tatvam', 'Bhagavad Gita Chapter 2 Sloka 5', 'Karma Yoga'..."*
- Supports natural language and specific queries (topic, scripture, chapter, sloka)
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
│  CacheService · YouTubeService          │
│  ArchiveService · ScraperService        │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────────┐
      │                         │
┌─────▼──────┐         ┌────────▼────────┐
│  SQLite DB │         │  External APIs  │
│  (cache)   │         │  YouTube API v3 │
└────────────┘         │  archive.org    │
                       │  chaganti.net   │
                       │  (scraped)      │
                       └─────────────────┘
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
  - `YouTubeService` — wraps YouTube Data API v3, filters by language/relevance
  - `ArchiveService` — wraps archive.org Metadata API for audio files
  - `ScraperService` — BeautifulSoup scraper for known Telugu Dharma sites (chaganti.net, etc.)
  - `CacheService` — SQLite-backed cache with 24-hour TTL

### 3.3 Database (SQLite)
- Three tables: `video_cache`, `audio_cache`, `vyakhanam_cache`
- Each row: `query_key`, `lang`, `results_json`, `cached_at`
- Cache invalidated after 24 hours

---

## 4. Data Flow

1. User types query + selects language → clicks Search
2. Frontend sends parallel requests to `/api/search?type=video`, `/api/search?type=audio`, `/api/vyakhanams`
3. Backend checks SQLite cache for each request
4. **Cache hit:** return cached JSON immediately
5. **Cache miss:** call YouTube API + archive.org API + scraper in parallel, store results in SQLite, return to frontend
6. Frontend renders:
   - Section 1: Videos tab (default) + Audio tab
   - Section 2: Vyakhanams panel (independent render, may load slightly later)

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

## 8. Error Handling

- **YouTube API quota exceeded:** Return cached results; show "Results may be limited" banner
- **Scraper fails for a site:** Skip that source silently, show results from remaining sources
- **No results found:** Show friendly message with suggested alternative search terms
- **Audio source unavailable:** Show disabled play button with tooltip "Source unavailable"

---

## 9. Out of Scope (v1)

- User accounts / favorites / playlists
- Admin panel for curating content
- Mobile app
- Notifications or subscriptions
- Full transcript/subtitle search
