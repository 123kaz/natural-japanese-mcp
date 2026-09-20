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

## Quick MCP runtime

The primary MCP runtime is `@natural-japanese-mcp` itself. It reproduces the
upstream quick-mode execution discipline without pretending to be an OpenAI
Skill.

ChatGPT availability is plan- and surface-dependent. As verified in September
2026, ChatGPT Plus is not listed by OpenAI as supporting custom MCP apps.
ChatGPT Pro supports custom MCP connections with read/fetch permissions, while
full MCP support is available to Business and Enterprise/Edu. MCP apps are
documented as Web-only. The Render service may therefore be healthy and fully
authenticated while no MCP actions are exposed in a Plus chat.

When the current ChatGPT plan/surface does not expose this custom MCP, do not
claim that its checks ran.

- `natural_japanese_quick_workflow`: must be called before Japanese
  write/rewrite/score work; returns the pinned upstream quick-mode excerpts and
  the required execution sequence.
- `natural_japanese_guidance`: returns one pinned upstream reference file only
  when judgment needs it.
- `lint_japanese`: mandatory before and after a quick rewrite.
- `outline_japanese` and `terms_japanese`: available, but not mandatory in
  quick mode.

The MCP server instructions explicitly prohibit claiming that a check ran when
the corresponding tool was not called. Full-mode subagent review and
`semantic.py` are not simulated by this runtime.

## MCP

- Endpoint: `https://natural-japanese-mcp.onrender.com/mcp`
- Health: `https://natural-japanese-mcp.onrender.com/health`
- Transport: Streamable HTTP
- Deployment: Render Web Service

### Authentication

The current remote MCP endpoint does not require authentication.

Do not treat this deployment as a security boundary. Anyone who can reach the
public endpoint may attempt to call the exposed read-only tools. Do not send
secrets, credentials, or other sensitive material through this deployment.

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
`asdk_app_6aaf26c0ea2881919a46b7fd45b35c74` instead of declaring another
`mcp.json` inside the test package. This keeps the local package tied to the
MCP connection already verified in ChatGPT.

The marketplace catalog at `.agents/plugins/marketplace.json` points to this
OpenAI test package.

The local plugin package can still be registered as a marketplace for Skill
testing. App-backed MCP action availability follows ChatGPT's current plan and
surface support.

For local desktop Skill testing, register this repository as a marketplace:

```text
codex plugin marketplace add 123kaz/natural-japanese-mcp --ref main
```

Then reload the ChatGPT desktop app, open the Plugin Directory, select
`Natural Japanese Local`, and install `natural-japanese`.

## Privacy and security

Input text sent to an MCP tool is transmitted over HTTPS to the Render-hosted
service and processed in a temporary file, which the wrapper deletes after the
tool call. The application does not intentionally persist input text or emit it
to application logs.

The MCP endpoint is unauthenticated. Input text is transmitted over HTTPS, but
the endpoint itself does not identify or authorize callers.

Render remains the hosting provider and therefore processes request data while
serving the MCP endpoint. This deployment does not claim provider-level
zero-retention of submitted text.

## License

Wrapper and adaptation code: MIT. See `LICENSE`.

Upstream copyright and license are preserved under
`vendor/coji-natural-japanese/LICENSE` and documented in
`THIRD_PARTY_NOTICES.md`.
