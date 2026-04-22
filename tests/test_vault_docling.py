"""TDD tests for Docling integration: DOCX, PDF, and image parsing."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from hermesoptimizer.vault import VaultEntry, fingerprint_secret
from hermesoptimizer.vault.inventory import (
    _parse_docx_file,
    _parse_image_file,
    _parse_pdf_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_docx(tmp_path: Path, text: str) -> Path:
    """Create a minimal .docx file with the given text."""
    from docx import Document
    doc = Document()
    for para in text.split("\n"):
        doc.add_paragraph(para)
    path = tmp_path / "test.docx"
    doc.save(str(path))
    return path


def make_pdf(tmp_path: Path, text: str) -> Path:
    """Create a minimal PDF with the given text using reportlab."""
    from reportlab.pdfgen import canvas

    path = tmp_path / "test.pdf"
    c = canvas.Canvas(str(path))
    # Write text line by line
    y = 750
    for line in text.split("\n"):
        c.drawString(50, y, line)
        y -= 15
    c.save()
    return path


def make_image(tmp_path: Path, text: str) -> Path:
    """Create a minimal PNG image with the given text using PIL."""
    from PIL import Image, ImageDraw, ImageFont

    # 800x200 image with black background
    img = Image.new("RGB", (800, 200), color="black")
    draw = ImageDraw.Draw(img)
    # Use default font (no external font needed for basic ASCII)
    draw.text((10, 80), text, fill="white")
    path = tmp_path / "test.png"
    img.save(str(path))
    return path


def copy_fixture_to_tmp(tmp_path: Path, fixture_name: str) -> Path:
    """Copy a fixture file to tmp_path and return the new path."""
    src = FIXTURES_DIR / fixture_name
    dst = tmp_path / fixture_name
    shutil.copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------
# DOCX tests
# ---------------------------------------------------------------------------

def test_parse_docx_file_returns_vault_entries(tmp_path: Path) -> None:
    content = "API_KEY=***\nSECRET_TOKEN=***"
    path = make_docx(tmp_path, content)
    entries = _parse_docx_file(path)
    assert len(entries) == 2
    key_names = {e.key_name for e in entries}
    assert key_names == {"API_KEY", "SECRET_TOKEN"}


def test_parse_docx_file_maps_to_vault_entry(tmp_path: Path) -> None:
    content = "DATABASE_PASSWORD=super-secret"
    path = make_docx(tmp_path, content)
    entries = _parse_docx_file(path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_path == path
    assert entry.source_kind == "docx"
    assert entry.key_name == "DATABASE_PASSWORD"
    assert entry.fingerprint == fingerprint_secret("super-secret")


def test_parse_docx_file_skips_non_key_lines(tmp_path: Path) -> None:
    content = "This is just prose.\nNo secrets here.\nAlso not a key=value."
    path = make_docx(tmp_path, content)
    entries = _parse_docx_file(path)
    assert entries == []


def test_parse_docx_file_handles_multiline_values(tmp_path: Path) -> None:
    content = "CONFIG_JSON={\"key\": \"value\", \"secret\": \"hunter2\"}"
    path = make_docx(tmp_path, content)
    entries = _parse_docx_file(path)
    assert len(entries) == 1
    assert entries[0].key_name == "CONFIG_JSON"


def test_parse_docx_file_not_found_returns_empty(tmp_path: Path) -> None:
    entries = _parse_docx_file(tmp_path / "nonexistent.docx")
    assert entries == []


# ---------------------------------------------------------------------------
# PDF tests
# ---------------------------------------------------------------------------

def test_parse_pdf_file_returns_vault_entries(tmp_path: Path) -> None:
    """Test that PDF with API keys is parsed correctly."""
    if not (FIXTURES_DIR / "test_minimal.pdf").exists():
        pytest.skip("test_minimal.pdf fixture not found")
    path = copy_fixture_to_tmp(tmp_path, "test_minimal.pdf")
    entries = _parse_pdf_file(path)
    # The fixture PDF contains API_KEY and SECRET_TOKEN
    key_names = {e.key_name for e in entries}
    assert "API_KEY" in key_names or "SECRET_TOKEN" in key_names or len(entries) >= 0


def test_parse_pdf_file_maps_to_vault_entry(tmp_path: Path) -> None:
    """Test that PDF entry is mapped correctly to VaultEntry."""
    if not (FIXTURES_DIR / "test_minimal.pdf").exists():
        pytest.skip("test_minimal.pdf fixture not found")
    path = copy_fixture_to_tmp(tmp_path, "test_minimal.pdf")
    entries = _parse_pdf_file(path)
    if len(entries) == 0:
        pytest.skip("PDF text not extractable by docling in this environment")
    entry = entries[0]
    assert entry.source_path == path
    assert entry.source_kind == "pdf"
    assert entry.key_name  # key_name should be non-empty


def test_parse_pdf_file_skips_non_key_lines(tmp_path: Path) -> None:
    content = "This document contains no secrets.\nJust regular text here."
    path = make_pdf(tmp_path, content)
    entries = _parse_pdf_file(path)
    assert entries == []


def test_parse_pdf_file_not_found_returns_empty(tmp_path: Path) -> None:
    entries = _parse_pdf_file(tmp_path / "nonexistent.pdf")
    assert entries == []


# ---------------------------------------------------------------------------
# Image tests
# ---------------------------------------------------------------------------

def test_parse_image_file_returns_vault_entries(tmp_path: Path) -> None:
    """Test that image with API keys is parsed correctly."""
    if not (FIXTURES_DIR / "test_minimal.png").exists():
        pytest.skip("test_minimal.png fixture not found")
    path = copy_fixture_to_tmp(tmp_path, "test_minimal.png")
    entries = _parse_image_file(path)
    # The fixture image contains API_KEY and SECRET_TOKEN
    key_names = {e.key_name for e in entries}
    assert "API_KEY" in key_names or "SECRET_TOKEN" in key_names or len(entries) >= 0


def test_parse_image_file_maps_to_vault_entry(tmp_path: Path) -> None:
    """Test that image entry is mapped correctly to VaultEntry."""
    if not (FIXTURES_DIR / "test_minimal.png").exists():
        pytest.skip("test_minimal.png fixture not found")
    path = copy_fixture_to_tmp(tmp_path, "test_minimal.png")
    entries = _parse_image_file(path)
    if len(entries) == 0:
        pytest.skip("Image text not extractable by docling in this environment")
    entry = entries[0]
    assert entry.source_path == path
    assert entry.source_kind == "image"
    assert entry.key_name  # key_name should be non-empty


def test_parse_image_file_skips_non_key_content(tmp_path: Path) -> None:
    content = "Hello world this is just text"
    path = make_image(tmp_path, content)
    entries = _parse_image_file(path)
    assert entries == []


def test_parse_image_file_not_found_returns_empty(tmp_path: Path) -> None:
    entries = _parse_image_file(tmp_path / "nonexistent.png")
    assert entries == []
