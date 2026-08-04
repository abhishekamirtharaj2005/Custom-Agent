"""Docker ephemeral-container execution backend.

Runs each command in a fresh, disposable container. Network is disabled
by default (tools.docker_network: none) to close the SSRF path that
Hermes Agent's own docs flag against unrestricted sandboxed execution.
"""

from __future__ import annotations

import asyncio
import shlex
from typing import Optional

from hermclaw.tools.base import ToolResult

DEFAULT_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT_S = 60


async def run_docker_command(
    command: str,
    image: str = DEFAULT_IMAGE,
    network: Optional[str] = "none",
    timeout_s: int = DEFAULT_TIMEOUT_S,
    workspace_host_path: Optional[str] = None,
    workspace_container_path: str = "/workspace",
) -> ToolResult:
    """Runs `command` inside a fresh container via the `docker run --rm`
    CLI. Uses the CLI rather than the Docker SDK to avoid an unconditional
    hard dependency; callers needing the SDK can swap this implementation.

    With no workspace_host_path, the container has no host filesystem
    access at all -- the strictest possible interpretation of
    tools.filesystem_scope. Passing one bind-mounts exactly that
    directory (nothing else on the host) at workspace_container_path and
    runs the command from there, so tools.filesystem_scope is actually
    enforced by the container boundary rather than merely documented.
    """
    docker_args = ["docker", "run", "--rm", "--network", network or "none"]
    if workspace_host_path:
        docker_args += ["-v", f"{workspace_host_path}:{workspace_container_path}", "-w", workspace_container_path]
    docker_args += [image, "/bin/sh", "-c", command]
    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(ok=False, output="", error=f"Docker command timed out after {timeout_s}s")

        ok = proc.returncode == 0
        return ToolResult(
            ok=ok,
            output=stdout.decode(errors="replace"),
            error=stderr.decode(errors="replace") if not ok else None,
            metadata={"returncode": proc.returncode, "image": image},
        )
    except FileNotFoundError:
        return ToolResult(ok=False, output="", error="docker executable not found on PATH")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=str(exc))
