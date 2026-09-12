"""Pre-flight checks. Run before build; run again after any file changes.

Findings have a severity: `error` blocks the build; `warn` is reported and the build
proceeds. The point is that nobody discovers a missing exhibit at the registry counter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .manifest import Document, Manifest


@dataclass
class Finding:
    severity: str  # "error" | "warn"
    tab: str | None
    message: str


@dataclass
class DocInfo:
    tab: str
    title: str
    pages: int
    landscape_pages: list[int] = field(default_factory=list)
    scanned_pages: list[int] = field(default_factory=list)
    encrypted: bool = False


@dataclass
class CheckReport:
    findings: list[Finding] = field(default_factory=list)
    docs: list[DocInfo] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def total_pages(self) -> int:
        return sum(d.pages for d in self.docs)

    def to_text(self) -> str:
        lines = []
        for f in self.findings:
            tab = f"tab {f.tab}: " if f.tab else ""
            lines.append(f"[{f.severity.upper():5}] {tab}{f.message}")
        lines.append(f"{len(self.docs)} documents, {self.total_pages} pages, "
                     f"{len(self.errors)} error(s), "
                     f"{len(self.findings) - len(self.errors)} warning(s)")
        return "\n".join(lines)


def _check_doc(m: Manifest, d: Document, report: CheckReport) -> None:
    path = m.resolve(d.file)
    if not path.exists():
        report.findings.append(Finding("error", d.tab, f"file not found: {path}"))
        return
    if path.suffix.lower() != ".pdf":
        report.findings.append(Finding("error", d.tab, f"not a PDF: {path.name} "
                                       "(convert first; bundlebuild does not convert)"))
        return
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001 -- pypdf raises several types here
                report.findings.append(Finding("error", d.tab,
                                               f"encrypted and cannot be opened: {path.name}"))
                return
        total = len(reader.pages)
    except (PdfReadError, OSError) as e:
        report.findings.append(Finding("error", d.tab, f"cannot read {path.name}: {e}"))
        return

    try:
        selection = d.page_selection(total)
    except ValueError as e:
        report.findings.append(Finding("error", d.tab, str(e)))
        return

    info = DocInfo(tab=d.tab, title=d.title, pages=len(selection), encrypted=reader.is_encrypted)
    for i in selection:
        page = reader.pages[i]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        rot = page.rotation % 180
        if (w > h) != (rot == 90):
            info.landscape_pages.append(i + 1)
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 -- extraction failures are a warning, not a crash
            text = ""
        if len(text) < 20:
            info.scanned_pages.append(i + 1)
    report.docs.append(info)

    if info.landscape_pages:
        report.findings.append(Finding("warn", d.tab,
                                       f"{len(info.landscape_pages)} landscape page(s): "
                                       f"{_short(info.landscape_pages)}"))
    if info.scanned_pages:
        if len(info.scanned_pages) == info.pages:
            report.findings.append(Finding("warn", d.tab,
                                           "no text layer on any page; OCR before filing"))
        else:
            report.findings.append(Finding("warn", d.tab,
                                           f"no text layer on {len(info.scanned_pages)} "
                                           f"page(s): {_short(info.scanned_pages)}"))
    if d.date is None:
        report.findings.append(Finding("warn", d.tab, "undated; index will show 'Undated'"))


def _short(pages: list[int], n: int = 8) -> str:
    s = ", ".join(map(str, pages[:n]))
    return s + (f", ... (+{len(pages) - n})" if len(pages) > n else "")


def check(m: Manifest) -> CheckReport:
    report = CheckReport()
    out = m.resolve(m.output)
    if out.exists():
        report.findings.append(Finding("warn", None,
                                       f"output exists and will be overwritten: {out}"))
    for d in m.documents:
        _check_doc(m, d, report)
    _check_tab_order(m, report)
    return report


def _check_tab_order(m: Manifest, report: CheckReport) -> None:
    """Warn if numeric tabs are out of order; tabs like '12A' are compared by their number."""
    import re

    prev = None
    for d in m.documents:
        mm = re.match(r"^\D*(\d+)", d.tab)
        if not mm:
            continue
        n = int(mm.group(1))
        if prev is not None and n < prev:
            report.findings.append(Finding("warn", d.tab, f"tab order: {d.tab} follows {prev}"))
        prev = n
