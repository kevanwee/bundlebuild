import hashlib

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from bundlebuild.build import build
from bundlebuild.manifest import Document, Manifest


def fixture(tmp_path, **doc):
    source = tmp_path / "source.pdf"
    c = canvas.Canvas(str(source))
    c.drawString(50, 500, "Original source evidence")
    c.save()
    return Manifest(title="Bundle", base_dir=tmp_path, stamp={"prefix": "AB"}, sections=[{
        "title": "Documents", "documents": [{"tab": "1", "title": "Source",
                                               "file": "source.pdf", **doc}]}])


def test_repeated_page_has_distinct_stamps_and_unchanged_source(tmp_path):
    m = fixture(tmp_path, pages="1,1")
    source = tmp_path / "source.pdf"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = build(m)
    reader = PdfReader(result.output)
    assert "AB-1" in reader.pages[result.index_pages].extract_text()
    assert "AB-2" not in reader.pages[result.index_pages].extract_text()
    assert "AB-2" in reader.pages[result.index_pages + 1].extract_text()
    assert "AB-1" not in reader.pages[result.index_pages + 1].extract_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_rotated_page_and_long_index_title(tmp_path):
    title = "An extended description of the evidence " * 10 + "FINAL WORDS"
    m = fixture(tmp_path, title=title)
    source = tmp_path / "source.pdf"
    writer = PdfWriter(clone_from=source)
    writer.pages[0].rotate(90)
    writer.write(source)
    result = build(m)
    reader = PdfReader(result.output)
    assert "FINAL WORDS" in " ".join(p.extract_text() for p in reader.pages[:result.index_pages])
    assert reader.pages[result.index_pages].rotation == 0


def test_sources_cannot_be_overwritten_even_with_skip_check(tmp_path):
    m = fixture(tmp_path)
    m.output = tmp_path / "source.pdf"
    with pytest.raises(ValueError, match="overwrite"):
        build(m, skip_check=True)


def test_descending_or_empty_selection_is_invalid():
    with pytest.raises(ValueError):
        Document(tab="1", title="test", file="a.pdf", pages="3-1").page_selection(3)
    with pytest.raises(ValueError):
        Document(tab="1", title="test", file="a.pdf").page_selection(0)
