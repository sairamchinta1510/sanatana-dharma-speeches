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
