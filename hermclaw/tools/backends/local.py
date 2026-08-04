"""Local subprocess execution backend.

This is the ONLY place in Hermclaw (besides its sibling backends in this
package) that is permitted to call asyncio.create_subprocess_exec /
subprocess.Popen. It is never reached implicitly -- the shell tool is not
even registered unless tools.shell_enabled is true AND tools.backend is
"local".
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from hermclaw.tools.base import ToolResult

DEFAULT_TIMEOUT_S = 30


async def run_local_command(
    command: str,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ToolResult:
    """Execute `command` via /bin/sh -c in a subprocess with an explicitly
    scoped environment (never the full parent environment by default --
    see security/secrets.py)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env if env is not None else {},
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(ok=False, output="", error=f"Command timed out after {timeout_s}s")

        output = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        ok = proc.returncode == 0
        return ToolResult(
            ok=ok,
            output=output,
            error=err if not ok else None,
            metadata={"returncode": proc.returncode},
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=str(exc))


def scoped_env(extra_allowed: Optional[list[str]] = None) -> dict[str, str]:
    """Build a minimal environment for subprocess execution: PATH/HOME/LANG
    only by default, plus any explicitly allow-listed variables for this
    specific tool call. Never forwards the full parent environment."""
    base_keys = ["PATH", "HOME", "LANG", "LC_ALL"]
    env = {k: os.environ[k] for k in base_keys if k in os.environ}
    if extra_allowed:
        for k in extra_allowed:
            if k in os.environ:
                env[k] = os.environ[k]
    return env
