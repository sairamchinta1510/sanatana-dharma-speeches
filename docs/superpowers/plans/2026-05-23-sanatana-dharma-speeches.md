# SanatanaDharmaSpeeches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform Expo app (iOS + Android + Web) and FastAPI backend that lets devotees search Sanatan Dharma speeches by topic/scripture/sloka, watch/listen in-app, and read scholarly Vyakhanams — all powered by LLM search via Amazon Bedrock with a $1/day cost cap.

**Architecture:** FastAPI backend on AWS EC2 handles all external API calls (YouTube, archive.org, scraping) and LLM orchestration via Amazon Bedrock. The Expo frontend (shared codebase) calls the backend REST API and renders results on iOS, Android, and Web. SQLite caches all results with 24-hour TTL to minimize costs.

**Tech Stack:** Python 3.11, FastAPI, SQLite, boto3 (Bedrock), google-api-python-client (YouTube), BeautifulSoup4, pytest; Expo SDK 51, expo-router v3, NativeWind v4, react-native-youtube-iframe, expo-av, TypeScript, Jest + React Native Testing Library.

---

## File Map

### Backend (`backend/`)
| File | Responsibility |
|---|---|
| `main.py` | FastAPI app factory, CORS, router registration |
| `database.py` | SQLite connection, table creation, migrations |
| `services/cost_tracking_service.py` | Track daily Bedrock spend, enforce $1/day cap |
| `services/llm_service.py` | Bedrock wrapper: parse_query, generate_search_terms, rank_results, highlight_vyakhanams |
| `services/cache_service.py` | SQLite read/write cache with 24-hr TTL |
| `services/youtube_service.py` | YouTube Data API v3 search |
| `services/archive_service.py` | archive.org Metadata API search |
| `services/scraper_service.py` | BeautifulSoup scraper for chaganti.net + others |
| `routers/search.py` | GET /api/search — orchestrates LLM + YouTube + Archive |
| `routers/vyakhanams.py` | GET /api/vyakhanams — orchestrates LLM + scraper |
| `tests/test_cost_tracking.py` | Unit tests for cost tracking |
| `tests/test_llm_service.py` | Unit tests for LLM service (mocked Bedrock) |
| `tests/test_cache_service.py` | Unit tests for cache |
| `tests/test_youtube_service.py` | Unit tests for YouTube service (mocked) |
| `tests/test_archive_service.py` | Unit tests for archive service (mocked) |
| `tests/test_scraper_service.py` | Unit tests for scraper (mocked HTTP) |
| `tests/test_search_router.py` | Integration tests for /api/search |
| `tests/test_vyakhanams_router.py` | Integration tests for /api/vyakhanams |

### Mobile (`mobile/`)
| File | Responsibility |
|---|---|
| `constants/theme.ts` | Color tokens, typography scale |
| `context/AppContext.tsx` | Global state: query, language, results, player state |
| `api/client.ts` | Typed fetch wrapper for backend REST API |
| `components/SearchBar.tsx` | Large search input + suggestion chips |
| `components/LanguageFilter.tsx` | Language pill selector |
| `components/VideoPlaylist.tsx` | Video results list + YouTube player |
| `components/AudioPlaylist.tsx` | Audio results list + expo-av player |
| `components/VyakhanamsPanel.tsx` | Scholar text section with expand-to-modal |
| `components/StickyPlayer.tsx` | Fixed bottom playback bar |
| `app/_layout.tsx` | Root layout: AppContext provider + StickyPlayer |
| `app/index.tsx` | Home screen: SearchBar + LanguageFilter + results sections |
| `app/vyakhanam/[id].tsx` | Full-screen Vyakhanam detail modal |

---

## Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `backend/database.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/routers/__init__.py`

- [ ] **Step 1: Create the backend directory structure**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches
mkdir backend\services backend\routers backend\tests
New-Item backend\services\__init__.py, backend\routers\__init__.py, backend\tests\__init__.py -ItemType File
```

- [ ] **Step 2: Create `backend/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
requests==2.32.3
beautifulsoup4==4.12.3
google-api-python-client==2.131.0
boto3==1.34.101
python-dotenv==1.0.1
pytest==8.2.0
pytest-asyncio==0.23.7
pytest-mock==3.14.0
```

- [ ] **Step 3: Create virtual environment and install dependencies**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 4: Create `backend/database.py`**

```python
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "dharma.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


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
        """)
```

- [ ] **Step 5: Create `backend/main.py`**

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import init_db
from routers import search, vyakhanams

load_dotenv()

app = FastAPI(title="SanatanaDharmaSpeeches API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api")
app.include_router(vyakhanams.router, prefix="/api")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Write a smoke test**

Create `backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 7: Run the smoke test**

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Expected output:
```
tests/test_health.py::test_health PASSED
```

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffolding — FastAPI app, SQLite schema, health endpoint"
```

---

## Task 2: CostTrackingService

**Files:**
- Create: `backend/services/cost_tracking_service.py`
- Create: `backend/tests/test_cost_tracking.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cost_tracking.py`:
```python
import pytest
import os
import time
from unittest.mock import patch
from services.cost_tracking_service import CostTrackingService, BudgetExceededError

os.environ["DB_PATH"] = ":memory:"


@pytest.fixture
def tracker():
    import database
    database.init_db()
    return CostTrackingService(daily_limit_usd=1.0)


def test_record_and_get_daily_cost(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.0001)
    assert tracker.get_today_cost() == pytest.approx(0.0001)


def test_accumulates_multiple_calls(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.40)
    tracker.record(model="haiku", tokens_in=600, tokens_out=200, cost_usd=0.35)
    assert tracker.get_today_cost() == pytest.approx(0.75)


def test_budget_not_exceeded_below_limit(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.50)
    assert tracker.is_budget_exceeded() is False


def test_budget_exceeded_at_limit(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=1.00)
    assert tracker.is_budget_exceeded() is True


def test_warning_threshold(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.96)
    assert tracker.is_warning_threshold() is True


def test_no_warning_below_threshold(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.50)
    assert tracker.is_warning_threshold() is False


def test_raise_if_exceeded(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=1.01)
    with pytest.raises(BudgetExceededError):
        tracker.raise_if_exceeded()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_cost_tracking.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — service doesn't exist yet.

- [ ] **Step 3: Implement `backend/services/cost_tracking_service.py`**

```python
from datetime import date
from database import db


class BudgetExceededError(Exception):
    """Raised when the daily LLM budget has been exceeded."""


class CostTrackingService:
    def __init__(self, daily_limit_usd: float = 1.0):
        self.daily_limit_usd = daily_limit_usd
        self._warning_threshold = daily_limit_usd * 0.95

    def record(self, model: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        today = date.today().isoformat()
        with db() as conn:
            conn.execute(
                "INSERT INTO llm_cost_log (date, model, tokens_in, tokens_out, cost_usd) "
                "VALUES (?, ?, ?, ?, ?)",
                (today, model, tokens_in, tokens_out, cost_usd),
            )

    def get_today_cost(self) -> float:
        today = date.today().isoformat()
        with db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_cost_log WHERE date = ?",
                (today,),
            ).fetchone()
        return float(row[0])

    def is_budget_exceeded(self) -> bool:
        return self.get_today_cost() >= self.daily_limit_usd

    def is_warning_threshold(self) -> bool:
        return self.get_today_cost() >= self._warning_threshold

    def raise_if_exceeded(self) -> None:
        if self.is_budget_exceeded():
            raise BudgetExceededError(
                f"Daily LLM budget of ${self.daily_limit_usd} exceeded. "
                "Falling back to keyword search."
            )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_cost_tracking.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/cost_tracking_service.py backend/tests/test_cost_tracking.py
git commit -m "feat: CostTrackingService — daily \$1 Bedrock budget cap"
```

---

## Task 3: LLMService (Amazon Bedrock)

**Files:**
- Create: `backend/services/llm_service.py`
- Create: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_llm_service.py`:
```python
import pytest
import json
import os
from unittest.mock import MagicMock, patch

os.environ["DB_PATH"] = ":memory:"
os.environ["AWS_REGION"] = "us-east-1"

from services.llm_service import LLMService, ParsedQuery


@pytest.fixture
def llm(mock_bedrock):
    import database; database.init_db()
    from services.cost_tracking_service import CostTrackingService
    tracker = CostTrackingService(daily_limit_usd=1.0)
    return LLMService(tracker=tracker)


@pytest.fixture
def mock_bedrock(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("boto3.client", lambda *a, **kw: mock_client)
    return mock_client


def _llama_response(text: str):
    return {"body": MagicMock(read=lambda: json.dumps({"generation": text}).encode())}


def _haiku_response(text: str):
    return {"body": MagicMock(read=lambda: json.dumps(
        {"content": [{"text": text}]}
    ).encode())}


def test_parse_query_siva_tatvam(llm, mock_bedrock):
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps({
        "topic": "Siva Tatvam",
        "scripture": None,
        "chapter": None,
        "sloka": None,
        "keywords": ["శివ తత్వం", "Shiva Tattva", "Siva philosophy"],
        "language": "Telugu",
        "search_intent": "conceptual discourse"
    }))
    result = llm.parse_query("Siva Tatvam", lang="Telugu")
    assert isinstance(result, ParsedQuery)
    assert result.topic == "Siva Tatvam"
    assert "శివ తత్వం" in result.keywords


def test_parse_query_specific_sloka(llm, mock_bedrock):
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps({
        "topic": "Bhagavad Gita",
        "scripture": "Bhagavad Gita",
        "chapter": 2,
        "sloka": 5,
        "keywords": ["BG 2.5", "భగవద్గీత 2వ అధ్యాయం 5వ శ్లోకం"],
        "language": "Telugu",
        "search_intent": "specific sloka"
    }))
    result = llm.parse_query("Bhagavad Gita Chapter 2 Sloka 5", lang="Telugu")
    assert result.chapter == 2
    assert result.sloka == 5


def test_generate_search_terms_returns_list(llm, mock_bedrock):
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=["శివ తత్వం", "Shiva Tattva"],
        language="Telugu", search_intent="conceptual discourse"
    )
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps([
        "Siva Tatvam Telugu discourse",
        "శివ తత్వం ప్రవచనం",
        "Shiva Tattva Telugu pravachanam"
    ]))
    terms = llm.generate_search_terms(parsed)
    assert len(terms) >= 2
    assert all(isinstance(t, str) for t in terms)


def test_rank_results_orders_by_score(llm, mock_bedrock):
    results = [
        {"title": "Random video", "speaker": "Unknown"},
        {"title": "Siva Tatvam discourse", "speaker": "Chaganti"},
    ]
    parsed = ParsedQuery(
        topic="Siva Tatvam", scripture=None, chapter=None, sloka=None,
        keywords=["Siva Tatvam"], language="Telugu", search_intent="discourse"
    )
    mock_bedrock.invoke_model.return_value = _llama_response(json.dumps([
        {"index": 0, "score": 0.2},
        {"index": 1, "score": 0.95},
    ]))
    ranked = llm.rank_results(results, parsed)
    assert ranked[0]["title"] == "Siva Tatvam discourse"


def test_fallback_on_budget_exceeded(llm, mock_bedrock):
    from services.cost_tracking_service import CostTrackingService
    import database; database.init_db()
    tracker = CostTrackingService(daily_limit_usd=0.0)  # already exceeded
    llm_exceeded = LLMService(tracker=tracker)
    result = llm_exceeded.parse_query("Siva Tatvam", lang="Telugu")
    assert result is None
    mock_bedrock.invoke_model.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_llm_service.py -v
```

Expected: `ImportError` — service not yet created.

- [ ] **Step 3: Implement `backend/services/llm_service.py`**

```python
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3

from services.cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)

LLAMA_MODEL = "meta.llama3-1-8b-instruct-v1:0"
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

# Approximate cost per 1k tokens (USD)
LLAMA_COST_PER_1K_IN = 0.0003
LLAMA_COST_PER_1K_OUT = 0.0006
HAIKU_COST_PER_1K_IN = 0.00025
HAIKU_COST_PER_1K_OUT = 0.00125


@dataclass
class ParsedQuery:
    topic: str
    scripture: str | None
    chapter: int | None
    sloka: int | None
    keywords: list[str] = field(default_factory=list)
    language: str = "Telugu"
    search_intent: str = "general"


class LLMService:
    def __init__(self, tracker: CostTrackingService):
        self.tracker = tracker
        region = os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def _call_llama(self, prompt: str) -> str:
        body = json.dumps({
            "prompt": (
                "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
                f"{prompt}"
                "<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
            ),
            "max_gen_len": 512,
            "temperature": 0.1,
        })
        resp = self._client.invoke_model(modelId=LLAMA_MODEL, body=body)
        raw = json.loads(resp["body"].read())
        text = raw.get("generation", "")
        tokens_in = len(prompt) // 4
        tokens_out = len(text) // 4
        cost = (tokens_in / 1000 * LLAMA_COST_PER_1K_IN +
                tokens_out / 1000 * LLAMA_COST_PER_1K_OUT)
        self.tracker.record(model=LLAMA_MODEL, tokens_in=tokens_in,
                            tokens_out=tokens_out, cost_usd=cost)
        return text

    def _call_haiku(self, prompt: str) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._client.invoke_model(modelId=HAIKU_MODEL, body=body)
        raw = json.loads(resp["body"].read())
        text = raw["content"][0]["text"]
        tokens_in = len(prompt) // 4
        tokens_out = len(text) // 4
        cost = (tokens_in / 1000 * HAIKU_COST_PER_1K_IN +
                tokens_out / 1000 * HAIKU_COST_PER_1K_OUT)
        self.tracker.record(model=HAIKU_MODEL, tokens_in=tokens_in,
                            tokens_out=tokens_out, cost_usd=cost)
        return text

    def _parse_json(self, text: str) -> Any:
        start = text.find("{") if "{" in text else text.find("[")
        end = text.rfind("}") if "{" in text else text.rfind("]")
        return json.loads(text[start:end + 1])

    def parse_query(self, query: str, lang: str) -> ParsedQuery | None:
        if self.tracker.is_budget_exceeded():
            logger.warning("LLM budget exceeded — skipping parse_query")
            return None
        prompt = (
            f"Parse this Sanatan Dharma search query into JSON.\n"
            f"Query: \"{query}\"\nLanguage preference: {lang}\n\n"
            "Return ONLY valid JSON with keys: topic, scripture (null if none), "
            "chapter (int or null), sloka (int or null), "
            "keywords (list of 3-5 strings including Telugu transliterations), "
            "language, search_intent.\n"
            "Example for 'Bhagavad Gita Chapter 2 Sloka 5':\n"
            '{"topic":"Bhagavad Gita","scripture":"Bhagavad Gita","chapter":2,"sloka":5,'
            '"keywords":["BG 2.5","భగవద్గీత అధ్యాయం 2 శ్లోకం 5"],'
            '"language":"Telugu","search_intent":"specific sloka"}'
        )
        try:
            text = self._call_llama(prompt)
            data = self._parse_json(text)
            return ParsedQuery(**data)
        except Exception as e:
            logger.error(f"parse_query failed: {e}")
            return None

    def generate_search_terms(self, parsed: ParsedQuery) -> list[str]:
        if self.tracker.is_budget_exceeded():
            return [parsed.topic]
        prompt = (
            f"Generate 4 YouTube/archive.org search queries for this Dharma topic.\n"
            f"Topic: {parsed.topic}, Scripture: {parsed.scripture}, "
            f"Chapter: {parsed.chapter}, Sloka: {parsed.sloka}, "
            f"Keywords: {parsed.keywords}, Language: {parsed.language}\n\n"
            "Return ONLY a JSON array of strings (search queries). "
            "Include Telugu script and English transliterations.\n"
            'Example: ["Siva Tatvam Telugu discourse","శివ తత్వం ప్రవచనం"]'
        )
        try:
            text = self._call_llama(prompt)
            return self._parse_json(text)
        except Exception as e:
            logger.error(f"generate_search_terms failed: {e}")
            return parsed.keywords[:3]

    def rank_results(self, results: list[dict], parsed: ParsedQuery) -> list[dict]:
        if self.tracker.is_budget_exceeded() or not results:
            return results
        items = [{"index": i, "title": r.get("title", ""), "speaker": r.get("speaker", "")}
                 for i, r in enumerate(results)]
        prompt = (
            f"Score these search results for relevance to: \"{parsed.topic}\" "
            f"(scripture={parsed.scripture}, chapter={parsed.chapter}, sloka={parsed.sloka}).\n"
            f"Results: {json.dumps(items)}\n\n"
            "Return ONLY a JSON array with objects {{index, score}} where score is 0.0–1.0.\n"
            'Example: [{"index":0,"score":0.9},{"index":1,"score":0.3}]'
        )
        try:
            text = self._call_llama(prompt)
            scores = {s["index"]: s["score"] for s in self._parse_json(text)}
            return sorted(results, key=lambda r: scores.get(results.index(r), 0), reverse=True)
        except Exception as e:
            logger.error(f"rank_results failed: {e}")
            return results

    def highlight_vyakhanams(self, texts: list[dict], parsed: ParsedQuery) -> list[dict]:
        if self.tracker.is_budget_exceeded() or not texts:
            return texts
        prompt = (
            f"For the topic \"{parsed.topic}\" "
            f"(scripture={parsed.scripture}, chapter={parsed.chapter}, sloka={parsed.sloka}), "
            f"identify the most relevant excerpt from each scholar's text below.\n"
            f"Scholars: {json.dumps([{'scholar': t['scholar'], 'text': t['text'][:500]} for t in texts])}\n\n"
            "Return ONLY a JSON array with objects {scholar, excerpt} — "
            "the excerpt should be the single most relevant sentence or passage (max 200 chars)."
        )
        try:
            text = self._call_haiku(prompt)
            highlights = {h["scholar"]: h["excerpt"] for h in self._parse_json(text)}
            for t in texts:
                t["highlight"] = highlights.get(t["scholar"], t["text"][:200])
            return texts
        except Exception as e:
            logger.error(f"highlight_vyakhanams failed: {e}")
            return texts
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_llm_service.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/llm_service.py backend/tests/test_llm_service.py
git commit -m "feat: LLMService — Bedrock Llama/Haiku for query parse, rank, highlight"
```

---

## Task 4: CacheService

**Files:**
- Create: `backend/services/cache_service.py`
- Create: `backend/tests/test_cache_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cache_service.py`:
```python
import json
import os
import time
import pytest

os.environ["DB_PATH"] = ":memory:"

from services.cache_service import CacheService


@pytest.fixture
def cache():
    import database; database.init_db()
    return CacheService(ttl_seconds=2)


def test_miss_on_empty(cache):
    assert cache.get("video", "siva tatvam", "Telugu") is None


def test_set_and_get(cache):
    data = [{"title": "Test Video", "speaker": "Scholar"}]
    cache.set("video", "siva tatvam", "Telugu", data)
    result = cache.get("video", "siva tatvam", "Telugu")
    assert result == data


def test_expired_returns_none(cache):
    data = [{"title": "Test"}]
    cache.set("audio", "gita", "Telugu", data)
    time.sleep(3)  # TTL is 2s in fixture
    assert cache.get("audio", "gita", "Telugu") is None


def test_different_lang_different_entry(cache):
    cache.set("video", "karma yoga", "Telugu", [{"title": "Telugu"}])
    cache.set("video", "karma yoga", "English", [{"title": "English"}])
    assert cache.get("video", "karma yoga", "Telugu")[0]["title"] == "Telugu"
    assert cache.get("video", "karma yoga", "English")[0]["title"] == "English"


def test_normalized_key(cache):
    cache.set("video", "  Siva Tatvam  ", "Telugu", [{"title": "x"}])
    assert cache.get("video", "siva tatvam", "Telugu") is not None
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_cache_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `backend/services/cache_service.py`**

```python
import json
import time
from database import db


class CacheService:
    def __init__(self, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds
        self._table_map = {
            "video": "video_cache",
            "audio": "audio_cache",
            "vyakhanam": "vyakhanam_cache",
        }

    def _normalize(self, key: str) -> str:
        return key.strip().lower()

    def get(self, kind: str, query_key: str, lang: str) -> list | None:
        table = self._table_map[kind]
        key = self._normalize(query_key)
        cutoff = time.time() - self.ttl_seconds
        with db() as conn:
            row = conn.execute(
                f"SELECT results_json FROM {table} "
                "WHERE query_key = ? AND lang = ? AND cached_at > ?",
                (key, lang, cutoff),
            ).fetchone()
        return json.loads(row["results_json"]) if row else None

    def set(self, kind: str, query_key: str, lang: str, results: list) -> None:
        table = self._table_map[kind]
        key = self._normalize(query_key)
        with db() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} "
                "(query_key, lang, results_json, cached_at) VALUES (?, ?, ?, ?)",
                (key, lang, json.dumps(results), time.time()),
            )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_cache_service.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/cache_service.py backend/tests/test_cache_service.py
git commit -m "feat: CacheService — SQLite cache with 24-hr TTL, normalized keys"
```

---

## Task 5: YouTubeService

**Files:**
- Create: `backend/services/youtube_service.py`
- Create: `backend/tests/test_youtube_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_youtube_service.py`:
```python
import pytest
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

from services.youtube_service import YouTubeService


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


def test_search_returns_normalized_results(svc, mock_youtube_build):
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "Siva Tatvam Telugu",
                "channelTitle": "Chaganti Official",
                "description": "Full discourse",
                "thumbnails": {"medium": {"url": "http://img.jpg"}},
            }
        }
    ])
    results = svc.search(["Siva Tatvam Telugu"], lang="Telugu", max_results=5)
    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"
    assert results[0]["speaker"] == "Chaganti Official"
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


def test_deduplicates_across_terms(svc, mock_youtube_build):
    item = {
        "id": {"videoId": "dup123"},
        "snippet": {"title": "Test", "channelTitle": "X",
                    "description": "", "thumbnails": {"medium": {"url": ""}}}
    }
    mock_youtube_build.search().list().execute.return_value = _make_yt_response([item])
    results = svc.search(["term1", "term2"], lang="Telugu", max_results=10)
    ids = [r["video_id"] for r in results]
    assert ids.count("dup123") == 1


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
        YouTubeService()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_youtube_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `backend/services/youtube_service.py`**

```python
import os
import logging
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

LANG_CODE = {"Telugu": "te", "English": "en", "Sanskrit": "sa", "Hindi": "hi"}


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
        return results
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_youtube_service.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/youtube_service.py backend/tests/test_youtube_service.py
git commit -m "feat: YouTubeService — search with deduplication and language filter"
```

---

## Task 6: ArchiveService

**Files:**
- Create: `backend/services/archive_service.py`
- Create: `backend/tests/test_archive_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_archive_service.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
import json
from services.archive_service import ArchiveService


@pytest.fixture
def svc():
    return ArchiveService()


def _mock_response(docs):
    m = MagicMock()
    m.json.return_value = {"response": {"docs": docs}}
    m.raise_for_status = MagicMock()
    return m


def test_search_returns_normalized_results(svc):
    doc = {
        "identifier": "siva-tatvam-telugu",
        "title": "Siva Tatvam Full",
        "creator": "Chaganti",
        "description": "Pravachanam",
        "avg_rating": 4.5,
    }
    with patch("requests.get", return_value=_mock_response([doc])):
        results = svc.search(["Siva Tatvam Telugu audio"], lang="Telugu")
    assert len(results) == 1
    assert results[0]["audio_url"].startswith("https://archive.org/download/")
    assert results[0]["speaker"] == "Chaganti"


def test_empty_docs_returns_empty(svc):
    with patch("requests.get", return_value=_mock_response([])):
        assert svc.search(["nothing"], lang="Telugu") == []


def test_deduplicates_across_terms(svc):
    doc = {"identifier": "dup", "title": "T", "creator": "X", "description": ""}
    with patch("requests.get", return_value=_mock_response([doc])):
        results = svc.search(["term1", "term2"], lang="Telugu")
    assert len(results) == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_archive_service.py -v
```

- [ ] **Step 3: Implement `backend/services/archive_service.py`**

```python
import logging
import requests

logger = logging.getLogger(__name__)
ARCHIVE_SEARCH_URL = "https://archive.org/advancedsearch.php"


class ArchiveService:
    def search(self, terms: list[str], lang: str, max_results: int = 10) -> list[dict]:
        seen = set()
        results = []
        for term in terms:
            try:
                resp = requests.get(
                    ARCHIVE_SEARCH_URL,
                    params={
                        "q": f"({term}) AND mediatype:audio",
                        "fl[]": ["identifier", "title", "creator", "description", "avg_rating"],
                        "output": "json",
                        "rows": max_results,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                for doc in resp.json().get("response", {}).get("docs", []):
                    ident = doc.get("identifier", "")
                    if ident in seen:
                        continue
                    seen.add(ident)
                    results.append({
                        "identifier": ident,
                        "title": doc.get("title", ident),
                        "speaker": doc.get("creator", "Unknown"),
                        "description": doc.get("description", ""),
                        "audio_url": f"https://archive.org/download/{ident}",
                        "page_url": f"https://archive.org/details/{ident}",
                        "rating": doc.get("avg_rating"),
                        "lang": lang,
                    })
            except Exception as e:
                logger.error(f"archive.org search failed for '{term}': {e}")
        return results
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_archive_service.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/archive_service.py backend/tests/test_archive_service.py
git commit -m "feat: ArchiveService — archive.org audio search with deduplication"
```

---

## Task 7: ScraperService (Vyakhanams)

**Files:**
- Create: `backend/services/scraper_service.py`
- Create: `backend/tests/test_scraper_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_scraper_service.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from services.scraper_service import ScraperService


@pytest.fixture
def svc():
    return ScraperService()


def _html(body: str) -> MagicMock:
    m = MagicMock()
    m.text = f"<html><body>{body}</body></html>"
    m.raise_for_status = MagicMock()
    return m


def test_scrape_returns_scholar_entries(svc):
    html = _html("<p>శివ తత్వం అంటే నిత్య సత్యం అని చెప్పారు.</p>")
    with patch("requests.get", return_value=html):
        results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert isinstance(results, list)


def test_respects_rate_limit(svc):
    import time
    html = _html("<p>test content here for testing purposes</p>")
    with patch("requests.get", return_value=html):
        with patch("time.sleep") as mock_sleep:
            svc.scrape("test", lang="Telugu")
    mock_sleep.assert_called()


def test_failed_request_skipped(svc):
    with patch("requests.get", side_effect=Exception("timeout")):
        results = svc.scrape("Siva Tatvam", lang="Telugu")
    assert results == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_scraper_service.py -v
```

- [ ] **Step 3: Implement `backend/services/scraper_service.py`**

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
        "content_selector": "p",
    },
    {
        "scholar": "Sri Sri Ravishankar",
        "affiliation": "artofliving.org",
        "url_template": "https://www.artofliving.org/in-en/search?q={query}",
        "lang": "Telugu",
        "content_selector": "p",
    },
    {
        "scholar": "Swami Sarvapriyananda",
        "affiliation": "vedantany.org",
        "url_template": "https://vedantany.org/?s={query}",
        "lang": "English",
        "content_selector": "p",
    },
]

HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}


class ScraperService:
    def scrape(self, query: str, lang: str, min_text_len: int = 80) -> list[dict]:
        results = []
        for source in SOURCES:
            time.sleep(1)  # respectful rate limiting
            url = source["url_template"].format(query=requests.utils.quote(query))
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [
                    p.get_text(strip=True)
                    for p in soup.select(source["content_selector"])
                    if len(p.get_text(strip=True)) > min_text_len
                ]
                if not paragraphs:
                    continue
                results.append({
                    "scholar": source["scholar"],
                    "affiliation": source["affiliation"],
                    "source_url": url,
                    "lang": source["lang"],
                    "text": " ".join(paragraphs[:3]),
                    "highlight": None,  # filled by LLMService.highlight_vyakhanams
                })
            except Exception as e:
                logger.error(f"Scrape failed for {source['scholar']}: {e}")
        return results
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_scraper_service.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/scraper_service.py backend/tests/test_scraper_service.py
git commit -m "feat: ScraperService — Vyakhanams from chaganti.net, artofliving, vedantany"
```

---

## Task 8: Search Router (`/api/search`)

**Files:**
- Create: `backend/routers/search.py`
- Create: `backend/tests/test_search_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_search_router.py`:
```python
import os, pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ["DB_PATH"] = ":memory:"
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-1")


@pytest.fixture
def client():
    import database; database.init_db()
    from main import app
    return TestClient(app)


VIDEO_RESULT = [{"video_id": "abc", "title": "Siva Tatvam", "speaker": "Chaganti",
                 "url": "https://youtube.com/watch?v=abc", "lang": "Telugu",
                 "description": "", "thumbnail": ""}]


def test_search_video_returns_results(client):
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
        mock_llm.tracker.is_warning_threshold.return_value = False
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["video_id"] == "abc"
    assert data["budget_warning"] is False


def test_search_returns_cache_on_hit(client):
    with patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = VIDEO_RESULT
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["results"][0]["video_id"] == "abc"


def test_search_fallback_on_llm_none(client):
    with patch("routers.search.llm_svc") as mock_llm, \
         patch("routers.search.yt_svc") as mock_yt, \
         patch("routers.search.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_llm.parse_query.return_value = None  # budget exceeded
        mock_yt.search.return_value = VIDEO_RESULT
        mock_llm.rank_results.return_value = VIDEO_RESULT
        mock_llm.tracker.is_warning_threshold.return_value = True
        response = client.get("/api/search?q=Siva+Tatvam&lang=Telugu&type=video")
    assert response.status_code == 200
    assert response.json()["budget_warning"] is True


def test_missing_query_returns_422(client):
    response = client.get("/api/search?lang=Telugu&type=video")
    assert response.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_search_router.py -v
```

- [ ] **Step 3: Implement `backend/routers/search.py`**

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
        return {"results": cached, "budget_warning": False, "from_cache": True}

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
    cache_svc.set(type, q, lang, results)

    return {
        "results": results,
        "budget_warning": tracker.is_warning_threshold(),
        "from_cache": False,
    }
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_search_router.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/search.py backend/tests/test_search_router.py
git commit -m "feat: /api/search — LLM-powered video/audio search with cache + fallback"
```

---

## Task 9: Vyakhanams Router (`/api/vyakhanams`)

**Files:**
- Create: `backend/routers/vyakhanams.py`
- Create: `backend/tests/test_vyakhanams_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vyakhanams_router.py`:
```python
import os, pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ["DB_PATH"] = ":memory:"
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-1")

SCHOLAR_RESULT = [{
    "scholar": "Chaganti", "affiliation": "chaganti.net",
    "text": "శివ తత్వం అంటే నిత్య సత్యం.", "highlight": "నిత్య సత్యం",
    "lang": "Telugu", "source_url": "https://chaganti.net"
}]


@pytest.fixture
def client():
    import database; database.init_db()
    from main import app
    return TestClient(app)


def test_vyakhanams_returns_results(client):
    with patch("routers.vyakhanams.scraper_svc") as mock_scraper, \
         patch("routers.vyakhanams.llm_svc") as mock_llm, \
         patch("routers.vyakhanams.cache_svc") as mock_cache:
        mock_cache.get.return_value = None
        mock_scraper.scrape.return_value = SCHOLAR_RESULT
        mock_llm.parse_query.return_value = MagicMock(topic="Siva Tatvam")
        mock_llm.highlight_vyakhanams.return_value = SCHOLAR_RESULT
        response = client.get("/api/vyakhanams?q=Siva+Tatvam&lang=Telugu")
    assert response.status_code == 200
    assert response.json()["results"][0]["scholar"] == "Chaganti"


def test_vyakhanams_cache_hit(client):
    with patch("routers.vyakhanams.cache_svc") as mock_cache:
        mock_cache.get.return_value = SCHOLAR_RESULT
        response = client.get("/api/vyakhanams?q=Siva+Tatvam&lang=Telugu")
    assert response.status_code == 200
    assert response.json()["from_cache"] is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_vyakhanams_router.py -v
```

- [ ] **Step 3: Implement `backend/routers/vyakhanams.py`**

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
    lang: str = Query("Telugu"),
):
    cached = cache_svc.get("vyakhanam", q, lang)
    if cached is not None:
        return {"results": cached, "from_cache": True}

    raw = scraper_svc.scrape(q, lang=lang)
    parsed = llm_svc.parse_query(q, lang=lang)
    results = llm_svc.highlight_vyakhanams(raw, parsed) if parsed and raw else raw
    cache_svc.set("vyakhanam", q, lang, results)

    return {"results": results, "from_cache": False}
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_vyakhanams_router.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Run full backend test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/vyakhanams.py backend/tests/test_vyakhanams_router.py
git commit -m "feat: /api/vyakhanams — scraped scholar text with LLM highlighting"
```

---

## Task 10: Expo App Scaffolding

**Files:**
- Create: `mobile/` (Expo project)
- Create: `mobile/constants/theme.ts`
- Create: `mobile/app.json`
- Create: `mobile/eas.json`

- [ ] **Step 1: Create Expo project**

```bash
cd C:\Users\schinta\SanatanaDharmaSpeeches
npx create-expo-app@latest mobile --template blank-typescript
cd mobile
```

- [ ] **Step 2: Install dependencies**

```bash
npx expo install expo-router expo-av expo-linear-gradient expo-status-bar
npx expo install react-native-safe-area-context react-native-screens
npx expo install react-native-youtube-iframe
npm install nativewind tailwindcss
npm install --save-dev @testing-library/react-native jest-expo
```

- [ ] **Step 3: Configure `mobile/app.json`**

Replace the generated `app.json` with:
```json
{
  "expo": {
    "name": "Sanatana Dharma Speeches",
    "slug": "sanatana-dharma-speeches",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "scheme": "dharmaspeech",
    "userInterfaceStyle": "dark",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#0d1117"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.dharmaspeech.app"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#0d1117"
      },
      "package": "com.dharmaspeech.app"
    },
    "web": {
      "bundler": "metro",
      "output": "static",
      "favicon": "./assets/favicon.png"
    },
    "plugins": ["expo-router"],
    "experiments": {
      "typedRoutes": true
    }
  }
}
```

- [ ] **Step 4: Configure `mobile/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0d1117", light: "#161b22", dark: "#090d13" },
        gold: { DEFAULT: "#e2a84b", light: "#f0c56a", dark: "#c48a2e" },
        border: "#21262d",
      },
    },
  },
};
```

- [ ] **Step 5: Create `mobile/constants/theme.ts`**

```typescript
export const COLORS = {
  bg: "#0d1117",
  bgLight: "#161b22",
  bgLighter: "#1c2128",
  border: "#21262d",
  gold: "#e2a84b",
  goldLight: "#f0c56a",
  goldDim: "#e2a84b22",
  text: "#c9d1d9",
  textMuted: "#8b949e",
  textDim: "#484f58",
  white: "#ffffff",
} as const;

export const SCHOLAR_COLORS = [
  "#e2a84b", "#4a9eff", "#7ee787", "#f78166", "#d2a8ff",
] as const;
```

- [ ] **Step 6: Create `mobile/eas.json`**

```json
{
  "cli": { "version": ">= 10.0.0" },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {}
  },
  "submit": {
    "production": {}
  }
}
```

- [ ] **Step 7: Verify Expo starts**

```bash
cd mobile
npx expo start --web
```

Expected: browser opens to blank Expo web app on `http://localhost:8081`.

- [ ] **Step 8: Commit**

```bash
cd ..
git add mobile/
git commit -m "feat: Expo app scaffold — expo-router, NativeWind, expo-av, eas config"
```

---

## Task 11: AppContext + API Client

**Files:**
- Create: `mobile/context/AppContext.tsx`
- Create: `mobile/api/client.ts`

- [ ] **Step 1: Create `mobile/api/client.ts`**

```typescript
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export interface VideoResult {
  video_id: string;
  title: string;
  speaker: string;
  description: string;
  thumbnail: string;
  url: string;
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

- [ ] **Step 2: Create `mobile/context/AppContext.tsx`**

```typescript
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
  loading: boolean;
  budgetWarning: boolean;
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
  const [loading, setLoading] = useState(false);
  const [budgetWarning, setBudgetWarning] = useState(false);
  const [currentPlayer, setCurrentPlayer] = useState<PlayerItem | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const [videoRes, audioRes, vyakhanamRes] = await Promise.all([
        api.searchVideos(q, language),
        api.searchAudio(q, language),
        api.getVyakhanams(q, language),
      ]);
      setVideos(videoRes.results);
      setAudio(audioRes.results);
      setVyakhanams(vyakhanamRes.results);
      setBudgetWarning(videoRes.budget_warning || audioRes.budget_warning);
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setLoading(false);
    }
  }, [language]);

  return (
    <AppContext.Provider value={{
      query, language, videos, audio, vyakhanams,
      loading, budgetWarning, currentPlayer,
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

- [ ] **Step 3: Commit**

```bash
cd mobile
git add context/ api/
git commit -m "feat: AppContext + typed API client for search and vyakhanams"
```

---

## Task 12: SearchBar + LanguageFilter Components

**Files:**
- Create: `mobile/components/SearchBar.tsx`
- Create: `mobile/components/LanguageFilter.tsx`

- [ ] **Step 1: Create `mobile/components/SearchBar.tsx`**

```typescript
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
      <View style={styles.inputRow}>
        <Text style={styles.icon}>🔍</Text>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder='Ask anything — "Siva Tatvam", "Bhagavad Gita Chapter 2 Sloka 5"...'
          placeholderTextColor={COLORS.textDim}
          onSubmitEditing={submit}
          returnKeyType="search"
          autoCorrect={false}
        />
        <TouchableOpacity style={styles.button} onPress={submit} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? "..." : "Search"}</Text>
        </TouchableOpacity>
      </View>
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
  inputRow: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: COLORS.bgLight,
    borderRadius: 28, borderWidth: 1.5, borderColor: COLORS.gold,
    paddingHorizontal: 16, paddingVertical: Platform.OS === "ios" ? 12 : 8,
    shadowColor: COLORS.gold, shadowOpacity: 0.15, shadowRadius: 12,
    elevation: 4,
  },
  icon: { fontSize: 16, marginRight: 8 },
  input: { flex: 1, color: COLORS.text, fontSize: 14 },
  button: {
    backgroundColor: COLORS.gold, borderRadius: 16,
    paddingHorizontal: 14, paddingVertical: 6, marginLeft: 8,
  },
  buttonText: { color: "#000", fontWeight: "700", fontSize: 12 },
  chips: { marginTop: 10 },
  chip: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: "#e2a84b33", borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 4, marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
```

- [ ] **Step 2: Create `mobile/components/LanguageFilter.tsx`**

```typescript
import React from "react";
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from "react-native";
import { Language } from "../context/AppContext";
import { COLORS } from "../constants/theme";

const LANGUAGES: Language[] = ["Telugu", "English", "Sanskrit", "Hindi"];

interface Props {
  selected: Language;
  onSelect: (lang: Language) => void;
}

export function LanguageFilter({ selected, onSelect }: Props) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}
      style={styles.scroll} contentContainerStyle={styles.row}>
      {LANGUAGES.map((lang) => {
        const active = lang === selected;
        return (
          <TouchableOpacity
            key={lang}
            style={[styles.pill, active && styles.pillActive]}
            onPress={() => onSelect(lang)}
          >
            <Text style={[styles.label, active && styles.labelActive]}>
              {lang === "Telugu" ? "🌐 " : ""}{lang}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { marginBottom: 8 },
  row: { paddingHorizontal: 16, gap: 8, flexDirection: "row" },
  pill: {
    borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.bgLight, paddingHorizontal: 14, paddingVertical: 5,
  },
  pillActive: { backgroundColor: COLORS.gold, borderColor: COLORS.gold },
  label: { color: COLORS.textMuted, fontSize: 12 },
  labelActive: { color: "#000", fontWeight: "700" },
});
```

- [ ] **Step 3: Commit**

```bash
git add components/SearchBar.tsx components/LanguageFilter.tsx
git commit -m "feat: SearchBar + LanguageFilter components with dark gold theme"
```

---

## Task 13: VideoPlaylist + AudioPlaylist Components

**Files:**
- Create: `mobile/components/VideoPlaylist.tsx`
- Create: `mobile/components/AudioPlaylist.tsx`

- [ ] **Step 1: Create `mobile/components/VideoPlaylist.tsx`**

```typescript
import React, { useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, Platform, Dimensions,
} from "react-native";
import YoutubePlayer from "react-native-youtube-iframe";
import { VideoResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

const { width } = Dimensions.get("window");

interface Props { videos: VideoResult[] }

export function VideoPlaylist({ videos }: Props) {
  const { setCurrentPlayer } = useApp();
  const [playingId, setPlayingId] = useState<string | null>(null);

  const play = (item: VideoResult) => {
    setPlayingId(item.video_id);
    setCurrentPlayer({ type: "video", item });
  };

  if (videos.length === 0) {
    return <Text style={styles.empty}>No videos found</Text>;
  }

  return (
    <FlatList
      data={videos}
      keyExtractor={(item) => item.video_id}
      scrollEnabled={false}
      renderItem={({ item }) => (
        <View style={[styles.row, playingId === item.video_id && styles.rowActive]}>
          {playingId === item.video_id && Platform.OS !== "web" ? (
            <YoutubePlayer
              height={200}
              width={width - 32}
              play
              videoId={item.video_id}
              onChangeState={(state) => {
                if (state === "ended") setPlayingId(null);
              }}
            />
          ) : null}
          {playingId === item.video_id && Platform.OS === "web" ? (
            <iframe
              width="100%"
              height="200"
              src={`https://www.youtube.com/embed/${item.video_id}?autoplay=1`}
              allow="autoplay; encrypted-media"
              allowFullScreen
              style={{ border: "none", borderRadius: 6 }}
            />
          ) : null}
          <TouchableOpacity style={styles.meta} onPress={() => play(item)}>
            <View style={styles.playBtn}>
              <Text style={styles.playIcon}>▶</Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
              <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
            </View>
            {playingId === item.video_id && (
              <View style={styles.badge}><Text style={styles.badgeText}>Playing</Text></View>
            )}
          </TouchableOpacity>
        </View>
      )}
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

- [ ] **Step 2: Create `mobile/components/AudioPlaylist.tsx`**

```typescript
import React, { useState, useRef } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
} from "react-native";
import { Audio } from "expo-av";
import { AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

interface Props { audio: AudioResult[] }

export function AudioPlaylist({ audio }: Props) {
  const { setCurrentPlayer } = useApp();
  const [playingId, setPlayingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);

  const play = async (item: AudioResult) => {
    try {
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
      const { sound } = await Audio.Sound.createAsync(
        { uri: item.audio_url },
        { shouldPlay: true }
      );
      soundRef.current = sound;
      setPlayingId(item.identifier);
      setCurrentPlayer({ type: "audio", item });
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setPlayingId(null);
          setCurrentPlayer(null);
        }
      });
    } catch (e) {
      console.error("Audio play failed:", e);
    }
  };

  const stop = async () => {
    if (soundRef.current) {
      await soundRef.current.stopAsync();
      await soundRef.current.unloadAsync();
      soundRef.current = null;
    }
    setPlayingId(null);
    setCurrentPlayer(null);
  };

  if (audio.length === 0) {
    return <Text style={styles.empty}>No audio found</Text>;
  }

  return (
    <FlatList
      data={audio}
      keyExtractor={(item) => item.identifier}
      scrollEnabled={false}
      renderItem={({ item }) => {
        const active = playingId === item.identifier;
        return (
          <TouchableOpacity
            style={[styles.row, active && styles.rowActive]}
            onPress={() => active ? stop() : play(item)}
          >
            <View style={[styles.iconBox, active && styles.iconBoxActive]}>
              <Text style={styles.icon}>{active ? "⏸" : "🎵"}</Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
              <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
            </View>
          </TouchableOpacity>
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
    flexDirection: "row", alignItems: "center",
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
});
```

- [ ] **Step 3: Commit**

```bash
git add components/VideoPlaylist.tsx components/AudioPlaylist.tsx
git commit -m "feat: VideoPlaylist (YouTube) + AudioPlaylist (expo-av) components"
```

---

## Task 14: StickyPlayer Component

**Files:**
- Create: `mobile/components/StickyPlayer.tsx`

- [ ] **Step 1: Create `mobile/components/StickyPlayer.tsx`**

```typescript
import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "../context/AppContext";
import { COLORS } from "../constants/theme";

export function StickyPlayer() {
  const { currentPlayer, setCurrentPlayer } = useApp();
  const insets = useSafeAreaInsets();

  if (!currentPlayer) return null;

  const title = currentPlayer.type === "video"
    ? currentPlayer.item.title
    : currentPlayer.item.title;
  const speaker = currentPlayer.type === "video"
    ? currentPlayer.item.speaker
    : currentPlayer.item.speaker;

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      <View style={styles.thumb}>
        <Text style={styles.thumbIcon}>
          {currentPlayer.type === "video" ? "▶" : "🎵"}
        </Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <Text style={styles.speaker} numberOfLines={1}>{speaker}</Text>
        <View style={styles.progressBar}>
          <View style={styles.progressFill} />
        </View>
      </View>
      <TouchableOpacity onPress={() => setCurrentPlayer(null)} style={styles.closeBtn}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    backgroundColor: COLORS.bgLight,
    borderTopWidth: 1, borderTopColor: COLORS.border,
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingTop: 8,
    elevation: 10, zIndex: 100,
  },
  thumb: {
    width: 44, height: 36, backgroundColor: COLORS.bg,
    borderRadius: 4, alignItems: "center", justifyContent: "center", marginRight: 10,
  },
  thumbIcon: { color: COLORS.gold, fontSize: 16 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 11, fontWeight: "600" },
  speaker: { color: COLORS.textMuted, fontSize: 10 },
  progressBar: {
    height: 3, backgroundColor: COLORS.border, borderRadius: 2, marginTop: 4,
  },
  progressFill: {
    width: "30%", height: "100%",
    backgroundColor: COLORS.gold, borderRadius: 2,
  },
  closeBtn: { padding: 8 },
  closeText: { color: COLORS.textMuted, fontSize: 14 },
});
```

- [ ] **Step 2: Commit**

```bash
git add components/StickyPlayer.tsx
git commit -m "feat: StickyPlayer — fixed bottom bar with safe area insets"
```

---

## Task 15: VyakhanamsPanel Component

**Files:**
- Create: `mobile/components/VyakhanamsPanel.tsx`

- [ ] **Step 1: Create `mobile/components/VyakhanamsPanel.tsx`**

```typescript
import React, { useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity,
  Modal, StyleSheet, SafeAreaView,
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
  modal: { flex: 1, backgroundColor: COLORS.bg },
  modalHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  modalTitle: { color: COLORS.text, fontSize: 16, fontWeight: "700" },
  closeText: { color: COLORS.gold, fontSize: 13 },
});
```

- [ ] **Step 2: Commit**

```bash
git add components/VyakhanamsPanel.tsx
git commit -m "feat: VyakhanamsPanel — scrollable scholar text with full-screen modal"
```

---

## Task 16: App Screens — Root Layout + Home Screen

**Files:**
- Create: `mobile/app/_layout.tsx`
- Create: `mobile/app/index.tsx`

- [ ] **Step 1: Create `mobile/app/_layout.tsx`**

```typescript
import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AppProvider } from "../context/AppContext";
import { StickyPlayer } from "../components/StickyPlayer";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: "#0d1117" },
            headerTintColor: "#e2a84b",
            headerTitleStyle: { fontWeight: "700" },
            contentStyle: { backgroundColor: "#0d1117" },
          }}
        >
          <Stack.Screen
            name="index"
            options={{ title: "🕉 Sanatana Dharma Speeches" }}
          />
          <Stack.Screen
            name="vyakhanam/[id]"
            options={{ title: "Vyakhanam", presentation: "modal" }}
          />
        </Stack>
        <StickyPlayer />
      </AppProvider>
    </SafeAreaProvider>
  );
}
```

- [ ] **Step 2: Create `mobile/app/index.tsx`**

```typescript
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
import { COLORS } from "../constants/theme";

type ResultTab = "video" | "audio";

export default function HomeScreen() {
  const { videos, audio, vyakhanams, loading, budgetWarning, language, setLanguage, search } =
    useApp();
  const [tab, setTab] = useState<ResultTab>("video");
  const hasResults = videos.length > 0 || audio.length > 0;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <Text style={styles.subtitle}>EXPLORE DHARMIC KNOWLEDGE</Text>
        <SearchBar onSearch={search} loading={loading} />
        <LanguageFilter selected={language} onSelect={setLanguage} />
      </View>

      {budgetWarning && (
        <View style={styles.warningBanner}>
          <Text style={styles.warningText}>
            ⚠️ Enhanced search paused — results shown as-is
          </Text>
        </View>
      )}

      {hasResults && (
        <>
          {/* ── Section 1: Videos & Audio ── */}
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

          {/* ── Decorative Divider ── */}
          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerSymbol}>✦ ✦ ✦</Text>
            <View style={styles.dividerLine} />
          </View>

          {/* ── Section 2: Vyakhanams ── */}
          <VyakhanamsPanel vyakhanams={vyakhanams} />
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { paddingBottom: 120 },
  hero: { paddingTop: 16 },
  subtitle: {
    textAlign: "center", color: COLORS.gold, fontSize: 10,
    letterSpacing: 2, opacity: 0.7, marginBottom: 8,
  },
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

- [ ] **Step 3: Verify the app runs on web**

```bash
cd mobile
npx expo start --web
```

Expected: browser shows the dark-themed home screen with search bar, language filter, and ✦ ✦ ✦ divider visible on results.

- [ ] **Step 4: Run on mobile simulator**

```bash
npx expo start --ios    # macOS only
npx expo start --android
```

Expected: app loads with dark navy background, gold search bar.

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat: Home screen + root layout — full UI wired to AppContext"
```

---

## Task 17: Backend `.env` + Final Integration + EAS Build Setup

**Files:**
- Create: `backend/.env.example`
- Create: `mobile/.env.example`

- [ ] **Step 1: Create `backend/.env.example`**

```
YOUTUBE_API_KEY=your_youtube_data_api_v3_key_here
AWS_REGION=us-east-1
DAILY_LLM_BUDGET_USD=1.0
DB_PATH=dharma.db
```

- [ ] **Step 2: Create `mobile/.env.example`**

```
EXPO_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Create `backend/.env` from example**

```bash
cd backend
copy .env.example .env
# Fill in YOUTUBE_API_KEY with your actual key
# AWS credentials come from IAM role on EC2 (no key needed in .env on prod)
```

- [ ] **Step 4: Create `mobile/.env` from example**

```bash
cd mobile
copy .env.example .env
```

- [ ] **Step 5: Run full backend test suite**

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 6: Start backend and test the API manually**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

In another terminal:
```bash
curl "http://localhost:8000/health"
# Expected: {"status":"ok"}

curl "http://localhost:8000/api/search?q=Siva+Tatvam&lang=Telugu&type=video"
# Expected: {"results":[...],"budget_warning":false,"from_cache":false}
```

- [ ] **Step 7: Start Expo and verify full flow**

```bash
cd mobile
npx expo start --web
```

Open `http://localhost:8081`, type "Siva Tatvam" in search, press Search.
Expected: videos section populates, Vyakhanams section populates below divider.

- [ ] **Step 8: Add `.gitignore` entries**

Add to root `.gitignore`:
```
backend/.env
backend/dharma.db
backend/.venv/
mobile/.env
mobile/node_modules/
mobile/.expo/
.superpowers/
```

- [ ] **Step 9: Set up EAS Build (for App Store/Play Store)**

```bash
cd mobile
npm install -g eas-cli
eas login          # log in with your Expo account
eas build:configure
```

To build for production:
```bash
eas build --platform ios --profile production
eas build --platform android --profile production
```

To submit to stores:
```bash
eas submit --platform ios
eas submit --platform android
```

- [ ] **Step 10: Final commit**

```bash
cd ..
git add .
git commit -m "feat: complete SanatanaDharmaSpeeches — Expo app + FastAPI backend

- LLM search via Amazon Bedrock (Llama 3.1 8B + Claude Haiku)
- \$1/day cost cap with graceful keyword fallback
- YouTube video + archive.org audio results
- Separate Vyakhanams scholar text section
- Dark spiritual theme, Telugu by default
- EAS Build ready for App Store + Play Store"
```

---

## Self-Review Checklist

### Spec Coverage
| Requirement | Task |
|---|---|
| Copilot-style large search bar | Task 12 (SearchBar) |
| YouTube video results with speaker name | Task 5, 8, 13 |
| Audio results with speaker name | Task 6, 8, 13 |
| Specific search (scripture/chapter/sloka) | Task 3 (LLMService.parse_query) |
| In-page playback | Task 13 (VideoPlaylist + AudioPlaylist) |
| Playlist-style display | Task 13, 16 |
| LLM search via Bedrock | Task 3 |
| Language filter (Telugu default) | Task 12 (LanguageFilter) |
| Vyakhanams separate section | Task 7, 9, 15 |
| Sticky bottom player | Task 14 |
| $1/day cost cap + fallback | Task 2 |
| Dark spiritual theme | Task 10, 12–16 |
| Expo iOS + Android + Web | Task 10 |
| EAS Build publish | Task 17 |
| AWS backend (EC2 + Bedrock IAM) | Task 17 |
