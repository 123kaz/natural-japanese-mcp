from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

UPSTREAM_ROOT = Path("/opt/natural-japanese")
LINT_SCRIPT = UPSTREAM_ROOT / "skills" / "natural-japanese" / "scripts" / "lint.py"
MAX_TEXT_CHARS = 200_000

mcp = MCPServer(
    "natural-japanese-mcp",
    instructions=(
        "Expose the upstream coji/natural-japanese lint.py without reimplementing "
        "its detection logic. This server is a thin transport wrapper."
    ),
)


@mcp.tool()
def lint_japanese(
    text: str,
    genre: Literal["tech", "business", "essay"] = "tech",
    reading_load: bool = False,
    experimental: bool = False,
) -> dict:
    """Run the pinned upstream natural-japanese lint.py against Japanese Markdown text."""
    if not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds {MAX_TEXT_CHARS} characters")
    if not LINT_SCRIPT.exists():
        raise RuntimeError(f"upstream lint.py not found: {LINT_SCRIPT}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        encoding="utf-8",
        delete=False,
    ) as fp:
        fp.write(text)
        temp_path = fp.name

    try:
        cmd = [
            "uv",
            "run",
            str(LINT_SCRIPT),
            temp_path,
            "--json",
            "--genre",
            genre,
        ]
        if reading_load:
            cmd.append("--reading-load")
        if experimental:
            cmd.append("--experimental")

        proc = subprocess.run(
            cmd,
            cwd=LINT_SCRIPT.parent,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                "natural-japanese lint failed: "
                + (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}")
            )

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "natural-japanese lint returned non-JSON output: "
                + proc.stdout[:1000]
            ) from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "upstream_lint_exists": LINT_SCRIPT.exists(),
        }
    )


# Render terminates TLS and forwards traffic through its reverse proxy.
# Disable MCP's localhost-focused DNS rebinding check explicitly at this layer;
# the public host itself is controlled by Render.
app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)
