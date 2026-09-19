# natural-japanese-mcp

Remote MCP wrapper for the upstream [coji/natural-japanese](https://github.com/coji/natural-japanese) lint tooling.

## Current scope

Phase 1 intentionally exposes only the upstream `lint.py` through MCP. It does
not reimplement or simplify the upstream detection rules.

- MCP endpoint: `/mcp`
- Health endpoint: `/health`
- Transport: Streamable HTTP
- Deployment target: Render Web Service
- Upstream commit: `9a78a42964096da509b8f3e011f0085a5f080151`

## MCP tool

### `lint_japanese`

Inputs:

- `text`: Japanese Markdown text
- `genre`: `tech`, `business`, or `essay`
- `reading_load`: enable upstream reading-load checks
- `experimental`: enable upstream experimental checks

The server writes the supplied text to a temporary Markdown file and invokes the
pinned upstream command through `uv run .../lint.py --json`.

## Render

This repository is designed to deploy as a Docker-based Render Web Service.
Render supplies `PORT`; `server.py` binds to `0.0.0.0:$PORT`.

No application secrets are required for the Phase 1 smoke test.

## License

Wrapper code: MIT. See `LICENSE`.

Upstream attribution and pinned revision: see `THIRD_PARTY_NOTICES.md`.
