from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from auth import Auth0TokenVerifier, build_auth_settings, load_oauth_config
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

UPSTREAM_ROOT = Path("/opt/natural-japanese")
SKILL_DIR = UPSTREAM_ROOT / "skills" / "natural-japanese"
SKILL_FILE = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "references"
SCRIPT_DIR = SKILL_DIR / "scripts"
UPSTREAM_COMMIT = "9a78a42964096da509b8f3e011f0085a5f080151"
MAX_TEXT_CHARS = 200_000

GUIDANCE_FILES = {
    "writing_constitution": REFERENCE_DIR / "writing-constitution.md",
    "revision_guide": REFERENCE_DIR / "revision-guide.md",
    "forbidden_patterns": REFERENCE_DIR / "forbidden-patterns.md",
    "translationese": REFERENCE_DIR / "translationese.md",
    "readability_principles": REFERENCE_DIR / "readability-principles.md",
    "readability_antipatterns": REFERENCE_DIR / "readability-antipatterns.md",
    "genre_notes": REFERENCE_DIR / "genre-notes.md",
    "diagnose": REFERENCE_DIR / "diagnose.md",
    "doctype_minutes": REFERENCE_DIR / "doctypes" / "minutes.md",
    "doctype_report": REFERENCE_DIR / "doctypes" / "report.md",
    "doctype_guide": REFERENCE_DIR / "doctypes" / "guide.md",
    "doctype_memo": REFERENCE_DIR / "doctypes" / "memo.md",
    "doctype_slide": REFERENCE_DIR / "doctypes" / "slide.md",
}

oauth_config = load_oauth_config()

mcp = MCPServer(
    "natural-japanese-mcp",
    token_verifier=Auth0TokenVerifier(oauth_config),
    auth=build_auth_settings(oauth_config),
    instructions=(
        "Natural Japanese quick runtime. 日本語文書の新規執筆・推敲・自然化・AI臭診断では、"
        "本文を書く前に必ず natural_japanese_quick_workflow を呼ぶ。rewrite では原文に "
        "lint_japanese を実行し、文脈で推敲し、推敲後にも lint_japanese を再実行する。"
        "再lintでは可能なら直前JSONを baseline に渡す。findingは疑いであり機械的に全修正しない。"
        "実行していない検査を実行済みと報告しない。判断に迷う場合だけ natural_japanese_guidance "
        "で本家referenceを読む。quickではoutline_japanese/terms_japaneseは必須ではない。"
        "full/exp相当を要求された場合、このMCP runtimeはquick高忠実度再現を主目的とし、"
        "正式Skillのfull工程やsemantic.pyを実行したふりをしない。"
    ),
)


def _read_utf8(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"upstream file not found: {path}")
    return path.read_text(encoding="utf-8")


def _section(markdown: str, heading: str, next_heading: str) -> str:
    start = markdown.find(heading)
    end = markdown.find(next_heading, start + len(heading))
    if start < 0 or end < 0:
        raise RuntimeError(f"upstream SKILL section not found: {heading}")
    return markdown[start:end].strip()


def _quick_excerpt() -> dict[str, str]:
    skill = _read_utf8(SKILL_FILE)
    execution = _section(skill, "## 実行モード — クイックとフル", "## 呼び出し方")
    quick_match = re.search(
        r"\*\*クイック（既定）\*\*:.*?(?=\n\n\*\*フル\*\*:)",
        execution,
        flags=re.S,
    )
    if not quick_match:
        raise RuntimeError("upstream quick-mode paragraph not found")

    return {
        "design_philosophy": _section(skill, "## 設計思想", "## 実行モード — クイックとフル"),
        "quick_mode": quick_match.group(0).strip(),
        "writing": _section(skill, "## 2. 執筆 — 文体憲法の下で書く", "## 3. 検査(1) — 静的検知"),
        "convergence": _section(skill, "## 5. 収束", "## 6. 最終パス — 自己点検ループと評価ハーネス"),
        "final_pass": _section(skill, "## 6. 最終パス — 自己点検ループと評価ハーネス", "## 7. 後片付け"),
    }


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


READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    open_world_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
)


@mcp.tool(annotations=READ_ONLY)
def natural_japanese_quick_workflow(
    operation: Literal["rewrite", "write", "score"] = "rewrite",
    document_type: Literal[
        "auto", "minutes", "report", "guide", "memo", "slide", "other"
    ] = "auto",
) -> dict[str, Any]:
    """Load the pinned upstream natural-japanese quick workflow before writing."""
    if operation == "rewrite":
        steps = [
            "対象文の読者・目的・主メッセージを短く確認する。",
            "原文に lint_japanese を必ず1回実行する。",
            "findingは疑いとして扱い、文脈で直す/残すを判断して推敲する。",
            "推敲後に lint_japanese を再実行する。可能なら初回JSONを baseline に渡す。",
            "新規findingがなければ、スケルトンと本文を通読して完了する。",
        ]
    elif operation == "write":
        steps = [
            "読者・目的・主メッセージ・見出しを先に決める。",
            "該当doctypeが明確なら natural_japanese_guidance で1ファイルだけ読む。",
            "本家の文体憲法に従って本文を書く。",
            "完成稿に lint_japanese を必ず1回実行する。",
            "findingを文脈で判断して修正し、lint_japanese を再実行する。",
            "新規findingがなければ、スケルトンと本文を通読して完了する。",
        ]
    else:
        steps = [
            "references/diagnose.md を natural_japanese_guidance(topic='diagnose') で必ず読む。",
            "対象文に lint_japanese を実行する。",
            "quick診断の定義に従って採点し、依頼がない限り本文を書き換えない。",
        ]

    doctype_topic = None if document_type in ("auto", "other") else f"doctype_{document_type}"

    return {
        "runtime": "natural-japanese quick MCP adaptation",
        "upstream_commit": UPSTREAM_COMMIT,
        "operation": operation,
        "document_type": document_type,
        "required_steps": steps,
        "doctype_guidance_topic": doctype_topic,
        "invariants": [
            "quickでもlintを省略しない。",
            "findingを機械的に全部直さない。",
            "読んで引っかからない文はいじらない。",
            "実行していない検査を実行済みと報告しない。",
            "referencesは判断に必要なものだけ読む。",
            "full/expの工程をquickで実行したふりをしない。",
        ],
        "upstream_excerpt": _quick_excerpt(),
    }


@mcp.tool(annotations=READ_ONLY)
def natural_japanese_guidance(
    topic: Literal[
        "writing_constitution",
        "revision_guide",
        "forbidden_patterns",
        "translationese",
        "readability_principles",
        "readability_antipatterns",
        "genre_notes",
        "diagnose",
        "doctype_minutes",
        "doctype_report",
        "doctype_guide",
        "doctype_memo",
        "doctype_slide",
    ],
) -> dict[str, Any]:
    """Return one pinned upstream reference file only when quick-mode judgment needs it."""
    path = GUIDANCE_FILES[topic]
    return {
        "upstream_commit": UPSTREAM_COMMIT,
        "topic": topic,
        "source": str(path.relative_to(UPSTREAM_ROOT)),
        "content": _read_utf8(path),
    }


@mcp.tool(annotations=READ_ONLY)
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


@mcp.tool(annotations=READ_ONLY)
def outline_japanese(text: str) -> dict[str, Any]:
    """Run the pinned upstream natural-japanese outline.py."""
    return _run_json_script("outline.py", text)


@mcp.tool(annotations=READ_ONLY)
def terms_japanese(text: str) -> dict[str, Any]:
    """Run the pinned upstream natural-japanese terms.py."""
    return _run_json_script("terms.py", text)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    tools = await mcp.list_tools()
    return JSONResponse(
        {
            "status": "ok",
            "upstream_commit": UPSTREAM_COMMIT,
            "upstream_skill_exists": SKILL_FILE.exists(),
            "upstream_scripts": {
                name: (SCRIPT_DIR / name).exists()
                for name in ["lint.py", "outline.py", "terms.py", "semantic.py"]
            },
            "registered_tools": [tool.name for tool in tools],
            "registered_tool_count": len(tools),
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
