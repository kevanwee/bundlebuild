"""Bundle manifest: the YAML index that is the single source of truth for a bundle."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class StampPosition(StrEnum):
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_CENTRE = "bottom-centre"
    TOP_RIGHT = "top-right"


class Stamp(BaseModel):
    position: StampPosition = StampPosition.BOTTOM_RIGHT
    prefix: str = ""  # e.g. "AB" -> "AB-12"; "" -> "12"
    separator: str = "-"
    font_size: int = 10
    margin_pt: int = 28

    def label(self, n: int) -> str:
        return f"{self.prefix}{self.separator}{n}" if self.prefix else str(n)


class Document(BaseModel):
    tab: str  # "1", "12A", "B-3"; a string because tabs are labels, not numbers
    title: str
    file: Path
    date: date | str | None = None
    description: str | None = None
    citation: str | None = Field(
        default=None, description="for authorities bundles: the neutral/report citation"
    )
    pages: str | None = Field(
        default=None, description="subset to include, e.g. '1-3,7'; default all"
    )

    def page_selection(self, total: int) -> list[int]:
        """0-based page indices to include."""
        if not self.pages:
            return list(range(total))
        out: list[int] = []
        for part in self.pages.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                out.extend(range(int(a) - 1, int(b)))
            else:
                out.append(int(part) - 1)
        bad = [p for p in out if p < 0 or p >= total]
        if bad:
            raise ValueError(f"{self.file}: page selection {self.pages!r} exceeds {total} pages")
        return out

    @property
    def date_label(self) -> str:
        if self.date is None:
            return "Undated"
        if isinstance(self.date, date):
            return self.date.strftime("%d %b %Y")
        return str(self.date)


class Section(BaseModel):
    title: str
    documents: list[Document]


class Manifest(BaseModel):
    title: str
    case: str | None = None
    parties: str | None = None
    court: str | None = None
    volume: str | None = None
    output: Path = Path("out/bundle.pdf")
    base_dir: Path | None = Field(default=None, description="resolved from the manifest's dir")
    start_page: int = 1
    stamp: Stamp = Stamp()
    index_title: str = "INDEX"
    sections: list[Section]

    @model_validator(mode="after")
    def _unique_tabs(self) -> Manifest:
        seen: set[str] = set()
        for s in self.sections:
            for d in s.documents:
                if d.tab in seen:
                    raise ValueError(f"duplicate tab {d.tab!r}")
                seen.add(d.tab)
        if not any(s.documents for s in self.sections):
            raise ValueError("manifest has no documents")
        return self

    @property
    def documents(self) -> list[Document]:
        return [d for s in self.sections for d in s.documents]

    def resolve(self, p: Path) -> Path:
        base = self.base_dir or Path(".")
        return p if p.is_absolute() else (base / p)


def load_manifest(path: str | Path) -> Manifest:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    m = Manifest.model_validate(raw)
    if m.base_dir is None:
        m.base_dir = path.resolve().parent
    return m
