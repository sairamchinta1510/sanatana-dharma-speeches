# Local PDF Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index 28 Telugu scripture PDFs from S3 into SQLite FTS5 and surface matching excerpts in the search API and mobile app before falling back to YouTube/archive.org.

**Architecture:** A one-time indexing script (`backend/scripts/index_pdfs.py`) extracts zip files from `~/Downloads/`, uploads PDFs to a new S3 bucket (`sanatana-dharma-content`), and indexes text chunks into a new SQLite FTS5 table. A new `LocalContentService` queries this index; the existing search router runs it in parallel with the online search and returns a new `local_results` field. The mobile app renders a `LocalResultsSection` component below the `ExplanationPanel`.

**Tech Stack:** Python/FastAPI, SQLite FTS5 (unicode61 tokenizer), pdfplumber, boto3, React Native/Expo, TypeScript

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `backend/database.py` | Add `local_content` + `local_content_fts` tables to `init_db()` |
| Create | `backend/services/local_content_service.py` | FTS5 search + S3 presigned URLs |
| Modify | `backend/routers/search.py` | Call `LocalContentService`, add `local_results` to response |
| Modify | `backend/requirements.txt` | Add `pdfplumber>=0.11.0` |
| Create | `backend/scripts/__init__.py` | Empty (makes scripts a package) |
| Create | `backend/scripts/index_pdfs.py` | Unzip → S3 upload → FTS5 index |
| Modify | `backend/.env.example` | Add `LOCAL_CONTENT_BUCKET` |
| Create | `backend/tests/test_local_content_service.py` | Unit tests for LocalContentService |
| Create | `backend/tests/test_index_pdfs.py` | Unit tests for indexing helpers |
| Modify | `backend/tests/test_search_router.py` | Assert `local_results` key in responses |
| Modify | `mobile/api/client.ts` | Add `LocalResult` type; add `local_results` to `SearchResponse<T>` |
| Modify | `mobile/context/AppContext.tsx` | Add `localResults` state; set from API response |
| Create | `mobile/components/LocalResultsSection.tsx` | Category-badged result cards with PDF link |
| Modify | `mobile/app/index.tsx` | Render `<LocalResultsSection>` after `<ExplanationPanel>` |

---

## Task 1: Database — Add local content tables

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: Write a failing test that proves the tables don't exist yet**

In `backend/tests/test_local_content_service.py` create the file with just this test first (it will fail because neither the table nor the service exist yet):

```python
# backend/tests/test_local_content_service.py
import os
os.environ["DB_PATH"] = ":memory:"

import pytest
import database


@pytest.fixture(autouse=True)
def fresh_db():
    import database as db_module
    db_module._memory_conn = None  # force new in-memory DB
    database.init_db()
    yield
    db_module._memory_conn = None


def test_local_content_table_exists():
    with database.db() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='local_content'"
        ).fetchone()
    assert row is not None, "local_content table should exist after init_db()"


def test_local_content_fts_table_exists():
    with database.db() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='local_content_fts'"
        ).fetchone()
    assert row is not None, "local_content_fts virtual table should exist after init_db()"
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd backend
pytest tests/test_local_content_service.py::test_local_content_table_exists tests/test_local_content_service.py::test_local_content_fts_table_exists -v
```

Expected: both tests FAIL with `AssertionError`

- [ ] **Step 3: Add the two tables to `init_db()` in `backend/database.py`**

Add to the `executescript` block after the existing `llm_cost_log` table creation:

```python
# In the executescript string, append after the llm_cost_log block:
            CREATE TABLE IF NOT EXISTS local_content (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_key     TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                page_number INTEGER NOT NULL,
                content     TEXT    NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS local_content_fts USING fts5(
                content,
                content='local_content',
                content_rowid='id',
                tokenize='unicode61'
            );
```

The full updated `init_db()` function:

```python
def init_db() -> None:
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS video_cache (
                query_key TEXT NOT NULL,
                lang TEXT NOT NULL,
                results_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (query_key, lang)
            );
            CREATE TABLE IF NOT EXISTS audio_cache (
                query_key TEXT NOT NULL,
                lang TEXT NOT NULL,
                results_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (query_key, lang)
            );
            CREATE TABLE IF NOT EXISTS vyakhanam_cache (
                query_key TEXT NOT NULL,
                lang TEXT NOT NULL,
                results_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (query_key, lang)
            );
            CREATE TABLE IF NOT EXISTS llm_cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                model TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS local_content (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_key     TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                page_number INTEGER NOT NULL,
                content     TEXT    NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS local_content_fts USING fts5(
                content,
                content='local_content',
                content_rowid='id',
                tokenize='unicode61'
            );
        """)
```

- [ ] **Step 4: Run the tests — they should now pass**

```bash
cd backend
pytest tests/test_local_content_service.py::test_local_content_table_exists tests/test_local_content_service.py::test_local_content_fts_table_exists -v
```

Expected: both PASS

- [ ] **Step 5: Run the full existing test suite to confirm nothing is broken**

```bash
cd backend
pytest tests/ -v
```

Expected: all existing tests pass (ignore the new test file for now — only those two tests exist in it)

- [ ] **Step 6: Commit**

```bash
git add backend/database.py backend/tests/test_local_content_service.py
git commit -m "feat: add local_content and local_content_fts tables to database schema"
```

---

## Task 2: LocalContentService

**Files:**
- Create: `backend/services/local_content_service.py`
- Modify: `backend/tests/test_local_content_service.py`

- [ ] **Step 1: Write failing tests for LocalContentService**

Append these tests to `backend/tests/test_local_content_service.py`:

```python
import dataclasses
from unittest.mock import patch, MagicMock
from services.local_content_service import LocalContentService, LocalResult


def _seed_db(conn, rows: list[dict]) -> None:
    """Insert rows into local_content and rebuild FTS5 index."""
    for row in rows:
        conn.execute(
            "INSERT INTO local_content (pdf_key, category, title, page_number, content) "
            "VALUES (:pdf_key, :category, :title, :page_number, :content)",
            row,
        )
    conn.execute("INSERT INTO local_content_fts(local_content_fts) VALUES('rebuild')")


SAMPLE_ROWS = [
    {
        "pdf_key": "pdfs/Veda/Rigveda.pdf",
        "category": "Veda",
        "title": "Rigveda",
        "page_number": 1,
        "content": "ఋగ్వేద సంహిత అగ్ని సూక్తం మొదటి మండలం",
    },
    {
        "pdf_key": "pdfs/Upanishad/MundakopanishadMantra.pdf",
        "category": "Upanishad",
        "title": "Mundakopanishad",
        "page_number": 3,
        "content": "ముండకోపనిషద్ బ్రహ్మ విద్య సారం",
    },
    {
        "pdf_key": "pdfs/Puran/Garuda Purana Telgu.pdf",
        "category": "Puran",
        "title": "Garuda Purana",
        "page_number": 5,
        "content": "గరుడ పురాణం విష్ణు మాహాత్మ్యం",
    },
]


@pytest.fixture
def svc():
    with database.db() as conn:
        _seed_db(conn, SAMPLE_ROWS)
    with patch("services.local_content_service.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/fake-presigned"
        mock_boto3.client.return_value = mock_s3
        yield LocalContentService()


def test_search_by_english_title(svc):
    results = svc.search("Rigveda", "Rigveda")
    assert len(results) >= 1
    assert results[0].title == "Rigveda"
    assert results[0].category == "Veda"
    assert results[0].page_number == 1
    assert "ఋగ్వేద" in results[0].excerpt
    assert results[0].pdf_url == "https://s3.example.com/fake-presigned"


def test_search_by_telugu_content(svc):
    results = svc.search("Mundaka Upanishad", "ముండకోపనిషద్")
    titles = [r.title for r in results]
    assert "Mundakopanishad" in titles


def test_search_no_match_returns_empty(svc):
    results = svc.search("Nonexistent Topic", "nonexistent")
    assert results == []


def test_result_has_presigned_url(svc):
    results = svc.search("Garuda Purana", "Garuda Purana")
    assert len(results) >= 1
    assert results[0].pdf_url.startswith("https://")


def test_result_is_local_result_dataclass(svc):
    results = svc.search("Rigveda", "Rigveda")
    assert len(results) >= 1
    assert isinstance(results[0], LocalResult)
    assert dataclasses.is_dataclass(results[0])


def test_presigned_url_failure_returns_empty_string(svc):
    svc._s3.generate_presigned_url.side_effect = Exception("S3 error")
    results = svc.search("Rigveda", "Rigveda")
    assert len(results) >= 1
    assert results[0].pdf_url == ""
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd backend
pytest tests/test_local_content_service.py -v -k "not table_exists"
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.local_content_service'`

- [ ] **Step 3: Create `backend/services/local_content_service.py`**

```python
# backend/services/local_content_service.py
import os
import sqlite3
import dataclasses
import logging
from database import db

logger = logging.getLogger(__name__)

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore


@dataclasses.dataclass
class LocalResult:
    title: str
    category: str
    page_number: int
    excerpt: str
    pdf_url: str
    pdf_key: str


class LocalContentService:
    def __init__(self) -> None:
        self._bucket = os.getenv("LOCAL_CONTENT_BUCKET", "sanatana-dharma-content")
        self._s3 = boto3.client(
            "s3", region_name=os.getenv("AWS_REGION", "us-east-1")
        ) if boto3 else None

    def search(self, topic: str, original_query: str) -> list[LocalResult]:
        """Return up to 5 LocalResults matching topic or original_query.

        Strategy 1: title LIKE match (handles English canonical names).
        Strategy 2: FTS5 content match (handles Telugu text in PDFs).
        Results are deduplicated by pdf_key.
        """
        results: list[LocalResult] = []
        seen_keys: set[str] = set()

        with db() as conn:
            # --- Strategy 1: title match ---
            title_rows = conn.execute(
                "SELECT id, pdf_key, category, title, page_number, content "
                "FROM local_content "
                "WHERE title LIKE ? OR title LIKE ? "
                "LIMIT 3",
                (f"%{topic}%", f"%{original_query}%"),
            ).fetchall()

            for row in title_rows:
                if row["pdf_key"] not in seen_keys:
                    seen_keys.add(row["pdf_key"])
                    results.append(self._to_result(row))

            # --- Strategy 2: FTS5 content match ---
            remaining = 5 - len(results)
            if remaining > 0:
                fts_query = self._build_fts_query(topic, original_query)
                if fts_query:
                    try:
                        fts_rows = conn.execute(
                            "SELECT lc.id, lc.pdf_key, lc.category, lc.title, "
                            "       lc.page_number, lc.content "
                            "FROM local_content_fts "
                            "JOIN local_content lc ON local_content_fts.rowid = lc.id "
                            "WHERE local_content_fts MATCH ? "
                            "ORDER BY rank "
                            "LIMIT ?",
                            (fts_query, remaining),
                        ).fetchall()

                        for row in fts_rows:
                            if row["pdf_key"] not in seen_keys:
                                seen_keys.add(row["pdf_key"])
                                results.append(self._to_result(row))

                    except sqlite3.OperationalError as exc:
                        logger.warning("FTS5 search failed: %s", exc)

        return results[:5]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_fts_query(self, *queries: str) -> str:
        """Build a safe FTS5 OR query from one or more query strings."""
        terms: list[str] = []
        seen: set[str] = set()
        for q in queries:
            for word in q.split():
                word = word.strip('.,;:?!()"\'।')
                if len(word) >= 2 and word not in seen:
                    seen.add(word)
                    # Quote each word to avoid FTS5 syntax errors
                    terms.append(f'"{word}"')
        return " OR ".join(terms[:10])

    def _to_result(self, row: sqlite3.Row) -> LocalResult:
        return LocalResult(
            title=row["title"],
            category=row["category"],
            page_number=row["page_number"],
            excerpt=row["content"][:500],
            pdf_url=self._presigned_url(row["pdf_key"]),
            pdf_key=row["pdf_key"],
        )

    def _presigned_url(self, pdf_key: str) -> str:
        if not self._s3:
            return ""
        try:
            return self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": pdf_key},
                ExpiresIn=3600,
            )
        except Exception as exc:
            logger.warning("Failed to generate presigned URL for %s: %s", pdf_key, exc)
            return ""
```

- [ ] **Step 4: Run tests — they should pass**

```bash
cd backend
pytest tests/test_local_content_service.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Run full suite**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/services/local_content_service.py backend/tests/test_local_content_service.py
git commit -m "feat: add LocalContentService with SQLite FTS5 search and S3 presigned URLs"
```

---

## Task 3: Update search router to include local_results

**Files:**
- Modify: `backend/routers/search.py`
- Modify: `backend/tests/test_search_router.py`

- [ ] **Step 1: Add failing tests for `local_results` in search response**

Add to the end of `backend/tests/test_search_router.py`:

```python
LOCAL_RESULT = {
    "title": "Rigveda",
    "category": "Veda",
    "page_number": 1,
    "excerpt": "ఋగ్వేద సంహిత",
    "pdf_url": "https://s3.example.com/presigned",
    "pdf_key": "pdfs/Veda/Rigveda.pdf",
}


def test_search_includes_local_results(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Rigveda", keywords=["Rigveda"], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = ["Rigveda Telugu"]
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = [
            MagicMock(**LOCAL_RESULT, __class__=object)
        ]
        # Use dataclasses mock to avoid asdict issues
        import dataclasses

        @dataclasses.dataclass
        class FakeLocalResult:
            title: str = LOCAL_RESULT["title"]
            category: str = LOCAL_RESULT["category"]
            page_number: int = LOCAL_RESULT["page_number"]
            excerpt: str = LOCAL_RESULT["excerpt"]
            pdf_url: str = LOCAL_RESULT["pdf_url"]
            pdf_key: str = LOCAL_RESULT["pdf_key"]

        mock_local.search.return_value = [FakeLocalResult()]

        response = client.get("/api/search?q=Rigveda&lang=Telugu&type=video")

    assert response.status_code == 200
    data = response.json()
    assert "local_results" in data
    assert len(data["local_results"]) == 1
    assert data["local_results"][0]["title"] == "Rigveda"
    assert data["local_results"][0]["category"] == "Veda"


def test_search_local_results_empty_when_no_match(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = MagicMock(
            topic="Unknown", keywords=[], language="Telugu"
        )
        mock_llm.generate_search_terms.return_value = []
        mock_yt.search.return_value = []
        mock_llm.rank_results.return_value = []
        mock_llm.explain_topic.return_value = None
        mock_llm.tracker.is_warning_threshold.return_value = False
        mock_local.search.return_value = []

        response = client.get("/api/search?q=unknown&lang=Telugu&type=video")

    assert response.status_code == 200
    assert response.json()["local_results"] == []


def test_search_cache_hit_includes_local_results(client):
    """Even on cache hit, local_results must be returned (presigned URLs are time-sensitive)."""
    with patch("routers.search.cache_svc") as mock_cache, \
         patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.local_content_svc") as mock_local:
        mock_cache.get.return_value = VIDEO_RESULT
        mock_llm.parse_query.return_value = MagicMock(
            topic="Rigveda", keywords=["Rigveda"], language="Telugu"
        )
        mock_llm.explain_topic.return_value = None
        import dataclasses

        @dataclasses.dataclass
        class FakeLocalResult:
            title: str = "Rigveda"
            category: str = "Veda"
            page_number: int = 1
            excerpt: str = "ఋగ్వేద"
            pdf_url: str = "https://s3.example.com/presigned"
            pdf_key: str = "pdfs/Veda/Rigveda.pdf"

        mock_local.search.return_value = [FakeLocalResult()]

        response = client.get("/api/search?q=Rigveda&lang=Telugu&type=video")

    assert response.status_code == 200
    data = response.json()
    assert data["from_cache"] is True
    assert "local_results" in data
    assert len(data["local_results"]) == 1
```

- [ ] **Step 2: Run to confirm new tests fail**

```bash
cd backend
pytest tests/test_search_router.py::test_search_includes_local_results \
       tests/test_search_router.py::test_search_local_results_empty_when_no_match \
       tests/test_search_router.py::test_search_cache_hit_includes_local_results -v
```

Expected: FAIL — `local_results` key not in response

- [ ] **Step 3: Update `backend/routers/search.py`**

Replace the full file with:

```python
# backend/routers/search.py
import os
import dataclasses
import logging
from fastapi import APIRouter, Query, HTTPException
from services.llm_service import LLMService
from services.youtube_service import YouTubeService
from services.archive_service import ArchiveService
from services.cache_service import CacheService
from services.cost_tracking_service import CostTrackingService
from services.local_content_service import LocalContentService

logger = logging.getLogger(__name__)
router = APIRouter()

tracker = CostTrackingService(daily_limit_usd=float(os.getenv("DAILY_LLM_BUDGET_USD", "1.0")))
llm_svc = LLMService(tracker=tracker)
yt_svc = YouTubeService()
archive_svc = ArchiveService()
cache_svc = CacheService()
local_content_svc = LocalContentService()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lang: str = Query("Telugu"),
    type: str = Query("video"),
):
    if type not in ("video", "audio"):
        raise HTTPException(status_code=400, detail="type must be 'video' or 'audio'")

    # Always run local search fresh — presigned URLs expire after 1h
    parsed = llm_svc.parse_query(q, lang=lang)
    topic = parsed.topic if parsed and isinstance(parsed.topic, str) and parsed.topic else q
    local_results = local_content_svc.search(topic, q)

    cached = cache_svc.get(type, q, lang)
    if cached:  # only serve non-empty cached results
        explanation_data = llm_svc.explain_topic(parsed) if parsed else None
        return {
            "results": cached,
            "local_results": [dataclasses.asdict(r) for r in local_results],
            "explanation": explanation_data.get("explanation") if explanation_data else None,
            "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
            "budget_warning": False,
            "from_cache": True,
        }

    if parsed:
        canonical = parsed.topic if isinstance(parsed.topic, str) and parsed.topic else q
        raw_terms = ([canonical] if canonical.lower() != q.lower() else []) + [q] + llm_svc.generate_search_terms(parsed)
        seen_t: set[str] = set()
        terms: list[str] = []
        for t in raw_terms:
            if isinstance(t, str) and t and t not in seen_t:
                seen_t.add(t)
                terms.append(t)
    else:
        terms = [q]

    if type == "video":
        raw = yt_svc.search(terms, lang=lang)
    else:
        ascii_terms = [t for t in terms if isinstance(t, str) and any(c.isascii() and c.isalpha() for c in t)][:2]
        if not ascii_terms:
            ascii_terms = [q]
        raw = archive_svc.search(ascii_terms, lang=lang)
        if not raw:
            raw = archive_svc.search([q], lang=lang)

    results = llm_svc.rank_results(raw, parsed) if parsed else raw
    explanation_data = llm_svc.explain_topic(parsed) if parsed else None

    if results:
        cache_svc.set(type, q, lang, results)

    return {
        "results": results,
        "local_results": [dataclasses.asdict(r) for r in local_results],
        "explanation": explanation_data.get("explanation") if explanation_data else None,
        "related_topics": explanation_data.get("related_topics", []) if explanation_data else [],
        "budget_warning": llm_svc.tracker.is_warning_threshold(),
        "from_cache": False,
    }
```

- [ ] **Step 4: Run the new tests — they should now pass**

```bash
cd backend
pytest tests/test_search_router.py -v
```

Expected: all tests in the file PASS

- [ ] **Step 5: Run full test suite**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/search.py backend/tests/test_search_router.py
git commit -m "feat: add local_results to search API response via LocalContentService"
```

---

## Task 4: Indexing script

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/index_pdfs.py`
- Create: `backend/tests/test_index_pdfs.py`

- [ ] **Step 1: Add pdfplumber to requirements.txt**

Open `backend/requirements.txt` and add after the last line:

```
pdfplumber>=0.11.0
```

- [ ] **Step 2: Add LOCAL_CONTENT_BUCKET to .env.example**

Open `backend/.env.example` and add:

```
LOCAL_CONTENT_BUCKET=sanatana-dharma-content
```

- [ ] **Step 3: Create the scripts package init**

```bash
touch backend/scripts/__init__.py
```

The file is empty.

- [ ] **Step 4: Write failing tests for indexing helpers**

Create `backend/tests/test_index_pdfs.py`:

```python
# backend/tests/test_index_pdfs.py
import os
os.environ["DB_PATH"] = ":memory:"

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import database
from index_pdfs import clean_title, chunk_text, find_zips


@pytest.fixture(autouse=True)
def fresh_db():
    import database as db_module
    db_module._memory_conn = None
    database.init_db()
    yield
    db_module._memory_conn = None


# --- clean_title ---

def test_clean_title_removes_extension():
    assert clean_title("Rigveda.pdf") == "Rigveda"


def test_clean_title_strips_telgu_suffix():
    assert clean_title("Garuda Purana Telgu.pdf") == "Garuda Purana"


def test_clean_title_strips_telugu_suffix():
    assert clean_title("YogaTelugu.pdf") == "Yoga"


def test_clean_title_strips_part_numbers():
    assert clean_title("Vishnu puran-1 Telgu.pdf") == "Vishnu puran"


# --- chunk_text ---

def test_chunk_text_short_text_single_chunk():
    text = "Hello world"
    chunks = chunk_text(text, size=500)
    assert chunks == ["Hello world"]


def test_chunk_text_splits_at_sentence_boundary():
    text = "First sentence. " + "X" * 490 + ". Third."
    chunks = chunk_text(text, size=500)
    assert len(chunks) >= 2
    # First chunk should end at sentence boundary
    assert chunks[0].endswith(".")


def test_chunk_text_no_empty_chunks():
    text = "   \n   ".join(["word"] * 10)
    chunks = chunk_text(text, size=10)
    for c in chunks:
        assert c.strip() != ""


def test_chunk_text_telugu_danda_boundary():
    """Telugu sentence-ending character '।' should be used as split point."""
    text = "వాక్యం ఒకటి।" + "అ" * 490 + "।"
    chunks = chunk_text(text, size=500)
    assert len(chunks) >= 2
    assert "।" in chunks[0]


# --- index_pdf (with mocked pdfplumber) ---

def test_index_pdf_inserts_chunks():
    from unittest.mock import patch, MagicMock
    from index_pdfs import index_pdf

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Sample Telugu text " * 50  # > 500 chars

    with patch("index_pdfs.pdfplumber") as mock_pdfplumber:
        mock_pdfplumber.open.return_value.__enter__.return_value.pages = [mock_page]

        with database.db() as conn:
            n = index_pdf(conn, Path("/fake/Rigveda.pdf"), "pdfs/Veda/Rigveda.pdf", "Veda", "Rigveda")

        assert n > 0

    with database.db() as conn:
        rows = conn.execute("SELECT COUNT(*) as cnt FROM local_content").fetchone()
    assert rows["cnt"] > 0


def test_index_pdf_empty_page_skipped():
    from unittest.mock import patch, MagicMock
    from index_pdfs import index_pdf

    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""  # empty page

    with patch("index_pdfs.pdfplumber") as mock_pdfplumber:
        mock_pdfplumber.open.return_value.__enter__.return_value.pages = [mock_page]

        with database.db() as conn:
            n = index_pdf(conn, Path("/fake/empty.pdf"), "pdfs/Veda/empty.pdf", "Veda", "Empty")

    assert n == 0


def test_already_indexed_returns_true_after_insert():
    from index_pdfs import already_indexed

    with database.db() as conn:
        conn.execute(
            "INSERT INTO local_content (pdf_key, category, title, page_number, content) "
            "VALUES (?, ?, ?, ?, ?)",
            ("pdfs/Veda/Rigveda.pdf", "Veda", "Rigveda", 1, "some text"),
        )

    with database.db() as conn:
        assert already_indexed(conn, "pdfs/Veda/Rigveda.pdf") is True


def test_already_indexed_returns_false_for_new_key():
    from index_pdfs import already_indexed

    with database.db() as conn:
        assert already_indexed(conn, "pdfs/Veda/NewVeda.pdf") is False
```

- [ ] **Step 5: Run tests to confirm they fail**

```bash
cd backend
pytest tests/test_index_pdfs.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'index_pdfs'`

- [ ] **Step 6: Create `backend/scripts/index_pdfs.py`**

```python
# backend/scripts/index_pdfs.py
"""One-time script: extract zips → upload PDFs to S3 → index text in SQLite FTS5.

Usage:
    cd backend
    python scripts/index_pdfs.py

Re-running is safe: existing S3 objects and indexed PDFs are skipped.
"""

import os
import sys
import zipfile
import tempfile
import shutil
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
import boto3
from botocore.exceptions import ClientError

from database import db, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BUCKET = os.getenv("LOCAL_CONTENT_BUCKET", "sanatana-dharma-content")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DOWNLOADS_DIR = Path.home() / "Downloads"
CHUNK_SIZE = 500

CATEGORY_MAP = {
    "Veda": "Veda",
    "Puran": "Puran",
    "Upnishad": "Upanishad",
    "Bonus": "Bonus",
}


def find_zips() -> list[Path]:
    patterns: list[Path] = []
    for prefix in CATEGORY_MAP:
        patterns.extend(DOWNLOADS_DIR.glob(f"{prefix}-*.zip"))
        patterns.extend(DOWNLOADS_DIR.glob(f"{prefix}.zip"))
    return sorted(set(patterns))


def clean_title(filename: str) -> str:
    """'Garuda Purana Telgu.pdf' → 'Garuda Purana'"""
    name = Path(filename).stem
    for suffix in (" Telugu", " Telgu", "-2", "-1"):
        name = name.replace(suffix, "")
    return name.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split text into ≤size-char chunks, preferring sentence boundaries."""
    chunks: list[str] = []
    while len(text) > size:
        split_at = size
        for sep in ("।", ".", "\n", " "):
            pos = text.rfind(sep, size // 2, size + 50)
            if pos != -1:
                split_at = pos + 1
                break
        chunk = text[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        text = text[split_at:].strip()
    if text.strip():
        chunks.append(text.strip())
    return chunks


def ensure_bucket(s3: "boto3.client") -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
        logger.info("S3 bucket exists: %s", BUCKET)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            kwargs: dict = {"Bucket": BUCKET}
            if AWS_REGION != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": AWS_REGION}
            s3.create_bucket(**kwargs)
            logger.info("Created S3 bucket: %s", BUCKET)
        else:
            raise


def upload_pdf(s3: "boto3.client", pdf_path: Path, s3_key: str) -> bool:
    """Upload PDF to S3. Returns True if newly uploaded, False if already existed."""
    try:
        s3.head_object(Bucket=BUCKET, Key=s3_key)
        logger.info("  Already in S3: %s", s3_key)
        return False
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            s3.upload_file(str(pdf_path), BUCKET, s3_key)
            logger.info("  Uploaded to S3: %s", s3_key)
            return True
        raise


def already_indexed(conn, pdf_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM local_content WHERE pdf_key = ? LIMIT 1", (pdf_key,)
    ).fetchone()
    return row is not None


def index_pdf(conn, pdf_path: Path, pdf_key: str, category: str, title: str) -> int:
    """Extract text from PDF, chunk it, and insert into local_content.

    Returns the number of chunks inserted. Returns 0 if no text was extracted
    (e.g., scanned image PDF).
    """
    chunks_inserted = 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                for chunk in chunk_text(text):
                    conn.execute(
                        "INSERT INTO local_content "
                        "(pdf_key, category, title, page_number, content) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (pdf_key, category, title, page_num, chunk),
                    )
                    chunks_inserted += 1
    except Exception as exc:
        logger.warning("  Failed to extract text from %s: %s", pdf_path.name, exc)
        return 0

    if chunks_inserted == 0:
        logger.warning(
            "  No text extracted from %s — may be a scanned image PDF", pdf_path.name
        )
    return chunks_inserted


def sync_fts(conn) -> None:
    """Rebuild FTS5 index from local_content source table."""
    conn.execute("INSERT INTO local_content_fts(local_content_fts) VALUES('rebuild')")
    logger.info("FTS5 index rebuilt")


def main() -> None:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    ensure_bucket(s3)
    init_db()

    zips = find_zips()
    if not zips:
        logger.error("No zip files found in %s", DOWNLOADS_DIR)
        sys.exit(1)

    logger.info("Found %d zip file(s)", len(zips))
    total_chunks = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        for zip_path in zips:
            logger.info("Processing: %s", zip_path.name)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp)

            for folder_name, category in CATEGORY_MAP.items():
                folder = tmp / folder_name
                if not folder.exists():
                    continue

                for pdf_path in sorted(folder.glob("*.pdf")):
                    title = clean_title(pdf_path.name)
                    s3_key = f"pdfs/{folder_name}/{pdf_path.name}"

                    upload_pdf(s3, pdf_path, s3_key)

                    with db() as conn:
                        if already_indexed(conn, s3_key):
                            logger.info("  Already indexed: %s", title)
                            continue
                        n = index_pdf(conn, pdf_path, s3_key, category, title)
                        total_chunks += n
                        logger.info("  Indexed '%s': %d chunks", title, n)

            # Clean extracted folders before processing next zip
            for item in tmp.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)

    with db() as conn:
        sync_fts(conn)

    logger.info("Done. Total chunks indexed: %d", total_chunks)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run the tests — they should now pass**

```bash
cd backend
pytest tests/test_index_pdfs.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Run full test suite**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/.env.example \
        backend/scripts/__init__.py backend/scripts/index_pdfs.py \
        backend/tests/test_index_pdfs.py
git commit -m "feat: add PDF indexing script (pdfplumber + S3 upload + FTS5)"
```

---

## Task 5: Mobile — update API types

**Files:**
- Modify: `mobile/api/client.ts`

- [ ] **Step 1: Add `LocalResult` interface and update `SearchResponse<T>` in `mobile/api/client.ts`**

Add the `LocalResult` interface after the `VyakhanamResult` interface (before the `SearchResponse` interface), and add `local_results` to `SearchResponse`:

**Add after `VyakhanamResult` interface:**
```typescript
export interface LocalResult {
  title: string;
  category: string;
  page_number: number;
  excerpt: string;
  pdf_url: string;
  pdf_key: string;
}
```

**Replace the existing `SearchResponse` interface:**
```typescript
export interface SearchResponse<T> {
  results: T[];
  local_results: LocalResult[];
  explanation: string | null;
  related_topics: string[];
  budget_warning: boolean;
  from_cache: boolean;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd mobile
npx tsc --noEmit
```

Expected: no errors (or only pre-existing errors unrelated to this change)

- [ ] **Step 3: Commit**

```bash
git add mobile/api/client.ts
git commit -m "feat: add LocalResult type and local_results to SearchResponse"
```

---

## Task 6: Mobile — update AppContext

**Files:**
- Modify: `mobile/context/AppContext.tsx`

- [ ] **Step 1: Add `localResults` state and surface it through context**

Make these changes to `mobile/context/AppContext.tsx`:

**1. Update the import** — add `LocalResult` to the import from `../api/client`:
```typescript
import { api, VideoResult, AudioResult, VyakhanamResult, LocalResult } from "../api/client";
```

**2. Add `localResults` to the `AppState` interface** (after `relatedTopics: string[];`):
```typescript
  localResults: LocalResult[];
```

**3. Add state variable** (after the `relatedTopics` useState):
```typescript
  const [localResults, setLocalResults] = useState<LocalResult[]>([]);
```

**4. Set `localResults` in the `search()` function** — inside the `try` block, after `setRelatedTopics(...)`:
```typescript
      setLocalResults(videoRes.local_results ?? []);
```

**5. Add `localResults` to the context Provider value** (after `relatedTopics`):
```typescript
      localResults,
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd mobile
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add mobile/context/AppContext.tsx
git commit -m "feat: add localResults to AppContext"
```

---

## Task 7: Mobile — create LocalResultsSection component

**Files:**
- Create: `mobile/components/LocalResultsSection.tsx`

- [ ] **Step 1: Create `mobile/components/LocalResultsSection.tsx`**

```typescript
// mobile/components/LocalResultsSection.tsx
import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Linking,
  StyleSheet,
  ScrollView,
} from "react-native";
import { LocalResult } from "../api/client";
import { COLORS } from "../constants/theme";

interface Props {
  results: LocalResult[];
}

const CATEGORY_COLORS: Record<string, string> = {
  Veda: "#FF9933",
  Puran: "#4CAF50",
  Upanishad: "#2196F3",
  Bonus: "#9C27B0",
};

function ResultCard({ item }: { item: LocalResult }) {
  const [expanded, setExpanded] = useState(false);
  const badgeColor = CATEGORY_COLORS[item.category] ?? COLORS.gold;
  const shortExcerpt = item.excerpt.length > 150
    ? item.excerpt.slice(0, 150) + "…"
    : item.excerpt;

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={[styles.badge, { backgroundColor: badgeColor + "33", borderColor: badgeColor }]}>
          <Text style={[styles.badgeText, { color: badgeColor }]}>{item.category}</Text>
        </View>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {item.title} — Page {item.page_number}
        </Text>
      </View>

      <TouchableOpacity onPress={() => setExpanded((e) => !e)}>
        <Text style={styles.excerpt}>
          {expanded ? item.excerpt : shortExcerpt}
        </Text>
        {item.excerpt.length > 150 && (
          <Text style={styles.expandToggle}>{expanded ? "చూపించకు ▲" : "మరింత చదవండి ▼"}</Text>
        )}
      </TouchableOpacity>

      {item.pdf_url ? (
        <TouchableOpacity
          style={styles.pdfButton}
          onPress={() => Linking.openURL(item.pdf_url)}
        >
          <Text style={styles.pdfButtonText}>📄 PDF తెరవండి</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

export function LocalResultsSection({ results }: Props) {
  if (results.length === 0) return null;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>📚 స్థానిక గ్రంథాలు</Text>
        <Text style={styles.subtitle}>Local Scriptures</Text>
      </View>
      <ScrollView horizontal={false} showsVerticalScrollIndicator={false}>
        {results.map((item, idx) => (
          <ResultCard key={`${item.pdf_key}-${item.page_number}-${idx}`} item={item} />
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: COLORS.bgLight,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: COLORS.gold + "33",
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: COLORS.bgLight,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  title: {
    color: COLORS.gold,
    fontSize: 12,
    fontWeight: "700",
  },
  subtitle: {
    color: COLORS.textMuted,
    fontSize: 10,
    opacity: 0.7,
  },
  card: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
    gap: 8,
  },
  badge: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: "600",
    flex: 1,
  },
  excerpt: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 20,
    marginBottom: 4,
  },
  expandToggle: {
    color: COLORS.gold,
    fontSize: 11,
    marginBottom: 6,
  },
  pdfButton: {
    alignSelf: "flex-start",
    marginTop: 6,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.gold + "66",
    backgroundColor: COLORS.bg,
  },
  pdfButtonText: {
    color: COLORS.gold,
    fontSize: 11,
    fontWeight: "600",
  },
});
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd mobile
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add mobile/components/LocalResultsSection.tsx
git commit -m "feat: add LocalResultsSection component with category badges and PDF link"
```

---

## Task 8: Mobile — integrate LocalResultsSection into HomeScreen

**Files:**
- Modify: `mobile/app/index.tsx`

- [ ] **Step 1: Add import at the top of `mobile/app/index.tsx`**

Add after the existing imports (e.g., after the `ExplanationPanel` import line):
```typescript
import { LocalResultsSection } from "../components/LocalResultsSection";
```

- [ ] **Step 2: Add `localResults` to the destructured values from `useApp()`**

Find the existing destructure:
```typescript
  const { videos, audio, vyakhanams, loading, hasSearched, budgetWarning, searchError,
          explanation, relatedTopics, language, query, setLanguage, search } =
    useApp();
```

Replace with:
```typescript
  const { videos, audio, vyakhanams, localResults, loading, hasSearched, budgetWarning,
          searchError, explanation, relatedTopics, language, query, setLanguage, search } =
    useApp();
```

- [ ] **Step 3: Render `LocalResultsSection` after `ExplanationPanel`**

Find this block in the JSX:
```tsx
        <ExplanationPanel
          explanation={explanation}
          relatedTopics={relatedTopics}
          onTopicPress={search}
        />
```

Add `LocalResultsSection` immediately after it:
```tsx
        <ExplanationPanel
          explanation={explanation}
          relatedTopics={relatedTopics}
          onTopicPress={search}
        />

        <LocalResultsSection results={localResults} />
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd mobile
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add mobile/app/index.tsx
git commit -m "feat: render LocalResultsSection below ExplanationPanel in HomeScreen"
```

---

## Task 9: Install backend dependencies and run indexing script

- [ ] **Step 1: Install pdfplumber in the backend virtual environment**

```bash
cd backend
pip install pdfplumber>=0.11.0
# Or if using a venv:
# .venv/Scripts/pip install pdfplumber>=0.11.0   (Windows)
# .venv/bin/pip install pdfplumber>=0.11.0        (Mac/Linux)
```

Expected output: `Successfully installed pdfplumber-...`

- [ ] **Step 2: Verify AWS credentials are configured**

```bash
aws sts get-caller-identity
```

Expected: JSON with your AWS account ID. If this fails, run `aws configure` first.

- [ ] **Step 3: Run the indexing script**

```bash
cd backend
python scripts/index_pdfs.py
```

Expected output (example):
```
INFO: S3 bucket exists: sanatana-dharma-content   (or "Created S3 bucket: ...")
INFO: Found 4 zip file(s)
INFO: Processing: Veda-20260524T225624Z-3-001.zip
INFO:   Uploaded to S3: pdfs/Veda/Rigveda.pdf
INFO:   Indexed 'Rigveda': 42 chunks
...
INFO: FTS5 index rebuilt
INFO: Done. Total chunks indexed: <N>
```

If any PDF shows `No text extracted` (scanned image), note the filename — those PDFs cannot be searched by content but are still uploaded to S3 and accessible via the PDF link from title matches.

- [ ] **Step 4: Verify indexing by querying the DB directly**

```bash
cd backend
python - <<'EOF'
import database; database.init_db()
with database.db() as conn:
    row = conn.execute("SELECT COUNT(*) as n FROM local_content").fetchone()
    print(f"Total chunks: {row['n']}")
    row = conn.execute("SELECT DISTINCT title FROM local_content LIMIT 10").fetchall()
    for r in row:
        print(" -", r['title'])
EOF
```

Expected: `Total chunks: <number greater than 0>` and a list of indexed titles.

- [ ] **Step 5: Run full backend test suite one last time**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: install pdfplumber; run initial PDF indexing into S3 + SQLite FTS5"
```

- [ ] **Step 7: Push all commits**

```bash
git push origin main
```

---

## Verification Checklist

After all tasks are complete, verify end-to-end behavior:

- [ ] Search for `"Rigveda"` → response contains `local_results` with at least one entry, `title == "Rigveda"`, `pdf_url` starts with `https://`
- [ ] Search for `"గరుడ పురాణం"` (Telugu) → response contains `local_results` with Garuda Purana entry
- [ ] Search for a topic not in the PDFs (e.g., `"modern cricket"`) → `local_results == []`
- [ ] Mobile app: after searching "Rigveda", a "స్థానిక గ్రంథాలు" section appears below the explanation panel
- [ ] Tap "PDF తెరవండి" → device browser opens the S3 presigned URL to the PDF
- [ ] Re-run `python scripts/index_pdfs.py` → no duplicate entries, script exits cleanly
