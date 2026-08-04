"""A minimal real MCP server, used only by tests/test_mcp_client.py.
Spawned as a subprocess over stdio -- exercises McpClientManager against
an actual (if tiny) MCP server rather than a mock of the mcp package.
"""

import asyncio

from mcp import types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


async def list_tools_handler(ctx, params):
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="add",
                description="Add two numbers",
                inputSchema={
                    "type": "object",
                    "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                    "required": ["a", "b"],
                },
            )
        ]
    )


async def call_tool_handler(ctx, params):
    if params.name == "add":
        result = params.arguments["a"] + params.arguments["b"]
        return types.CallToolResult(content=[types.TextContent(type="text", text=str(result))], isError=False)
    return types.CallToolResult(content=[types.TextContent(type="text", text="unknown tool")], isError=True)


async def main() -> None:
    server = Server("test-server", version="0.1", on_list_tools=list_tools_handler, on_call_tool=call_tool_handler)
    async with stdio_server() as (read, write):
        await server.run(
            read, write,
            InitializationOptions(
                server_name="test-server", server_version="0.1",
                capabilities=server.get_capabilities(notification_options=None, experimental_capabilities={}),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
