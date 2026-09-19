from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

UPSTREAM_ROOT = Path("/opt/natural-japanese")
SCRIPT_DIR = UPSTREAM_ROOT / "skills" / "natural-japanese" / "scripts"
MAX_TEXT_CHARS = 200_000

mcp = MCPServer(
    "natural-japanese-mcp",
    instructions=(
        "Expose the pinned upstream coji/natural-japanese deterministic scripts "
        "without reimplementing their logic. Use these tools when the "
        "natural-japanese skill asks for lint, outline, or terminology checks."
    ),
)


def _run_json_script(
    script_name: str,
    text: str,
    extra_args: list[str] | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds {MAX_TEXT_CHARS} characters")

    script = SCRIPT_DIR / script_name
    if not script.exists():
        raise RuntimeError(f"upstream script not found: {script}")

    baseline_path: str | None = None
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", encoding="utf-8", delete=False
    ) as fp:
        fp.write(text)
        text_path = fp.name

    try:
        cmd = ["uv", "run", str(script), text_path, "--json"]
        if extra_args:
            cmd.extend(extra_args)

        if baseline is not None:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8", delete=False
            ) as bp:
                json.dump(baseline, bp, ensure_ascii=False)
                baseline_path = bp.name
            cmd.extend(["--baseline", baseline_path])

        proc = subprocess.run(
            cmd,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{script_name} failed: "
                + (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}")
            )

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{script_name} returned non-JSON output: " + proc.stdout[:1000]
            ) from exc
    finally:
        Path(text_path).unlink(missing_ok=True)
        if baseline_path is not None:
            Path(baseline_path).unlink(missing_ok=True)


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
def lint_japanese(
    text: str,
    genre: Literal["tech", "business", "essay"] | None = None,
    reading_load: bool = False,
    experimental: bool = False,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the pinned upstream natural-japanese lint.py."""
    args: list[str] = []
    if genre is not None:
        args.extend(["--genre", genre])
    if reading_load:
        args.append("--reading-load")
    if experimental:
        args.append("--experimental")
    return _run_json_script("lint.py", text, args, baseline=baseline)


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
def outline_japanese(text: str) -> dict[str, Any]:
    """Run the pinned upstream natural-japanese outline.py."""
    return _run_json_script("outline.py", text)


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
def terms_japanese(text: str) -> dict[str, Any]:
    """Run the pinned upstream natural-japanese terms.py."""
    return _run_json_script("terms.py", text)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "upstream_scripts": {
                name: (SCRIPT_DIR / name).exists()
                for name in ["lint.py", "outline.py", "terms.py", "semantic.py"]
            },
        }
    )


app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)
