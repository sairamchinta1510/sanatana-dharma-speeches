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

