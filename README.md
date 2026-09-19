# natural-japanese-mcp

ChatGPT Plugin + remote MCP wrapper for the upstream
[coji/natural-japanese](https://github.com/coji/natural-japanese).

The goal is to preserve the upstream natural-Japanese workflow while making its
deterministic checks available from ChatGPT surfaces that cannot execute the
upstream Python scripts locally.

## Architecture

```text
ChatGPT Plugin
├─ skills/natural-japanese/    # OpenAI-adapted Skill
│  ├─ SKILL.md
│  ├─ agents/openai.yaml
│  ├─ references/
│  ├─ assets/
│  └─ scripts/                # upstream copies for audit/reference
└─ remote MCP
   ├─ lint_japanese
   ├─ outline_japanese
   └─ terms_japanese
        ↓
Render
        ↓
pinned coji/natural-japanese scripts
```

The upstream Skill snapshot is also preserved without modification under
`vendor/coji-natural-japanese/`.

## Upstream pin

- Repository: `coji/natural-japanese`
- Commit: `9a78a42964096da509b8f3e011f0085a5f080151`
- License: MIT

`vendor/coji-natural-japanese/UPSTREAM_COMMIT` records the pinned revision.

## MCP

- Endpoint: `https://natural-japanese-mcp.onrender.com/mcp`
- Health: `https://natural-japanese-mcp.onrender.com/health`
- Transport: Streamable HTTP
- Deployment: Render Web Service

### `lint_japanese`

Runs the pinned upstream `lint.py`.

Inputs include:

- `text`
- `genre`: `tech`, `business`, or `essay`
- `reading_load`
- `experimental`
- `baseline`: previous JSON result for convergence comparison

### `outline_japanese`

Runs the pinned upstream `outline.py` and returns its JSON skeleton analysis.

### `terms_japanese`

Runs the pinned upstream `terms.py` and returns its JSON terminology inventory.

All three MCP tools are read-only and idempotent. They process supplied text but
do not write back to user repositories or external services.

## semantic.py

The upstream `semantic.py` is retained in the Skill/vendor snapshots but is not
exposed through the current Render Free MCP deployment. It requires a heavyweight
embedding stack and roughly 1 GB of initial model download. The adapted Skill must
state that `exp` semantic analysis is unavailable rather than simulate it.

## Plugin packages

This repository keeps two packaging forms separate.

### Portable package

The repository root contains the portable Agent Plugins form:

- `plugin.json`
- `mcp.json`
- `skills/natural-japanese/`

This form declares the remote MCP URL directly.

### OpenAI local test package

`plugins/natural-japanese/` contains an OpenAI-compatible local test package:

- `.codex-plugin/plugin.json`
- `.app.json`
- `skills/natural-japanese/`

It references the already registered ChatGPT app
`asdk_app_6aae03fa144081919c3e1e990516df87` instead of declaring another
`mcp.json` inside the test package. This keeps the local package tied to the
MCP connection already verified in ChatGPT.

The marketplace catalog at `.agents/plugins/marketplace.json` points to this
OpenAI test package.

For local desktop testing, register this repository as a marketplace:

```text
codex plugin marketplace add 123kaz/natural-japanese-mcp --ref main
```

Then reload the ChatGPT desktop app, open the Plugin Directory, select
`Natural Japanese Local`, and install `natural-japanese`.

## Privacy and security

The current MCP endpoint uses no authentication. Input text sent to an MCP tool
is transmitted to the Render-hosted service and processed in a temporary file,
which the wrapper deletes after the tool call.

Do not treat the unauthenticated deployment as a security boundary. Add
authentication and review hosting/privacy requirements before exposing the
service broadly or relying on it for sensitive material.

## License

Wrapper and adaptation code: MIT. See `LICENSE`.

Upstream copyright and license are preserved under
`vendor/coji-natural-japanese/LICENSE` and documented in
`THIRD_PARTY_NOTICES.md`.
