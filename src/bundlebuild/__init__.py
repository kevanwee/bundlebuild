"""bundlebuild: court bundles from a YAML index.

    load_manifest(path)     -> Manifest
    check(manifest)         -> CheckReport   pre-flight: files, pages, orientation, text layer
    build(manifest)         -> BuildResult   merged, stamped, indexed, bookmarked PDF
"""

from .build import BuildResult, build
from .check import CheckReport, Finding, check
from .manifest import Document, Manifest, Section, load_manifest

__all__ = [
    "Manifest",
    "Section",
    "Document",
    "load_manifest",
    "check",
    "CheckReport",
    "Finding",
    "build",
    "BuildResult",
]

__version__ = "0.1.0"
