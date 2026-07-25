# src/codegraphcontext/api/mcp_sse.py
import json
import asyncio
import logging
import anyio
from fastapi import Request, Response
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ServerCapabilities, ToolsCapability
from mcp.server.sse import SseServerTransport
from codegraphcontext.api.router import get_server
from codegraphcontext.server import _strip_workspace_prefix, _apply_response_token_limit

logger = logging.getLogger(__name__)

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
    
    result = await server.handle_tool_call(name, args)
    result = _strip_workspace_prefix(result)
    
    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]
    
    response_text = json.dumps(result, indent=2)
    response_text = _apply_response_token_limit(name, response_text)
    return [TextContent(type="text", text=response_text)]

# Create the SSE transport.
sse = SseServerTransport("/api/v1/mcp/messages")

async def handle_sse(request: Request):
    """Entry point for the SSE connection."""
    logger.info("SSE client connected")
    try:
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
    except anyio.EndOfStream:
        logger.debug("SSE client disconnected cleanly (stream ended)")
    except Exception as exc:
        logger.debug("SSE connection closed: %s", type(exc).__name__)
    finally:
        logger.info("SSE client disconnected — handler exited, resources freed")


async def handle_messages(request: Request):
    """Endpoint for receiving messages from the client.

    Uses a buffer framing collector to ensure the full JSON-RPC payload
    is received before processing. This prevents crashes caused by large
    responses being split across SSE line boundaries.
    """
    # Buffer the complete request body before any parsing occurs.
    # request.body() accumulates all chunks, preventing partial JSON reads.
    raw_body = await request.body()

    try:
        json.loads(raw_body)
    except json.JSONDecodeError as e:
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: incomplete or malformed JSON-RPC message: {e}"
                },
                "id": None
            }),
            status_code=400,
            media_type="application/json"
        )

    try:
        await sse.handle_post_message(request.scope, request.receive, request._send)
    except Exception as exc:
        logger.debug("Message handler closed: %s", type(exc).__name__)
