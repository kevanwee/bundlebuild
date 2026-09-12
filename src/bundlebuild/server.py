"""MCP server: lets an assistant pre-flight and build a bundle from a manifest path.

Deliberately thin. The assistant's job is to help write the manifest; the build is
deterministic and local.
"""

from __future__ import annotations

from pathlib import Path

try:  # mcp >= 2.0 renamed FastMCP -> MCPServer; same decorator/run surface
    from mcp.server.mcpserver import MCPServer as FastMCP
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from .build import build
from .check import check
from .cli import TEMPLATE
from .manifest import load_manifest

mcp = FastMCP(
    "bundlebuild",
    instructions=(
        "Builds court bundles from a YAML manifest. Always run check_bundle before "
        "build_bundle and show the user every warning. Never invent document titles or "
        "dates; ask for them."
    ),
)


@mcp.tool()
def manifest_template() -> str:
    """Return a template manifest to fill in."""
    return TEMPLATE


@mcp.tool()
def check_bundle(manifest_path: str) -> dict:
    """Pre-flight a manifest: missing files, unreadable PDFs, scanned pages, tab order."""
    rep = check(load_manifest(Path(manifest_path)))
    return {
        "ok": rep.ok,
        "total_pages": rep.total_pages,
        "findings": [{"severity": f.severity, "tab": f.tab, "message": f.message}
                     for f in rep.findings],
    }


@mcp.tool()
def build_bundle(manifest_path: str) -> dict:
    """Build the bundle. Fails if pre-flight has errors."""
    res = build(load_manifest(Path(manifest_path)))
    return {
        "output": str(res.output),
        "index_pages": res.index_pages,
        "content_pages": res.content_pages,
        "index": res.index_json(),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
