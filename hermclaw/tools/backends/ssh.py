"""SSH remote-host execution backend."""

from __future__ import annotations

import asyncio
from typing import Optional

from hermclaw.tools.base import ToolResult

DEFAULT_TIMEOUT_S = 30


async def run_ssh_command(
    command: str,
    host: str,
    user: Optional[str] = None,
    identity_file: Optional[str] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ToolResult:
    target = f"{user}@{host}" if user else host
    ssh_args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if identity_file:
        ssh_args += ["-i", identity_file]
    ssh_args += [target, command]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(ok=False, output="", error=f"SSH command timed out after {timeout_s}s")

        ok = proc.returncode == 0
        return ToolResult(
            ok=ok,
            output=stdout.decode(errors="replace"),
            error=stderr.decode(errors="replace") if not ok else None,
            metadata={"returncode": proc.returncode, "host": host},
        )
    except FileNotFoundError:
        return ToolResult(ok=False, output="", error="ssh executable not found on PATH")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=str(exc))
