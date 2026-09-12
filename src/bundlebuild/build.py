"""Build: merge, stamp, index, bookmark.

Page-number arithmetic is done once, up front, from the manifest and the page counts. The
index is generated *after* that arithmetic so it can print page ranges, and its rows are
turned into link annotations after the merge so they point at the right pages.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .check import check
from .manifest import Document, Manifest, StampPosition

PAGE_W, PAGE_H = A4
MARGIN = 50
ROW_H = 18
COLS = {"tab": 50, "title": 95, "date": 400, "pages": 485}  # x positions


@dataclass
class IndexRow:
    doc: Document
    first: int  # bundle page number (as stamped)
    last: int
    target_index: int = 0  # 0-based page index in the final PDF, set after merge

    @property
    def page_label(self) -> str:
        return str(self.first) if self.first == self.last else f"{self.first}-{self.last}"


@dataclass
class BuildResult:
    output: Path
    index_pages: int
    content_pages: int
    rows: list[IndexRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def index_json(self) -> list[dict]:
        return [
            {
                "tab": r.doc.tab,
                "title": r.doc.title,
                "date": r.doc.date_label,
                "citation": r.doc.citation,
                "pages": r.page_label,
                "first_page": r.first,
                "last_page": r.last,
            }
            for r in self.rows
        ]

    def citecheck_manifest(self) -> dict:
        """Authorities in this bundle as a citecheck manifest (only rows with a citation)."""
        entries = [{"key": r.doc.citation, "title": r.doc.title,
                    "note": f"tab {r.doc.tab}, pp {r.page_label}"}
                   for r in self.rows if r.doc.citation]
        return {"coverage": [], "entries": entries}


# -- index PDF ---------------------------------------------------------------------------


def _draw_index(m: Manifest, rows: list[IndexRow]) -> tuple[bytes, list[tuple[int, tuple]]]:
    """Render the index. Returns (pdf bytes, [(index_page_no, rect) per row])."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    rects: list[tuple[int, tuple]] = []
    page_no = 0

    def header(first: bool) -> float:
        y = PAGE_H - MARGIN
        if first:
            c.setFont("Helvetica-Bold", 12)
            for line in filter(None, [m.court, m.case, m.parties]):
                c.drawCentredString(PAGE_W / 2, y, line)
                y -= 16
            y -= 8
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(PAGE_W / 2, y, m.title.upper())
            y -= 18
            if m.volume:
                c.setFont("Helvetica", 11)
                c.drawCentredString(PAGE_W / 2, y, f"Volume {m.volume}")
                y -= 16
            y -= 6
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(PAGE_W / 2, y, m.index_title)
            y -= 22
        else:
            c.setFont("Helvetica", 9)
            c.drawRightString(PAGE_W - MARGIN, y, f"{m.index_title} (cont.)")
            y -= 20
        c.setFont("Helvetica-Bold", 10)
        c.drawString(COLS["tab"], y, "Tab")
        c.drawString(COLS["title"], y, "Document")
        c.drawString(COLS["date"], y, "Date")
        c.drawString(COLS["pages"], y, "Page")
        y -= 4
        c.line(MARGIN, y, PAGE_W - MARGIN, y)
        return y - ROW_H

    y = header(True)
    for section in m.sections:
        if y < MARGIN + 2 * ROW_H:
            c.showPage()
            page_no += 1
            y = header(False)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(COLS["tab"], y, section.title.upper())
        y -= ROW_H
        for row in (r for r in rows if r.doc in section.documents):
            if y < MARGIN + ROW_H:
                c.showPage()
                page_no += 1
                y = header(False)
            c.setFont("Helvetica", 10)
            c.drawString(COLS["tab"], y, row.doc.tab)
            title = row.doc.title
            if row.doc.citation:
                title = f"{title} {row.doc.citation}"
            c.drawString(COLS["title"], y, _fit(c, title, COLS["date"] - COLS["title"] - 8))
            c.drawString(COLS["date"], y, row.doc.date_label)
            c.drawString(COLS["pages"], y, row.page_label)
            rects.append((page_no, (MARGIN, y - 4, PAGE_W - MARGIN, y + ROW_H - 6)))
            y -= ROW_H
    c.save()
    return buf.getvalue(), rects


def _fit(c: canvas.Canvas, text: str, width: float, font: str = "Helvetica", size: int = 10) -> str:
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return text + "..."


# -- stamping ----------------------------------------------------------------------------


def _stamp_overlay(w: float, h: float, label: str, m: Manifest) -> PdfReader:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFont("Helvetica", m.stamp.font_size)
    mg = m.stamp.margin_pt
    pos = m.stamp.position
    if pos is StampPosition.BOTTOM_RIGHT:
        c.drawRightString(w - mg, mg, label)
    elif pos is StampPosition.BOTTOM_CENTRE:
        c.drawCentredString(w / 2, mg, label)
    else:
        c.drawRightString(w - mg, h - mg, label)
    c.save()
    buf.seek(0)
    return PdfReader(buf)


# -- build -------------------------------------------------------------------------------


def build(m: Manifest, *, skip_check: bool = False) -> BuildResult:
    if not skip_check:
        rep = check(m)
        if not rep.ok:
            raise RuntimeError("pre-flight failed:\n" + rep.to_text())

    # 1. page arithmetic
    readers: list[tuple[Document, PdfReader, list[int]]] = []
    rows: list[IndexRow] = []
    n = m.start_page
    for d in m.documents:
        r = PdfReader(str(m.resolve(d.file)))
        if r.is_encrypted:
            r.decrypt("")
        sel = d.page_selection(len(r.pages))
        readers.append((d, r, sel))
        rows.append(IndexRow(d, n, n + len(sel) - 1))
        n += len(sel)
    content_pages = n - m.start_page

    # 2. index
    index_bytes, rects = _draw_index(m, rows)
    index_reader = PdfReader(io.BytesIO(index_bytes))
    index_pages = len(index_reader.pages)

    # 3. merge
    writer = PdfWriter()
    for p in index_reader.pages:
        writer.add_page(p)
    for row, (_, r, sel) in zip(rows, readers, strict=True):
        row.target_index = len(writer.pages)
        for i in sel:
            page = r.pages[i]
            label = m.stamp.label(row.first + sel.index(i))
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            overlay = _stamp_overlay(w, h, label, m)
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

    # 4. bookmarks
    section_items = {}
    for section in m.sections:
        first_row = next((r for r in rows if r.doc in section.documents), None)
        if first_row is None:
            continue
        section_items[section.title] = writer.add_outline_item(section.title,
                                                               first_row.target_index)
        for row in (r for r in rows if r.doc in section.documents):
            writer.add_outline_item(f"Tab {row.doc.tab}: {row.doc.title}", row.target_index,
                                    parent=section_items[section.title])

    # 5. index hyperlinks
    for row, (ipage, rect) in zip(rows, rects, strict=True):
        writer.add_annotation(page_number=ipage,
                              annotation=Link(rect=rect, target_page_index=row.target_index))

    writer.add_metadata({"/Title": m.title, "/Producer": "bundlebuild"})
    out = m.resolve(m.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)

    result = BuildResult(out, index_pages, content_pages, rows)
    (out.with_suffix(".index.json")).write_text(json.dumps(result.index_json(), indent=2),
                                                 encoding="utf-8")
    if any(r.doc.citation for r in rows):
        out.with_suffix(".citecheck.json").write_text(
            json.dumps(result.citecheck_manifest(), indent=2), encoding="utf-8")
    return result
