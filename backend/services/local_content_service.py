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
                "ORDER BY page_number ASC "
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
                            "ORDER BY rank ASC "
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

    def _build_fts_query(self, *queries: str) -> str:
        """Build a safe FTS5 OR query from one or more query strings."""
        terms: list[str] = []
        seen: set[str] = set()
        for q in queries:
            for word in q.split():
                word = word.strip('.,;:?!()"\'।')
                if len(word) >= 2 and word not in seen:
                    seen.add(word)
                    word = word.replace('"', '""')  # FTS5 quote escaping
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
