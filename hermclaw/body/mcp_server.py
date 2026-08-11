"""MCP (Model Context Protocol) Server.

Exposes Hermclaw's tools to external MCP clients (VS Code, Claude Desktop,
other agents) over stdio transport. This makes Hermclaw a tool provider
that any MCP-compatible AI can consume.

Usage:
    hermclaw mcp-server

Protocol: JSON-RPC 2.0 over stdin/stdout
Spec: https://modelcontextprotocol.io
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class MCPServer:
    """Minimal MCP server exposing Hermclaw tools via stdio.

    Implements the required MCP lifecycle:
    - initialize / initialized
    - tools/list
    - tools/call
    """

    def __init__(self, tool_dispatcher: Any) -> None:
        self._dispatcher = tool_dispatcher
        self._initialized = False

    async def handle_message(self, message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Process a single JSON-RPC message and return the response."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return self._handle_initialize(msg_id, params)
        elif method == "notifications/initialized":
            self._initialized = True
            return None  # Notification, no response
        elif method == "tools/list":
            return self._handle_tools_list(msg_id)
        elif method == "tools/call":
            return await self._handle_tools_call(msg_id, params)
        elif method == "ping":
            return self._success(msg_id, {})
        else:
            return self._error(msg_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, msg_id: Any, params: dict) -> dict:
        """Handle MCP initialize handshake."""
        logger.info("mcp.initialize", client_info=params.get("clientInfo"))
        return self._success(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "hermclaw",
                "version": "0.1.0",
            },
        })

    def _handle_tools_list(self, msg_id: Any) -> dict:
        """Return all registered tools as MCP tool definitions."""
        specs = self._dispatcher.specs()
        tools = []
        for spec in specs:
            tool = {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.parameters or {"type": "object", "properties": {}},
            }
            tools.append(tool)

        logger.info("mcp.tools_list", count=len(tools))
        return self._success(msg_id, {"tools": tools})

    async def _handle_tools_call(self, msg_id: Any, params: dict) -> dict:
        """Execute a tool call and return the result."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.info("mcp.tools_call", tool=name)

        try:
            result = await self._dispatcher.dispatch(name, arguments)

            content = []
            if result.ok:
                content.append({
                    "type": "text",
                    "text": result.output or "Tool executed successfully.",
                })
            else:
                content.append({
                    "type": "text",
                    "text": result.error or "Tool execution failed.",
                })

            return self._success(msg_id, {
                "content": content,
                "isError": not result.ok,
            })
        except Exception as exc:
            logger.error("mcp.tool_call_failed", tool=name, error=str(exc))
            return self._success(msg_id, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            })

    @staticmethod
    def _success(msg_id: Any, result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


async def run_mcp_stdio(tool_dispatcher: Any) -> None:
    """Run the MCP server on stdin/stdout.

    Reads JSON-RPC messages from stdin (one per line),
    processes them, and writes responses to stdout.
    """
    server = MCPServer(tool_dispatcher)
    reader = asyncio.StreamReader()

    # Set up stdin reader
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin.buffer,
    )

    logger.info("mcp.server_started", transport="stdio")

    while True:
        try:
            line = await reader.readline()
            if not line:
                break  # EOF

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                message = json.loads(line_str)
            except json.JSONDecodeError as exc:
                error_resp = MCPServer._error(None, -32700, f"Parse error: {exc}")
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()
                continue

            response = await server.handle_message(message)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except Exception as exc:
            logger.error("mcp.read_error", error=str(exc))
            break

    logger.info("mcp.server_stopped")
