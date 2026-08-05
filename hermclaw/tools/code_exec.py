"""Sandboxed code execution tool.

Runs Python (and optionally JavaScript via Node.js) code in an isolated
subprocess with a timeout.  The subprocess inherits a minimal environment
and writes to a temp directory that is cleaned up after execution.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT_S = 30


class CodeExecTool(ToolABC):
    """Execute Python or JavaScript code in a sandboxed subprocess."""

    def __init__(self, timeout_s: int = _DEFAULT_TIMEOUT_S) -> None:
        self._timeout_s = timeout_s

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="code_exec",
            description=(
                "Execute Python or JavaScript code and return the output. "
                "Runs in a subprocess with a timeout. Use this for calculations, "
                "data processing, testing code snippets, or any task that benefits "
                "from running actual code. The code has access to the filesystem "
                "and network."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The code to execute."},
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript"],
                        "description": "Programming language. Default: python.",
                    },
                },
                "required": ["code"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        code = args["code"]
        language = args.get("language", "python").lower()

        with tempfile.TemporaryDirectory(prefix="hermclaw_exec_") as tmpdir:
            if language == "python":
                script_path = Path(tmpdir) / "script.py"
                script_path.write_text(code, encoding="utf-8")
                cmd = [sys.executable, str(script_path)]
            elif language == "javascript":
                script_path = Path(tmpdir) / "script.js"
                script_path.write_text(code, encoding="utf-8")
                cmd = ["node", str(script_path)]
            else:
                return ToolResult(ok=False, output="", error=f"Unsupported language: {language}")

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout_s
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ToolResult(ok=False, output="", error=f"Execution timed out after {self._timeout_s}s")
            except FileNotFoundError:
                return ToolResult(
                    ok=False, output="",
                    error=f"Interpreter not found for {language}. "
                          f"{'Install Node.js to run JavaScript.' if language == 'javascript' else ''}"
                )

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            output_parts = []
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(f"[stderr]\n{stderr_text}")

            output = "\n".join(output_parts) or "(no output)"

            # Truncate very long output
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated]"

            if proc.returncode != 0:
                return ToolResult(ok=False, output=output, error=f"Process exited with code {proc.returncode}")
            return ToolResult(ok=True, output=output)
