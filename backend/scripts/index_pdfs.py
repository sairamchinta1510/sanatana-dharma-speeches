"""One-time script: extract zips -> upload PDFs to S3 -> index text in SQLite FTS5.

Usage:
    cd backend
    python scripts/index_pdfs.py

Re-running is safe: existing S3 objects and indexed PDFs are skipped.
"""

import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path

import boto3
import pdfplumber
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BUCKET = os.getenv("LOCAL_CONTENT_BUCKET", "sanatana-dharma-content")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DOWNLOADS_DIR = Path.home() / "Downloads"
CHUNK_SIZE = 500
EXTRACT_DIR = Path(__file__).resolve().parent.parent / ".index_pdfs_tmp"

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
    """'Garuda Purana Telgu.pdf' -> 'Garuda Purana'"""
    name = Path(filename).stem
    for suffix in (" Telugu", " Telgu", "Telugu", "Telgu", "-2", "-1"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split text into <=size-char chunks, preferring sentence boundaries."""
    chunks: list[str] = []
    text = text.strip()
    while len(text) > size:
        split_at = size
        for sep in ("।", ".", "\n", " "):
            pos = text.rfind(sep, 0, size + 1)
            if pos != -1:
                split_at = pos + 1
                break
        if split_at == size:
            for sep in ("।", ".", "\n", " "):
                pos = text.find(sep, size, min(len(text), size + 51))
                if pos != -1:
                    split_at = pos + 1
                    break
        chunk = text[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
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
        code = exc.response["Error"]["Code"]
        if code == "404":
            s3.upload_file(str(pdf_path), BUCKET, s3_key)
            logger.info("  Uploaded to S3: %s", s3_key)
            return True
        logger.warning("  S3 error for %s (code %s): %s", s3_key, code, exc)
        return False


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
            "  No text extracted from %s - may be a scanned image PDF", pdf_path.name
        )
    return chunks_inserted


def sync_fts(conn) -> None:
    """Rebuild FTS5 index from local_content source table."""
    conn.execute("INSERT INTO local_content_fts(local_content_fts) VALUES('rebuild')")
    logger.info("FTS5 index rebuilt")


def _reset_extract_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


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

    _reset_extract_dir(EXTRACT_DIR)
    try:
        for zip_path in zips:
            logger.info("Processing: %s", zip_path.name)
            with zipfile.ZipFile(zip_path) as zf:
                # Validate members to prevent path traversal
                extract_target = EXTRACT_DIR.resolve()
                for member in zf.namelist():
                    member_path = (EXTRACT_DIR / member).resolve()
                    if not str(member_path).startswith(str(extract_target)):
                        raise ValueError(f"Refusing to extract member outside target dir: {member}")
                zf.extractall(EXTRACT_DIR)

            for folder_name, category in CATEGORY_MAP.items():
                folder = EXTRACT_DIR / folder_name
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

            for item in EXTRACT_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    finally:
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)

    with db() as conn:
        sync_fts(conn)

    logger.info("Done. Total chunks indexed: %d", total_chunks)


if __name__ == "__main__":
    main()
