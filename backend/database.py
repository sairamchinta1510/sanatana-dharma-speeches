import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "dharma.db")
_memory_conn = None


def get_connection() -> sqlite3.Connection:
    global _memory_conn
    if DB_PATH == ":memory:":
        if _memory_conn is None:
            _memory_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _memory_conn.row_factory = sqlite3.Row
        return _memory_conn
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
        if DB_PATH != ":memory:":
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
