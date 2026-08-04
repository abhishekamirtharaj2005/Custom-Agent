from __future__ import annotations

import sys
from pathlib import Path

from hermclaw.body.mcp_client import McpClientManager
from hermclaw.tools.approvals import build_approval_gate
from hermclaw.tools.base import ToolDispatcher

_TEST_SERVER = str(Path(__file__).parent / "fixtures" / "mcp_test_server.py")


class _FakeMcpServerConfig:
    def __init__(self, name: str, command: str) -> None:
        self.name = name
        self.transport = "stdio"
        self.command = command
        self.url = None


async def test_mcp_client_discovers_and_calls_tools() -> None:
    server_cfg = _FakeMcpServerConfig("testsrv", f"{sys.executable} {_TEST_SERVER}")
    manager = McpClientManager([server_cfg])
    try:
        tools = await manager.connect_all()
        assert len(tools) == 1
        assert tools[0].spec().name == "mcp__testsrv__add"

        dispatcher = ToolDispatcher(build_approval_gate(mode="off"))
        for t in tools:
            dispatcher.register(t)

        result = await dispatcher.dispatch("mcp__testsrv__add", {"a": 3, "b": 4})
        assert result.ok is True
        assert result.output.strip() == "7"
    finally:
        await manager.close()


async def test_mcp_client_skips_unreachable_server_without_crashing() -> None:
    bad_cfg = _FakeMcpServerConfig("unreachable", "this-binary-does-not-exist-anywhere")
    manager = McpClientManager([bad_cfg])
    tools = await manager.connect_all()
    assert tools == []
    await manager.close()
