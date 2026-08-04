"""MCP client: connects to servers declared under skills.mcp_servers and
wraps each of their tools as a Hermclaw Tool, so remote MCP tools flow
through the exact same ToolDispatcher and approval gate as local ones --
no separate code path, no separate trust model.
"""

from __future__ import annotations

import shlex
from contextlib import AsyncExitStack
from typing import Any, Optional

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class McpToolAdapter(ToolABC):
    def __init__(self, session: ClientSession, mcp_tool: Any, server_name: str) -> None:
        self._session = session
        self._mcp_tool = mcp_tool
        self.server_name = server_name

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=f"mcp__{self.server_name}__{self._mcp_tool.name}",
            description=self._mcp_tool.description or f"Tool '{self._mcp_tool.name}' from MCP server '{self.server_name}'.",
            parameters=self._mcp_tool.input_schema or {"type": "object", "properties": {}},
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            result = await self._session.call_tool(self._mcp_tool.name, args)
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"MCP call failed: {exc}")

        text_parts = [block.text for block in result.content if hasattr(block, "text")]
        output = "\n".join(text_parts)
        if result.is_error:
            return ToolResult(ok=False, output="", error=output or "MCP tool reported an error")
        return ToolResult(ok=True, output=output)


class McpClientManager:
    """Owns the lifecycle of every configured MCP server connection.
    connect_all() is best-effort per server -- one misconfigured or
    unreachable server logs a warning and is skipped rather than
    blocking every other server (and the rest of Hermclaw) from
    starting."""

    def __init__(self, servers: list[Any]) -> None:  # list[config.McpServerConfig]
        self.servers = servers
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[McpToolAdapter] = []

    async def connect_all(self) -> list[McpToolAdapter]:
        for server in self.servers:
            try:
                await self._connect_one(server)
            except Exception as exc:
                logger.warning("mcp.connect_failed", server=server.name, error=str(exc))
        return list(self._tools)

    async def _connect_one(self, server: Any) -> None:
        if server.transport == "stdio":
            if not server.command:
                raise ValueError(f"MCP server {server.name!r}: transport=stdio requires 'command'")
            parts = shlex.split(server.command)
            params = StdioServerParameters(command=parts[0], args=parts[1:])
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        elif server.transport == "sse":
            if not server.url:
                raise ValueError(f"MCP server {server.name!r}: transport=sse requires 'url'")
            read, write = await self._exit_stack.enter_async_context(sse_client(server.url))
        else:
            raise ValueError(f"Unknown MCP transport for server {server.name!r}: {server.transport}")

        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[server.name] = session

        tools_result = await session.list_tools()
        for t in tools_result.tools:
            self._tools.append(McpToolAdapter(session, t, server.name))
        logger.info("mcp.connected", server=server.name, tool_count=len(tools_result.tools))

    def session(self, server_name: str) -> Optional[ClientSession]:
        return self._sessions.get(server_name)

    async def close(self) -> None:
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tools.clear()
