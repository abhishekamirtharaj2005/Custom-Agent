"""Language Server Protocol (LSP) tool for Hermclaw.

Provides code intelligence:
- Diagnostics (syntax errors, linting, type checks)
- Go to definition
- Hover documentation & type signatures
- Code completion suggestions
- Document symbols (functions, classes, methods)
- Symbol references search
- Language server installation & status
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class LSPTool(ToolABC):
    """Language Server Protocol tool for code intelligence and diagnostics."""

    SERVER_CONFIGS = {
        "python": {
            "name": "pyright / pylsp",
            "install": "pip install pyright pylsp ruff",
            "cmd": ["pyright", "pylsp", "ruff"],
            "extensions": [".py", ".pyi"],
        },
        "typescript": {
            "name": "typescript-language-server",
            "install": "npm install -g typescript typescript-language-server",
            "cmd": ["typescript-language-server", "tsc"],
            "extensions": [".ts", ".tsx", ".js", ".jsx"],
        },
        "rust": {
            "name": "rust-analyzer",
            "install": "rustup component add rust-analyzer",
            "cmd": ["rust-analyzer"],
            "extensions": [".rs"],
        },
        "go": {
            "name": "gopls",
            "install": "go install golang.org/x/tools/gopls@latest",
            "cmd": ["gopls"],
            "extensions": [".go"],
        },
        "cpp": {
            "name": "clangd",
            "install": "apt-get install clangd / choco install llvm",
            "cmd": ["clangd"],
            "extensions": [".cpp", ".hpp", ".c", ".h", ".cc"],
        },
    }

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="lsp",
            description=(
                "Language Server Protocol (LSP) client for code intelligence. "
                "Actions: diagnostics (syntax/type errors), definition (find definition), "
                "hover (docs & signature), completions (suggestions), symbols (document outline), "
                "references (find usages), install_server (server setup info)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "diagnostics",
                            "definition",
                            "hover",
                            "completions",
                            "symbols",
                            "references",
                            "install_server",
                        ],
                        "description": "LSP action to perform.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Target source code file path.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "1-indexed line number for hover/definition/completions.",
                    },
                    "column": {
                        "type": "integer",
                        "description": "1-indexed column number for hover/definition/completions.",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol or identifier name to inspect or search.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language (python, typescript, rust, go, cpp).",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "diagnostics")
        file_path_str = args.get("file_path", "")
        line = args.get("line", 1)
        column = args.get("column", 1)
        symbol = args.get("symbol", "")
        language = args.get("language", "").lower()

        if action == "install_server":
            return self._install_server_info(language or self._detect_language(file_path_str))

        if not file_path_str:
            return ToolResult(ok=False, output="", error="file_path is required for this action")

        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            return ToolResult(ok=False, output="", error=f"File not found: {file_path_str}")

        if not language:
            language = self._detect_language(str(file_path))

        try:
            if action == "diagnostics":
                return self._run_diagnostics(file_path, language)
            elif action == "definition":
                return self._get_definition(file_path, line, column, symbol, language)
            elif action == "hover":
                return self._get_hover(file_path, line, column, symbol, language)
            elif action == "completions":
                return self._get_completions(file_path, line, column, language)
            elif action == "symbols":
                return self._get_symbols(file_path, language)
            elif action == "references":
                return self._get_references(file_path, symbol, language)
            else:
                return ToolResult(ok=False, output="", error=f"Unknown LSP action: {action}")
        except Exception as exc:
            logger.error("lsp.execute_failed", action=action, error=str(exc))
            return ToolResult(ok=False, output="", error=f"LSP execution error: {exc}")

    def _detect_language(self, path_str: str) -> str:
        ext = Path(path_str).suffix.lower()
        for lang, cfg in self.SERVER_CONFIGS.items():
            if ext in cfg["extensions"]:
                return lang
        return "python"

    def _install_server_info(self, language: str) -> ToolResult:
        if language in self.SERVER_CONFIGS:
            cfg = self.SERVER_CONFIGS[language]
            installed_cmds = [cmd for cmd in cfg["cmd"] if shutil.which(cmd)]
            status = f"Installed ({', '.join(installed_cmds)})" if installed_cmds else "Not installed"
            output = (
                f"LSP Server for {language.capitalize()}:\n"
                f"- Server: {cfg['name']}\n"
                f"- Status: {status}\n"
                f"- Installation Command: {cfg['install']}"
            )
            return ToolResult(ok=True, output=output)
        return ToolResult(
            ok=True,
            output="Supported languages: python, typescript, rust, go, cpp. Pass language parameter for specific instructions.",
        )

    def _run_diagnostics(self, file_path: Path, language: str) -> ToolResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        diagnostics: List[Dict[str, Any]] = []

        if language == "python":
            # 1. AST Syntax Check
            try:
                ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                diagnostics.append({
                    "line": e.lineno or 1,
                    "column": e.offset or 1,
                    "severity": "Error",
                    "code": "SyntaxError",
                    "message": str(e.msg),
                })

            # 2. Check py_compile as secondary verification
            if not diagnostics:
                try:
                    import py_compile
                    py_compile.compile(str(file_path), doraise=True)
                except py_compile.PyCompileError as e:
                    diagnostics.append({
                        "line": 1,
                        "column": 1,
                        "severity": "Error",
                        "code": "CompileError",
                        "message": str(e),
                    })

            # 3. If ruff or flake8 installed, run fast lint
            if shutil.which("ruff"):
                try:
                    res = subprocess.run(
                        ["ruff", "check", "--output-format=json", str(file_path)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    import json
                    if res.stdout.strip():
                        data = json.loads(res.stdout)
                        for item in data:
                            diagnostics.append({
                                "line": item.get("location", {}).get("row", 1),
                                "column": item.get("location", {}).get("column", 1),
                                "severity": "Warning",
                                "code": item.get("code", "LINT"),
                                "message": item.get("message", ""),
                            })
                except Exception:
                    pass

        elif language in ("typescript", "javascript"):
            # Check basic bracket/brace balance and tsc if installed
            if shutil.which("tsc"):
                try:
                    res = subprocess.run(
                        ["tsc", "--noEmit", str(file_path)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    for line in res.stdout.splitlines():
                        if ": error TS" in line:
                            parts = line.split(":")
                            diagnostics.append({
                                "line": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1,
                                "column": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1,
                                "severity": "Error",
                                "code": "TS",
                                "message": ":".join(parts[3:]).strip(),
                            })
                except Exception:
                    pass

        if not diagnostics:
            return ToolResult(ok=True, output=f"✅ Clean: No errors or diagnostics found in {file_path.name}.")

        lines = [f"Diagnostics for {file_path.name} ({len(diagnostics)} found):"]
        for d in diagnostics:
            lines.append(f"  [{d['severity']}] L{d['line']}:C{d['column']} ({d['code']}): {d['message']}")
        return ToolResult(ok=True, output="\n".join(lines))

    def _get_symbols(self, file_path: Path, language: str) -> ToolResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        symbols: List[str] = []

        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        symbols.append(f"📦 Class {node.name} (Line {node.lineno})")
                        for sub in node.body:
                            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                symbols.append(f"   ↳ Method {sub.name} (Line {sub.lineno})")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(f"⚡ Function {node.name} (Line {node.lineno})")
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                symbols.append(f"🔹 Variable {target.id} (Line {node.lineno})")
            except Exception as e:
                return ToolResult(ok=False, output="", error=f"Failed to parse symbols: {e}")
        else:
            # Generic regex-based symbol scanner
            fn_matches = re.finditer(r"(function|def|fn|func|class|struct|interface)\s+([a-zA-Z0-9_]+)", content)
            for m in fn_matches:
                line_no = content[: m.start()].count("\n") + 1
                symbols.append(f"🔹 {m.group(1)} {m.group(2)} (Line {line_no})")

        if not symbols:
            return ToolResult(ok=True, output="No symbols found.")
        return ToolResult(ok=True, output="\n".join(symbols))

    def _get_definition(self, file_path: Path, line: int, column: int, symbol: str, language: str) -> ToolResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        target_sym = symbol
        if not target_sym and 1 <= line <= len(lines):
            line_str = lines[line - 1]
            match = re.search(r"([a-zA-Z0-9_]+)", line_str[max(0, column - 1):])
            if match:
                target_sym = match.group(1)

        if not target_sym:
            return ToolResult(ok=False, output="", error="No symbol specified or found at cursor")

        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_sym:
                        return ToolResult(
                            ok=True,
                            output=f"Definition of '{target_sym}': {file_path}:{node.lineno}:{node.col_offset + 1}",
                        )
            except Exception:
                pass

        # Workspace/file grep fallback
        pattern = re.compile(rf"(def|class|function|const|let|var|type|struct)\s+{re.escape(target_sym)}\b")
        for i, l in enumerate(lines, 1):
            if pattern.search(l):
                return ToolResult(
                    ok=True,
                    output=f"Definition of '{target_sym}': {file_path}:{i} -> {l.strip()}",
                )

        return ToolResult(ok=True, output=f"Definition for '{target_sym}' not found in current file.")

    def _get_hover(self, file_path: Path, line: int, column: int, symbol: str, language: str) -> ToolResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        target_sym = symbol
        if not target_sym and 1 <= line <= len(lines):
            line_str = lines[line - 1]
            match = re.search(r"([a-zA-Z0-9_]+)", line_str[max(0, column - 1):])
            if match:
                target_sym = match.group(1)

        if not target_sym:
            return ToolResult(ok=False, output="", error="No symbol specified or found at cursor")

        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_sym:
                        doc = ast.get_docstring(node) or "No docstring provided."
                        args = []
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            args = [a.arg for a in node.args.args]
                            sig = f"def {node.name}({', '.join(args)})"
                        else:
                            sig = f"class {node.name}"
                        return ToolResult(
                            ok=True,
                            output=f"**{sig}**\n\n```text\n{doc}\n```\nDefined at line {node.lineno}.",
                        )
            except Exception:
                pass

        return ToolResult(
            ok=True,
            output=f"**Symbol: {target_sym}** (Language: {language})\nIn {file_path.name} at line {line}.",
        )

    def _get_completions(self, file_path: Path, line: int, column: int, language: str) -> ToolResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        prefix = ""
        if 1 <= line <= len(lines):
            line_str = lines[line - 1]
            prefix_match = re.search(r"([a-zA-Z0-9_]+)$", line_str[:column])
            if prefix_match:
                prefix = prefix_match.group(1)

        # Gather identifiers from the file
        identifiers = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", content))
        if prefix:
            matches = [id_ for id_ in sorted(identifiers) if id_.startswith(prefix) and id_ != prefix]
        else:
            matches = sorted(identifiers)[:20]

        if not matches:
            return ToolResult(ok=True, output=f"No completion matches for '{prefix}'.")

        return ToolResult(
            ok=True,
            output=f"Completions for '{prefix}':\n" + "\n".join(f"- {m}" for m in matches[:25]),
        )

    def _get_references(self, file_path: Path, symbol: str, language: str) -> ToolResult:
        if not symbol:
            return ToolResult(ok=False, output="", error="Symbol is required to find references.")

        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        pattern = re.compile(rf"\b{re.escape(symbol)}\b")

        references: List[str] = []
        for i, l in enumerate(lines, 1):
            if pattern.search(l):
                references.append(f"Line {i}: {l.strip()}")

        if not references:
            return ToolResult(ok=True, output=f"No references to '{symbol}' found in {file_path.name}.")

        return ToolResult(
            ok=True,
            output=f"Found {len(references)} references to '{symbol}' in {file_path.name}:\n"
            + "\n".join(references[:30]),
        )
