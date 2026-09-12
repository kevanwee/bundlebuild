# bundlebuild

Court bundles from a YAML index. Merge the PDFs, stamp continuous page numbers, generate a
hyperlinked index and PDF bookmarks, and pre-flight everything so the missing exhibit is
found at your desk rather than at the registry.

```yaml
title: Bundle of Documents
case: HC/OC 123/2026
parties: Alpha Pte Ltd v Beta Pte Ltd
output: out/bundle.pdf
stamp: { prefix: "AB" }          # stamps AB-1, AB-2, ...

sections:
  - title: Pleadings
    documents:
      - { tab: "1", title: Statement of Claim, date: 2026-03-02, file: docs/soc.pdf }
      - { tab: "2", title: Defence,            date: 2026-03-23, file: docs/defence.pdf }
  - title: Correspondence
    documents:
      - { tab: "3", title: Letter of demand,   date: 2025-11-14, file: docs/lod.pdf, pages: "1-2" }
```

```
$ bundlebuild check bundle.yaml
[WARN ] tab 3: undated; index will show 'Undated'
[WARN ] tab 4: no text layer on any page; OCR before filing
5 documents, 10 pages, 0 error(s), 2 warning(s)

$ bundlebuild build bundle.yaml
wrote out/bundle.pdf: 1 index page(s) + 10 bundle page(s), 5 tabs
index: out/bundle.index.json
```

## Why

Bundle assembly is paid-product territory (Bundledocs, Opus 2, Casedo) and the free
alternative is a paralegal with Acrobat and an afternoon. The mechanics are not hard:
`pypdf` merges and annotates, `reportlab` draws. What is missing is a tool that treats the
index as the source of truth and checks the inputs before anyone prints 800 pages.

## What it does

| Step | Detail |
|---|---|
| **Pre-flight** (`check`) | Missing files, non-PDFs, unreadable or encrypted PDFs, page selections out of range, landscape pages, pages with no text layer (scans), undated documents, tabs out of order. Errors block the build; warnings are printed. |
| **Merge** | Documents in manifest order, optional per-document page subsets (`pages: "1-3,7"`). |
| **Stamp** | Continuous page numbers with optional prefix (`AB-12`), bottom-right / bottom-centre / top-right, sized to each page. |
| **Index** | Generated front matter: court, case, parties, title, volume; then Tab / Document / Date / Page rows grouped by section. Spills across pages as needed. |
| **Hyperlinks** | Every index row is a link annotation to its first page. |
| **Bookmarks** | PDF outline: sections, then `Tab n: title` under each. |
| **Sidecars** | `<output>.index.json` (tab, title, date, page range). For authorities bundles with `citation` fields, `<output>.citecheck.json`, a manifest [citecheck](https://github.com/kevanwee/citecheck) can consume. |

## Install

```bash
pip install -e ".[dev]"     # library + CLI + tests
pip install -e ".[mcp]"     # adds the MCP server
```

Python 3.11+. Pure Python; no Ghostscript, no Acrobat, no Java.

## CLI

```bash
bundlebuild init [bundle.yaml]      # write a template manifest
bundlebuild check bundle.yaml       # pre-flight; exit 1 on errors
bundlebuild build bundle.yaml       # check, then build; exit 1 on errors
bundlebuild build bundle.yaml --skip-check
```

## MCP server

```json
{ "mcpServers": { "bundlebuild": { "command": "bundlebuild-mcp" } } }
```

Tools: `manifest_template`, `check_bundle(manifest_path)`, `build_bundle(manifest_path)`.
The assistant's job is to help write the manifest from a folder of documents; the build is
deterministic and local.

## Manifest reference

| Field | Notes |
|---|---|
| `title`, `court`, `case`, `parties`, `volume` | Front matter on the index page. Only `title` is required. |
| `output` | Relative to the manifest file. |
| `start_page` | First stamped number (default 1; use e.g. 341 for volume 2). |
| `stamp.position` / `prefix` / `separator` / `font_size` / `margin_pt` | Stamp appearance. |
| `index_title` | Default `INDEX`. |
| `sections[].title` | Section heading in the index and the outline. |
| `documents[].tab` | A string label; must be unique across the bundle. |
| `documents[].title`, `date`, `description` | `date` may be a YAML date or free text ("Undated", "circa 2019"). |
| `documents[].file` | Relative to the manifest. Must be a PDF; convert first. |
| `documents[].pages` | Subset, 1-based, e.g. `"1-3,7"`. |
| `documents[].citation` | For authorities bundles; printed in the index and exported to the citecheck sidecar. |

## Conventions and limits

- The index is **not** page-numbered; bundle page 1 is the first content page. If your
  practice direction requires the index within the numbering, open an issue; it is a small
  change but it should be a deliberate one.
- Existing page numbers on the source documents are not removed. Stamps are placed in the
  margin; if a source document already prints in that corner, choose a different
  `stamp.position`.
- Rotated source pages are stamped in the page's own coordinate space, so the stamp rotates
  with the page. This is the correct behaviour for landscape exhibits inserted into a
  portrait bundle.
- No OCR. `check` tells you which pages lack a text layer; OCR them with whatever you use
  (ocrmypdf is good) and re-run.
- No conversion from Word/email/images. Convert first, then bundle.

## Related projects

[citecheck](https://github.com/kevanwee/citecheck) consumes the authorities sidecar. [chronology](https://github.com/kevanwee/chronology)
entries cite bundle page references produced here. See also [sg-deadline](https://github.com/kevanwee/sg-deadline).

## License

MIT.
