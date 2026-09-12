"""End-to-end: generate PDFs, write a manifest, check, build, inspect the output."""

import io
from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from bundlebuild import build, check, load_manifest
from bundlebuild.cli import main


def make_pdf(path: Path, pages: int, *, text: bool = True, land: bool = False) -> None:
    c = canvas.Canvas(str(path), pagesize=landscape(A4) if land else A4)
    for i in range(pages):
        if text:
            c.drawString(72, 700, f"{path.stem} page {i + 1} lorem ipsum dolor sit amet")
        else:
            c.rect(72, 600, 200, 100)  # a scanned page has drawing but no text
        c.showPage()
    c.save()


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    make_pdf(docs / "soc.pdf", 3)
    make_pdf(docs / "defence.pdf", 2)
    make_pdf(docs / "letter.pdf", 4)
    make_pdf(docs / "scan.pdf", 1, text=False)
    make_pdf(docs / "plan.pdf", 1, land=True)
    manifest = {
        "title": "Bundle of Documents",
        "case": "HC/OC 123/2026",
        "parties": "Alpha v Beta",
        "output": "out/bundle.pdf",
        "stamp": {"prefix": "AB"},
        "sections": [
            {"title": "Pleadings", "documents": [
                {"tab": "1", "title": "Statement of Claim", "date": "2026-03-02",
                 "file": "docs/soc.pdf"},
                {"tab": "2", "title": "Defence", "date": "2026-03-23", "file": "docs/defence.pdf"},
            ]},
            {"title": "Correspondence", "documents": [
                {"tab": "3", "title": "Letter", "file": "docs/letter.pdf", "pages": "1-2,4"},
                {"tab": "4", "title": "Scanned receipt", "date": "2025-01-01",
                 "file": "docs/scan.pdf"},
                {"tab": "5", "title": "Site plan", "date": "2025-01-01", "file": "docs/plan.pdf",
                 "citation": "[2020] SGHC 1"},
            ]},
        ],
    }
    (tmp_path / "bundle.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return tmp_path


def test_check_reports_warnings_not_errors(bundle_dir):
    rep = check(load_manifest(bundle_dir / "bundle.yaml"))
    assert rep.ok
    msgs = [f.message for f in rep.findings]
    assert any("no text layer on any page" in m for m in msgs)  # scan.pdf
    assert any("landscape" in m for m in msgs)  # plan.pdf
    assert any("undated" in m for m in msgs)  # letter
    assert rep.total_pages == 3 + 2 + 3 + 1 + 1


def test_check_missing_file_is_error(bundle_dir):
    (bundle_dir / "docs" / "defence.pdf").unlink()
    rep = check(load_manifest(bundle_dir / "bundle.yaml"))
    assert not rep.ok
    assert any("file not found" in f.message for f in rep.errors)


def test_duplicate_tab_rejected(bundle_dir):
    raw = yaml.safe_load((bundle_dir / "bundle.yaml").read_text())
    raw["sections"][0]["documents"][1]["tab"] = "1"
    (bundle_dir / "bundle.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(Exception, match="duplicate tab"):
        load_manifest(bundle_dir / "bundle.yaml")


def test_build_pages_stamps_links_bookmarks(bundle_dir):
    m = load_manifest(bundle_dir / "bundle.yaml")
    res = build(m)
    assert res.content_pages == 10
    assert res.index_pages == 1
    assert [(r.doc.tab, r.first, r.last) for r in res.rows] == [
        ("1", 1, 3), ("2", 4, 5), ("3", 6, 8), ("4", 9, 9), ("5", 10, 10)]

    reader = PdfReader(str(res.output))
    assert len(reader.pages) == 11
    # stamps: bundle page 1 is PDF page index 1 (after the index)
    assert "AB-1" in reader.pages[1].extract_text()
    assert "AB-10" in reader.pages[10].extract_text()
    # letter page selection 1-2,4: pdf page for bundle page 8 should be letter's page 4
    assert "letter page 4" in reader.pages[8].extract_text()
    # index text
    idx = reader.pages[0].extract_text()
    assert "Statement of Claim" in idx and "6-8" in idx and "[2020] SGHC 1" in idx
    # links on the index page, one per document
    annots = reader.pages[0].get("/Annots") or []
    assert len(annots) == 5
    # outline: 2 sections with children
    outline = reader.outline
    titles = [o.title for o in outline if not isinstance(o, list)]
    assert titles == ["Pleadings", "Correspondence"]
    # sidecars
    assert res.output.with_suffix(".index.json").exists()
    cm = res.output.with_suffix(".citecheck.json")
    assert cm.exists() and "[2020] SGHC 1" in cm.read_text()


def test_build_refuses_on_error(bundle_dir):
    (bundle_dir / "docs" / "soc.pdf").unlink()
    with pytest.raises(RuntimeError, match="pre-flight failed"):
        build(load_manifest(bundle_dir / "bundle.yaml"))


def test_cli(bundle_dir, capsys):
    assert main(["check", str(bundle_dir / "bundle.yaml")]) == 0
    assert main(["build", str(bundle_dir / "bundle.yaml")]) == 0
    assert "10 bundle page(s)" in capsys.readouterr().out
    assert main(["init", str(bundle_dir / "new.yaml")]) == 0
    assert (bundle_dir / "new.yaml").exists()
    assert main(["init", str(bundle_dir / "new.yaml")]) == 1  # refuses to overwrite


def test_index_spills_to_second_page(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    make_pdf(docs / "d.pdf", 1)
    sections = [{"title": "Many", "documents": [
        {"tab": str(i), "title": f"Document number {i}", "file": "docs/d.pdf", "date": "2026-01-01"}
        for i in range(1, 60)]}]
    (tmp_path / "b.yaml").write_text(yaml.safe_dump({"title": "T", "sections": sections}))
    res = build(load_manifest(tmp_path / "b.yaml"))
    assert res.index_pages == 2
    reader = PdfReader(str(res.output))
    assert "(cont.)" in reader.pages[1].extract_text()
    assert res.rows[0].target_index == 2


def test_stamp_is_readable_from_buffer():
    # sanity: reportlab -> pypdf round-trip used by the overlay
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(10, 10, "x")
    c.save()
    buf.seek(0)
    assert len(PdfReader(buf).pages) == 1
