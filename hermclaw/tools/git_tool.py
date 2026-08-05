"""Git checkpoint management tool.

Provides automatic git checkpoint creation, diff viewing,
rollback, and stash management for the agent's coding workflow.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class GitTool(ToolABC):
    """Git operations for checkpoint management."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="git",
            description=(
                "Git checkpoint management. Actions: status (working tree status), "
                "diff (show changes), checkpoint (commit all changes with message), "
                "log (recent commits), rollback (undo last checkpoint), stash (save/pop changes), "
                "branch (create/switch branches), init (initialize repo)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "diff", "checkpoint", "log", "rollback", "stash", "branch", "init"],
                    },
                    "message": {"type": "string", "description": "Commit message (checkpoint)."},
                    "path": {"type": "string", "description": "Working directory path."},
                    "branch_name": {"type": "string", "description": "Branch name (branch action)."},
                    "stash_action": {
                        "type": "string",
                        "enum": ["save", "pop", "list", "drop"],
                        "description": "Stash sub-action.",
                    },
                    "n": {"type": "integer", "description": "Number of log entries. Default: 10."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        cwd = args.get("path", ".")

        try:
            if action == "status":
                return self._run_git(["status", "--short", "--branch"], cwd)

            elif action == "diff":
                result = self._run_git(["diff", "--stat"], cwd)
                if result.ok:
                    detailed = self._run_git(["diff"], cwd)
                    output = result.output
                    if detailed.ok and detailed.output:
                        # Truncate if too long
                        diff_text = detailed.output
                        if len(diff_text) > 5000:
                            diff_text = diff_text[:5000] + "\n... [truncated]"
                        output += "\n\n" + diff_text
                    return ToolResult(ok=True, output=output)
                return result

            elif action == "checkpoint":
                message = args.get("message", f"Checkpoint at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                # Stage all changes
                add_result = self._run_git(["add", "-A"], cwd)
                if not add_result.ok:
                    return add_result
                # Commit
                return self._run_git(["commit", "-m", message, "--allow-empty"], cwd)

            elif action == "log":
                n = args.get("n", 10)
                return self._run_git(
                    ["log", f"--oneline", f"-{n}", "--decorate", "--graph"],
                    cwd,
                )

            elif action == "rollback":
                return self._run_git(["reset", "--soft", "HEAD~1"], cwd)

            elif action == "stash":
                stash_action = args.get("stash_action", "save")
                if stash_action == "save":
                    return self._run_git(["stash", "push", "-m", f"hermclaw-stash-{int(time.time())}"], cwd)
                elif stash_action == "pop":
                    return self._run_git(["stash", "pop"], cwd)
                elif stash_action == "list":
                    return self._run_git(["stash", "list"], cwd)
                elif stash_action == "drop":
                    return self._run_git(["stash", "drop"], cwd)
                else:
                    return ToolResult(ok=False, output="", error=f"Unknown stash action: {stash_action}")

            elif action == "branch":
                branch_name = args.get("branch_name", "")
                if not branch_name:
                    return self._run_git(["branch", "-a"], cwd)
                # Check if branch exists
                existing = self._run_git(["branch", "--list", branch_name], cwd)
                if existing.ok and branch_name in existing.output:
                    return self._run_git(["checkout", branch_name], cwd)
                return self._run_git(["checkout", "-b", branch_name], cwd)

            elif action == "init":
                return self._run_git(["init"], cwd)

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Git error: {exc}")

    def _run_git(self, cmd: list[str], cwd: str) -> ToolResult:
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr and result.returncode != 0:
                output += "\n" + result.stderr
            if len(output) > 8000:
                output = output[:8000] + "\n... [truncated]"
            return ToolResult(
                ok=result.returncode == 0,
                output=output.strip(),
                error=result.stderr.strip() if result.returncode != 0 else None,
            )
        except FileNotFoundError:
            return ToolResult(ok=False, output="", error="Git not found. Install git first.")
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output="", error="Git command timed out.")
