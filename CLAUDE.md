# CLAUDE.md — bundlebuild

Engineering conventions for this repository. They bind AI assistants and humans equally.

## What this is

A deterministic PDF assembler driven by a YAML manifest. The manifest is the source of
truth; the PDF is a build artefact. If a bundle is wrong, the fix is to the manifest and
the build, never to the PDF by hand.

## Non-negotiables

1. **The manifest is the only input.** No interactive prompts, no reading document titles
   out of PDF metadata, no guessing dates from filenames. If a field is missing the index
   says so ("Undated") and `check` warns.
2. **Pre-flight before build, always.** `build()` runs `check()` and refuses on errors.
   `--skip-check` exists for re-runs on already-checked inputs; never make it the default.
3. **Page arithmetic happens once, up front.** Compute every document's page range from
   the manifest and page counts *before* drawing the index or merging anything. Never derive
   a page number from the writer's current page count mid-merge; that is how off-by-ones
   survive to the courtroom.
4. **No external binaries.** `pypdf` + `reportlab` only. No Ghostscript, no Acrobat, no
   LibreOffice, no OCR engine. Conversion and OCR are upstream of this tool.
5. **Do not modify source PDFs.** Read them, overlay stamps onto copies in the writer.
6. **Sidecar JSON is part of the contract.** `<output>.index.json` and the citecheck
   sidecar are consumed by other tools; changing their shape is a breaking change.

## Layout

```
src/bundlebuild/
  manifest.py   pydantic models + loader (base_dir resolution lives here)
  check.py      pre-flight; Finding(severity, tab, message)
  build.py      page arithmetic -> index drawing -> merge+stamp -> bookmarks -> links
  cli.py        argparse; the manifest TEMPLATE lives here
  server.py     MCP wrapper; thin
examples/       manifests only (no PDFs committed)
tests/          generates its own PDFs with reportlab into tmp_path
```

## Testing discipline

- Tests generate their own PDFs (`make_pdf` in `test_build.py`). Never commit binary PDF
  fixtures; they rot and they bloat the repo.
- Every build feature is asserted by reading the output back with `pypdf`: stamped text
  via `extract_text()`, links via `/Annots`, outline via `reader.outline`. If you cannot
  assert it from the output PDF, it is not tested.
- Page-range expectations are written as literal tuples (`("3", 6, 8)`), computed by hand
  from the fixture page counts.
- `python -m pytest` and `ruff check src tests` before every commit. The suite runs in
  about a second.

## Style

- Python 3.11+, type hints, pydantic for the manifest, dataclasses for results.
- Line length 100.
- reportlab drawing code: constants for layout (`MARGIN`, `ROW_H`, `COLS`) at module top;
  no magic numbers inline. If a number appears twice, name it.
- Comments explain layout decisions and PDF quirks (coordinate origin, rotation), not what
  the code does.

## Legal-content conventions

- Tabs are strings. Practitioners use "12A" and "B-3". Never coerce to int; sort warnings
  use the leading integer only.
- Dates in the index print as `02 Mar 2026`. Free-text dates ("Undated", "circa 2019") are
  allowed and printed verbatim.
- The index is unnumbered by convention. If a court's practice direction differs, add a
  manifest option; do not change the default.
- Stamp labels use the manifest prefix exactly; never add "Page" or "p." automatically.

## Commit hygiene

- Imperative subject, scoped: `build: stamp rotated pages in page space`.
- One logical change per commit.
- No AI attribution lines or co-author trailers.

## What not to build here

- OCR, Word-to-PDF, email-to-PDF conversion.
- A GUI.
- Redaction. That is a different tool with different failure modes.
- Automatic index generation from a folder listing. Titles and dates must be typed by a
  person who has read the document.
