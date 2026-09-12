"""CLI: init, check, build."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .build import build
from .check import check
from .manifest import load_manifest

TEMPLATE = """\
# bundlebuild manifest. Paths are relative to this file.
title: Bundle of Documents
court: In the General Division of the High Court of the Republic of Singapore
case: HC/OC 123/2026
parties: Alpha Pte Ltd v Beta Pte Ltd
volume: "1"
output: out/bundle.pdf
start_page: 1
stamp:
  position: bottom-right   # bottom-right | bottom-centre | top-right
  prefix: ""               # e.g. "AB" stamps AB-1, AB-2 ...

sections:
  - title: Pleadings
    documents:
      - tab: "1"
        title: Statement of Claim
        date: 2026-03-02
        file: docs/soc.pdf
      - tab: "2"
        title: Defence
        date: 2026-03-23
        file: docs/defence.pdf
  - title: Correspondence
    documents:
      - tab: "3"
        title: Letter from Alpha to Beta
        date: 2025-11-14
        file: docs/letter.pdf
        pages: "1-2"        # optional subset
"""


def _load(path: Path):
    try:
        return load_manifest(path)
    except ValidationError as e:
        print(f"invalid manifest {path}:\n{e}", file=sys.stderr)
        sys.exit(2)


def cmd_init(a) -> int:
    if a.path.exists() and not a.force:
        print(f"{a.path} exists; use --force to overwrite", file=sys.stderr)
        return 1
    a.path.write_text(TEMPLATE, encoding="utf-8")
    print(f"wrote {a.path}")
    return 0


def cmd_check(a) -> int:
    rep = check(_load(a.manifest))
    print(rep.to_text())
    return 0 if rep.ok else 1


def cmd_build(a) -> int:
    m = _load(a.manifest)
    try:
        res = build(m, skip_check=a.skip_check)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"wrote {res.output}: {res.index_pages} index page(s) + {res.content_pages} "
          f"bundle page(s), {len(res.rows)} tabs")
    print(f"index: {res.output.with_suffix('.index.json')}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bundlebuild", description="Court bundles from a YAML index.")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="write a template manifest")
    i.add_argument("path", type=Path, nargs="?", default=Path("bundle.yaml"))
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=cmd_init)

    c = sub.add_parser("check", help="pre-flight the manifest and its files")
    c.add_argument("manifest", type=Path)
    c.set_defaults(fn=cmd_check)

    b = sub.add_parser("build", help="build the bundle PDF")
    b.add_argument("manifest", type=Path)
    b.add_argument("--skip-check", action="store_true")
    b.set_defaults(fn=cmd_build)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
