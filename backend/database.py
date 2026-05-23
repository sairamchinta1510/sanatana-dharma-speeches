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
