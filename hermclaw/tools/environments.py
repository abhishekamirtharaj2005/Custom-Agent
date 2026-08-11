"""Additional execution environments: Modal, Daytona, Singularity.

Also includes:
- PTY (pseudo-terminal) support
- File sync between host and environments
- Codex/Responses API runtime
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Modal cloud execution
# ---------------------------------------------------------------------------


class ModalEnvironment:
    """Execute code in Modal.com cloud functions."""

    def __init__(self, token: str = "") -> None:
        self._token = token or os.environ.get("MODAL_TOKEN_ID", "")

    async def run(self, code: str, image: str = "python:3.12",
                  timeout: int = 300, gpu: str = "") -> dict[str, Any]:
        """Run Python code in a Modal sandbox."""
        if not self._token:
            return {"error": "MODAL_TOKEN_ID not set"}

        try:
            # Create a temporary script
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                modal_script = f"""
import modal
app = modal.App("hermclaw-sandbox")

@app.function(image=modal.Image.debian_slim().pip_install("httpx"), timeout={timeout}{f', gpu="{gpu}"' if gpu else ''})
def run_code():
{chr(10).join('    ' + line for line in code.splitlines())}

if __name__ == "__main__":
    with app.run():
        result = run_code.remote()
        print(result)
"""
                f.write(modal_script)
                script_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "python", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "MODAL_TOKEN_ID": self._token},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 30)

            return {
                "stdout": stdout.decode()[:4000],
                "stderr": stderr.decode()[:2000],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"error": "Modal execution timed out"}
        except Exception as exc:
            return {"error": f"Modal error: {exc}"}


# ---------------------------------------------------------------------------
# Daytona dev environments
# ---------------------------------------------------------------------------


class DaytonaEnvironment:
    """Manage Daytona dev environments for remote code execution."""

    def __init__(self, api_url: str = "http://localhost:3986") -> None:
        self._url = api_url.rstrip("/")

    async def create_workspace(self, repo_url: str, name: str = "") -> dict:
        """Create a new Daytona workspace."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._url}/workspace",
                    json={"repositories": [{"url": repo_url}], "name": name or "hermclaw-ws"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return {"error": f"Daytona error: {exc}"}

    async def list_workspaces(self) -> list[dict]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._url}/workspace")
                return resp.json()
        except Exception:
            return []

    async def exec_in_workspace(self, workspace_id: str, command: str) -> dict:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._url}/workspace/{workspace_id}/toolbox/process/execute",
                    json={"command": command},
                )
                return resp.json()
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Singularity container execution
# ---------------------------------------------------------------------------


class SingularityEnvironment:
    """Execute code in Singularity/Apptainer containers (HPC environments)."""

    def __init__(self, image: str = "library://default/python:3.12") -> None:
        self._image = image

    async def run(self, command: str, bind_paths: list[str] | None = None) -> dict[str, Any]:
        """Run a command inside a Singularity container."""
        cmd = ["singularity", "exec"]

        if bind_paths:
            for bp in bind_paths:
                cmd.extend(["--bind", bp])

        cmd.extend([self._image, "bash", "-c", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            return {
                "stdout": stdout.decode()[:4000],
                "stderr": stderr.decode()[:2000],
                "exit_code": proc.returncode,
            }
        except FileNotFoundError:
            return {"error": "Singularity/Apptainer not installed"}
        except asyncio.TimeoutError:
            return {"error": "Execution timed out"}
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# PTY (pseudo-terminal) support
# ---------------------------------------------------------------------------


class PTYSession:
    """Pseudo-terminal session for interactive command execution."""

    def __init__(self) -> None:
        self._process = None
        self._master_fd = None

    async def start(self, command: str = "bash") -> bool:
        """Start a PTY session."""
        if platform.system() == "Windows":
            # On Windows, use conpty via subprocess
            try:
                self._process = await asyncio.create_subprocess_shell(
                    command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                return True
            except Exception as exc:
                logger.error("pty.start_failed", error=str(exc)[:100])
                return False
        else:
            # On Unix, use pty module
            try:
                import pty
                import os
                master_fd, slave_fd = pty.openpty()
                self._master_fd = master_fd
                self._process = await asyncio.create_subprocess_exec(
                    command,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                )
                os.close(slave_fd)
                return True
            except Exception as exc:
                logger.error("pty.start_failed", error=str(exc)[:100])
                return False

    async def send(self, data: str) -> None:
        """Send data to the PTY."""
        if self._process and self._process.stdin:
            self._process.stdin.write(data.encode())
            await self._process.stdin.drain()
        elif self._master_fd:
            os.write(self._master_fd, data.encode())

    async def read(self, size: int = 4096) -> str:
        """Read output from the PTY."""
        if self._master_fd:
            import os
            try:
                data = os.read(self._master_fd, size)
                return data.decode("utf-8", errors="replace")
            except OSError:
                return ""
        elif self._process and self._process.stdout:
            data = await self._process.stdout.read(size)
            return data.decode("utf-8", errors="replace")
        return ""

    async def close(self) -> None:
        if self._process:
            self._process.kill()
        if self._master_fd:
            os.close(self._master_fd)


# ---------------------------------------------------------------------------
# File sync between host and environments
# ---------------------------------------------------------------------------


class FileSync:
    """Sync files between host and remote/container environments."""

    def __init__(self, local_root: Path, remote_root: str = "/workspace") -> None:
        self._local = local_root
        self._remote = remote_root

    async def push(self, paths: list[str], target: str = "docker",
                   container_name: str = "hermclaw") -> int:
        """Push files from host to remote environment."""
        count = 0
        for path in paths:
            local_path = self._local / path
            if not local_path.exists():
                continue

            remote_path = f"{self._remote}/{path}"

            if target == "docker":
                cmd = f"docker cp {local_path} {container_name}:{remote_path}"
            elif target == "ssh":
                cmd = f"scp {local_path} {container_name}:{remote_path}"
            else:
                continue

            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    count += 1
            except Exception:
                pass

        logger.info("file_sync.pushed", count=count, target=target)
        return count

    async def pull(self, paths: list[str], source: str = "docker",
                   container_name: str = "hermclaw") -> int:
        """Pull files from remote environment to host."""
        count = 0
        for path in paths:
            remote_path = f"{self._remote}/{path}"
            local_path = self._local / path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if source == "docker":
                cmd = f"docker cp {container_name}:{remote_path} {local_path}"
            elif source == "ssh":
                cmd = f"scp {container_name}:{remote_path} {local_path}"
            else:
                continue

            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    count += 1
            except Exception:
                pass

        logger.info("file_sync.pulled", count=count, source=source)
        return count


# ---------------------------------------------------------------------------
# Codex / Responses API runtime
# ---------------------------------------------------------------------------


class CodexRuntime:
    """OpenAI Codex / Responses API runtime adapter.

    Executes tool calls in Codex format and maps them to HermClaw tools.
    """

    CODEX_TOOL_MAP = {
        "code_interpreter": "code_exec",
        "file_search": "grep_search",
        "web_search": "web_search",
    }

    def __init__(self, dispatcher: Any = None) -> None:
        self._dispatcher = dispatcher

    async def execute_codex_call(self, call: dict[str, Any]) -> dict[str, Any]:
        """Execute a Codex-format tool call via HermClaw dispatcher."""
        codex_tool = call.get("type", "")
        hermclaw_tool = self.CODEX_TOOL_MAP.get(codex_tool, codex_tool)

        if not self._dispatcher:
            return {"error": "No dispatcher configured"}

        args = call.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"input": args}

        # Map Codex arguments to HermClaw format
        if codex_tool == "code_interpreter":
            args = {"code": args.get("input", ""), "language": "python"}

        try:
            result = await self._dispatcher.dispatch(hermclaw_tool, args)
            return {"output": result.output, "status": "success" if result.ok else "error"}
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Tirith security framework
# ---------------------------------------------------------------------------


class TirithSecurityFramework:
    """Security policy enforcement framework.

    Evaluates security policies defined as rules against tool calls,
    file operations, and network requests.
    """

    def __init__(self) -> None:
        self._policies: list[dict] = []
        self._violations: list[dict] = []

    def add_policy(self, name: str, check_fn: str, action: str = "warn",
                   description: str = "") -> None:
        """Add a security policy rule."""
        self._policies.append({
            "name": name,
            "check": check_fn,
            "action": action,  # "warn", "block", "log"
            "description": description,
        })

    def evaluate(self, context: dict[str, Any]) -> list[dict]:
        """Evaluate all policies against a context."""
        violations = []
        for policy in self._policies:
            check = policy["check"]
            violated = False

            # Simple pattern-based checks
            if check.startswith("deny_tool:"):
                tool = check.split(":", 1)[1]
                if context.get("tool") == tool:
                    violated = True
            elif check.startswith("deny_path:"):
                pattern = check.split(":", 1)[1]
                path = context.get("path", "")
                if pattern in path:
                    violated = True
            elif check.startswith("deny_domain:"):
                domain = check.split(":", 1)[1]
                url = context.get("url", "")
                if domain in url:
                    violated = True
            elif check.startswith("max_file_size:"):
                max_size = int(check.split(":", 1)[1])
                if context.get("file_size", 0) > max_size:
                    violated = True

            if violated:
                violation = {
                    "policy": policy["name"],
                    "action": policy["action"],
                    "description": policy["description"],
                    "context": {k: str(v)[:100] for k, v in context.items()},
                }
                violations.append(violation)
                self._violations.append(violation)

                if policy["action"] == "block":
                    logger.warning("tirith.blocked", policy=policy["name"])

        return violations

    def is_blocked(self, violations: list[dict]) -> bool:
        return any(v["action"] == "block" for v in violations)

    @property
    def violation_history(self) -> list[dict]:
        return self._violations

    def load_policies_from_file(self, path: Path) -> int:
        """Load policies from a JSON file."""
        if not path.exists():
            return 0
        try:
            policies = json.loads(path.read_text())
            for p in policies:
                self.add_policy(p["name"], p["check"], p.get("action", "warn"), p.get("description", ""))
            return len(policies)
        except Exception as exc:
            logger.error("tirith.load_failed", error=str(exc)[:100])
            return 0
