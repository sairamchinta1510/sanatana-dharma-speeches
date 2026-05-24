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
