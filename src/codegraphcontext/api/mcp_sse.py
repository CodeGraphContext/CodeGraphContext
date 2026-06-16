# src/codegraphcontext/api/mcp_sse.py
import json
import asyncio
from fastapi import Request
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ServerCapabilities, ToolsCapability
from mcp.server.sse import SseServerTransport

from codegraphcontext.api.router import get_server
from codegraphcontext.server import _strip_workspace_prefix, _apply_response_token_limit

# Create the MCP Server instance using the SDK
mcp_server = Server("CodeGraphContext")

@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools (honors disabledTools from mcp.json)."""
    server = get_server()
    tools = []
    for name, defn in server.tools.items():
        tools.append(Tool(
            name=name,
            description=defn["description"],
            inputSchema=defn["inputSchema"]
        ))
    return tools

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Handle tool execution."""
    server = get_server()
    args = arguments or {}
    
    # Execute via the existing handler logic
    result = await server.handle_tool_call(name, args)
    result = _strip_workspace_prefix(result)
    
    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]
    
    # Format result as JSON string for the AI, with the same token budget
    # the stdio transport applies.
    response_text = json.dumps(result, indent=2)
    response_text = _apply_response_token_limit(name, response_text)
    return [TextContent(type="text", text=response_text)]

# Create the SSE transport. 
# The messages_url is where the client will POST JSON-RPC messages.
sse = SseServerTransport("/api/v1/mcp/messages")

async def handle_sse(request: Request):
    """Entry point for the SSE connection."""
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="CodeGraphContext",
                server_version="0.1.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False)
                )
            )
        )

async def handle_messages(request: Request):
    """Endpoint for receiving messages from the client."""
    await sse.handle_post_message(request.scope, request.receive, request._send)
