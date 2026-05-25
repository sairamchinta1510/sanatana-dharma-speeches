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
