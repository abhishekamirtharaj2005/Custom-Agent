"""The shell tool.

Config default: tools.shell_enabled: false. When false, this tool is not
registered in ToolDispatcher at all -- it never appears in the tool list
sent to the model, which is stricter than either source project's
default of "on, but guarded." See config.py / ToolDispatcher.register.
"""

from __future__ import annotations

from typing import Any, Optional

from hermclaw.tools.backends.docker import run_docker_command
from hermclaw.tools.backends.local import run_local_command, scoped_env
from hermclaw.tools.backends.ssh import run_ssh_command
from hermclaw.tools.backends.stubs import (
    run_daytona_command,
    run_modal_command,
    run_singularity_command,
)
from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

SUPPORTED_BACKENDS = ("local", "docker", "ssh", "singularity", "modal", "daytona")


class ShellTool(ToolABC):
    """Executes a shell command through exactly one of six backends. This
    class contains NO direct subprocess/Popen/docker calls of its own --
    it only delegates to the backend modules under tools/backends/."""

    def __init__(
        self,
        backend: str = "local",
        docker_image: Optional[str] = None,
        docker_network: Optional[str] = "none",
        ssh_host: Optional[str] = None,
        ssh_user: Optional[str] = None,
        ssh_identity_file: Optional[str] = None,
        extra_allowed_env: Optional[list[str]] = None,
        filesystem_scope: Optional[str] = None,
    ) -> None:
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"Unknown backend '{backend}', must be one of {SUPPORTED_BACKENDS}")
        self.backend = backend
        self.docker_image = docker_image or "python:3.11-slim"
        self.docker_network = docker_network
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_identity_file = ssh_identity_file
        self.extra_allowed_env = extra_allowed_env or []
        self.filesystem_scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="shell",
            description=(
                "Execute a shell command and return its stdout/stderr. "
                "Use this to open applications (e.g., 'start notepad', 'start chrome'), "
                "open URLs in the browser (e.g., 'start https://youtube.com'), "
                "manage files, install software, run scripts, and perform any system task."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."},
                },
                "required": ["command"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        command = args.get("command", "")
        if not command:
            return ToolResult(ok=False, output="", error="Missing 'command' argument")

        if self.backend == "local":
            return await run_local_command(command, env=scoped_env(self.extra_allowed_env), cwd=self.filesystem_scope)
        if self.backend == "docker":
            return await run_docker_command(
                command, image=self.docker_image, network=self.docker_network,
                workspace_host_path=self.filesystem_scope,
            )
        if self.backend == "ssh":
            if not self.ssh_host:
                return ToolResult(ok=False, output="", error="ssh backend requires tools.ssh_host to be set")
            return await run_ssh_command(
                command, host=self.ssh_host, user=self.ssh_user, identity_file=self.ssh_identity_file
            )
        if self.backend == "singularity":
            return await run_singularity_command(command)
        if self.backend == "modal":
            return await run_modal_command(command)
        if self.backend == "daytona":
            return await run_daytona_command(command)

        return ToolResult(ok=False, output="", error=f"Unsupported backend: {self.backend}")
