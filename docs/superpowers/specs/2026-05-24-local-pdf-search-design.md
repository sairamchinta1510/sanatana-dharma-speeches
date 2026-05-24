# Local PDF Search Feature Design

**Date:** 2026-05-24  
**Status:** Approved  
**Author:** Copilot (via brainstorming session)

---

## Overview

Add a local-first search layer to the Sanatana Dharma Speeches app. Before hitting YouTube or archive.org, the app searches a locally indexed collection of 28 Telugu scripture PDFs organized across 4 categories (Veda, Puran, Upanishad, Bonus). Matching results appear in the mobile app below the existing Explanation/Disclosure section, showing a Telugu text excerpt and a direct link to open the full PDF.

The PDFs are stored in a dedicated AWS S3 bucket and indexed in SQLite FTS5 (the same database already used for caching). The feature supports both English queries ("What is Mundaka Upanishad?") and Telugu queries ("మండూకోపనిషద్") — English queries match PDF titles; Telugu queries match content directly via the unicode61 tokenizer.

---

## Source Content

**Zip files** (currently in `~/Downloads/`, downloaded 2026-05-24):

| Zip | # PDFs | Categories |
|-----|--------|------------|
| `Veda-*.zip` | 5 | Rigveda, Yajurveda, Atharvaveda, Sama Veda, Samba Veda |
| `Puran-*.zip` | 17 | Bhagavata, Vishnu, Shiva, Garuda, Padma, Kurma, and more |
| `Upnishad-*.zip` | 4 | Upanishads & related texts |
| `Bonus-*.zip` | 2 | Yoga (Telugu), Ayurveda (Telugu) |

**Total: 28 PDFs**, all in Telugu.

---

## Architecture

### Components

```
[~/Downloads/*.zip]
        ↓ (one-time indexing script)
[S3 Bucket: sanatana-dharma-content]
  pdfs/
    Veda/Rigveda.pdf
    Puran/Garuda Purana Telgu.pdf
    ...
        ↓ (text extraction via pdfplumber)
[SQLite: dharma.db]
  local_content table (text chunks)
  local_content_fts  (FTS5 virtual table)
        ↓ (at query time)
[Backend: LocalContentService]
        ↓
[FastAPI: GET /api/search]  ← adds local_results to response
        ↓
[Mobile: LocalResultsSection component]
```

---

## S3 Bucket

- **Bucket name:** `sanatana-dharma-content`  
- **Region:** `us-east-1` (same as existing AWS config)  
- **Key structure:** `pdfs/<Category>/<filename>.pdf`  
  - e.g., `pdfs/Veda/Rigveda.pdf`, `pdfs/Puran/Garuda Purana Telgu.pdf`
- **Access:** Private; served via presigned URLs with 1-hour TTL
- **Extensibility:** New zips can be dropped into `~/Downloads/` and re-running the indexing script adds them without duplicating existing entries

---

## Database Schema

Two new tables added to `backend/database.py`:

```sql
-- Stores one row per text chunk (~500 chars)
CREATE TABLE IF NOT EXISTS local_content (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  pdf_key      TEXT    NOT NULL,   -- S3 key: "pdfs/Veda/Rigveda.pdf"
  category     TEXT    NOT NULL,   -- "Veda" | "Puran" | "Upanishad" | "Bonus"
  title        TEXT    NOT NULL,   -- Human-readable title, e.g. "Rigveda"
  page_number  INTEGER NOT NULL,
  content      TEXT    NOT NULL    -- Telugu text chunk
);

-- FTS5 external-content virtual table — indexes the content column of local_content
CREATE VIRTUAL TABLE IF NOT EXISTS local_content_fts USING fts5(
  content,
  content='local_content',   -- source table
  content_rowid='id',        -- rowid column in source table
  tokenize='unicode61'       -- handles Telugu Unicode
);
```

**Query pattern** (joins back to source table for metadata):
```sql
SELECT lc.title, lc.category, lc.page_number, lc.content, lc.pdf_key
FROM local_content_fts
JOIN local_content lc ON local_content_fts.rowid = lc.id
WHERE local_content_fts MATCH ?
ORDER BY rank
LIMIT 5;
```

**Title derivation:** Strip extension and clean filename. E.g., `Garuda Purana Telgu.pdf` → `Garuda Purana`.

**Category mapping:** Derived from the zip folder name: `Veda` → `Veda`, `Puran` → `Puran`, `Upnishad` → `Upanishad`, `Bonus` → `Bonus`.

---

## Indexing Script

**File:** `backend/scripts/index_pdfs.py`

**Usage:**
```bash
python backend/scripts/index_pdfs.py
```

**Steps:**
1. Locate zip files in `~/Downloads/` matching `*-20260524T*.zip` (or any `Veda|Puran|Upnishad|Bonus` zip)
2. Extract to a temporary directory
3. For each PDF:
   a. Upload to S3 at `pdfs/<Category>/<filename>.pdf` (skip if already exists via `head_object`)
   b. Extract text page-by-page using `pdfplumber`
   c. Skip if `pdf_key` already in `local_content` (idempotent)
   d. Chunk each page's text into ~500-character segments at sentence boundaries
   e. Insert chunks into `local_content` and `local_content_fts`
4. Log a warning for any PDF where pdfplumber returns empty text (likely scanned image)
5. Clean up temp directory

**Dependencies to add** to `requirements.txt`:
- `pdfplumber>=0.11.0`

---

## LocalContentService

**File:** `backend/services/local_content_service.py`

```python
class LocalResult:
    title: str         # e.g. "Rigveda"
    category: str      # e.g. "Veda"
    page_number: int
    excerpt: str       # ~500 char Telugu text snippet
    pdf_url: str       # S3 presigned URL (1-hour TTL)
    pdf_key: str       # "pdfs/Veda/Rigveda.pdf"

class LocalContentService:
    def search(self, topic: str, original_query: str) -> list[LocalResult]:
        """
        Search strategy:
        1. Title match: check if topic/original_query matches any PDF title (LIKE)
        2. FTS5 content match: query FTS5 with both topic and original_query terms
        3. Deduplicate and rank by relevance score (BM25 via FTS5 rank)
        4. Return top 5 results with presigned S3 URL
        """
```

**Query strategy:**
- `topic` = LLM-normalized canonical name (English), e.g. `"Mundaka Upanishad"`
- `original_query` = raw user input (may be Telugu or English)
- Title match: `SELECT ... FROM local_content WHERE title LIKE '%Mundaka%'`
- FTS5 match: `SELECT ... FROM local_content_fts WHERE local_content_fts MATCH ?` using both topic keywords and original_query
- Results ordered by FTS5 `rank` (BM25 score)
- Max 5 results returned

---

## Search Router Changes

**File:** `backend/routers/search.py`

**Updated `SearchResponse`:**
```python
class SearchResponse(BaseModel):
    results: list[VideoResult | AudioResult]
    local_results: list[LocalResult]   # NEW
    explanation: str | None
    related_topics: list[str]
    budget_warning: bool
    from_cache: bool
```

**Updated flow in `GET /api/search`:**
```python
# After LLM parse_query():
parsed = await llm_service.parse_query(q)

# Run local search AND online search in parallel:
local_task = asyncio.create_task(
    local_content_service.search(parsed.topic, q)
)
online_task = asyncio.create_task(
    youtube_service.search(...) or archive_service.search(...)
)
local_results, online_results = await asyncio.gather(local_task, online_task)

# ... rest of existing flow (LLM rank, explain, cache)
# Include local_results in cached response
```

**Cache schema note:** The `video_cache` and `audio_cache` `results_json` fields will now include `local_results`. No schema migration needed — JSON columns handle this transparently. Existing cached entries without `local_results` return an empty list for that field.

---

## Mobile App Changes

### Types

**File:** `mobile/api/client.ts` — add:
```typescript
export type LocalResult = {
  title: string
  category: string
  page_number: number
  excerpt: string
  pdf_url: string
  pdf_key: string
}

// Update SearchResponse<T>:
export type SearchResponse<T> = {
  results: T[]
  local_results: LocalResult[]   // NEW
  explanation: string | null
  related_topics: string[]
  budget_warning: boolean
  from_cache: boolean
}
```

### New Component

**File:** `mobile/components/LocalResultsSection.tsx`

- Displayed below the Explanation/Disclosure section in the search results screen
- Only rendered when `local_results.length > 0`
- Section heading: `"స్థానిక గ్రంథాలు"` (Local Scriptures)

Each result card shows:
- **Category badge**: colored pill (Veda=saffron, Puran=green, Upanishad=blue, Bonus=purple)
- **Title** + page number: e.g. "Rigveda — Page 42"
- **Telugu excerpt**: truncated to ~150 chars with "..." expand button
- **"PDF తెరవండి" button** ("Open PDF"): opens `pdf_url` in device browser via `Linking.openURL()`

### Search Screen Integration

The existing search screen that renders results is updated to:
1. Accept `local_results` from `SearchResponse`
2. Render `<LocalResultsSection results={local_results} />` after the explanation panel

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| pdfplumber returns empty text for a PDF | Log warning, skip indexing that PDF; script continues |
| S3 upload fails during indexing | Log error and skip; re-run script to retry |
| S3 presigned URL generation fails | Return `pdf_url: ""` for that result; mobile hides the Open PDF button |
| FTS5 search returns no results | `local_results: []` in response; mobile hides the section |
| SQLite FTS5 unavailable | Catch exception, return `local_results: []` gracefully |

---

## Testing

- **Unit tests** for `LocalContentService.search()` using an in-memory SQLite DB seeded with sample chunks
- **Unit test** for indexing script: mock S3 and pdfplumber, verify correct FTS5 insertion
- **Integration test**: end-to-end `GET /api/search?q=Rigveda` returns `local_results` with at least one entry (requires indexed test fixture)
- Existing tests unchanged

---

## Environment Variables

No new required env vars. The script uses existing `DB_PATH` and Boto3 uses existing `AWS_REGION` / credentials.

---

## Rollout

1. Run `index_pdfs.py` once locally to populate S3 and SQLite
2. Deploy updated backend (new service + router changes)
3. Deploy updated mobile app (new component)
4. Verify search returns local results for known titles (e.g., "Rigveda", "Garuda Purana")
