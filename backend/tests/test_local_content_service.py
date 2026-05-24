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


def test_fts5_syncs_on_insert():
    """Verify that inserting into local_content makes it searchable via FTS5."""
    with database.db() as conn:
        conn.execute(
            "INSERT INTO local_content (pdf_key, category, title, page_number, content) "
            "VALUES (?, ?, ?, ?, ?)",
            ("pdfs/Veda/Rigveda.pdf", "Veda", "Rigveda", 1, "అగ్ని మీళే పురోహితం"),
        )

    with database.db() as conn:
        rows = conn.execute(
            "SELECT lc.title FROM local_content_fts "
            "JOIN local_content lc ON local_content_fts.rowid = lc.id "
            'WHERE local_content_fts MATCH \'"అగ్ని"\' '
        ).fetchall()

    assert len(rows) >= 1
    assert rows[0]["title"] == "Rigveda"


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
    # FTS5 triggers handle sync automatically (no manual rebuild needed)


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
def svc(fresh_db):
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

