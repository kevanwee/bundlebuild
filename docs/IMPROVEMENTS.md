# Improvement audit — 16 September 2026

## Correctness checkpoint

Output could overwrite a source, repeated pages shared stamp content, page ranges accepted descending empty selections, and index titles were truncated.

Implemented: preserve source pdfs and correctly stamp repeated and rotated pages. Regression tests exercise the failure cases and
the original suite remains required. GitHub Actions runs tests, lint and package builds.

## Requested next release

The user requested the ranked product improvements, including optional local browser
workspaces. This extends the earlier CLI-only scope in CLAUDE.md. Existing command-line
interfaces and deterministic libraries remain supported. Browser workspaces must preserve
source evidence and explicit human review; they must not infer legal conclusions.

Workspace implementation, integration tests and release validation are in progress.
