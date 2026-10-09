# src/codegraphcontext/api/mcp_sse.py
import json
import logging

import anyio
from fastapi import Request, Response
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from codegraphcontext.api.router import get_server
from codegraphcontext.server import _strip_workspace_prefix, _apply_response_token_limit

logger = logging.getLogger(__name__)


async def handle_list_tools(ctx, params) -> ListToolsResult:
    """List available tools (honors disabledTools from mcp.json)."""
    server = get_server()
    tools = []
    for name, defn in server.tools.items():
        tools.append(Tool(
            name=name,
            description=defn["description"],
            inputSchema=defn["inputSchema"]
        ))
    return ListToolsResult(tools=tools)


async def handle_call_tool(ctx, params) -> CallToolResult:
    """Handle tool execution."""
    server = get_server()
    args = params.arguments or {}

    result = await server.handle_tool_call(params.name, args)
    result = _strip_workspace_prefix(result)

    if "error" in result:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {result['error']}")],
            isError=True,
        )

    response_text = json.dumps(result, indent=2)
    response_text = _apply_response_token_limit(params.name, response_text)
    return CallToolResult(content=[TextContent(type="text", text=response_text)])


# Streamable HTTP server (spec 2026-07-28), mounted at /api/v1/mcp in app.py.
mcp_server = Server(
    "CodeGraphContext",
    version="0.1.0",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


# --- Deprecated HTTP+SSE transport (2024-11-05) -----------------------------
# Kept alongside the Streamable HTTP mount above so clients still configured
# with the old /api/v1/mcp/sse URL (see docs/INTEGRATION_GUIDE.md) keep
# working. New clients should use the single /api/v1/mcp endpoint instead;
# this is eligible for removal once existing client configs have migrated.
sse = SseServerTransport("/api/v1/mcp/messages")


class _AlreadySentResponse(Response):
    """Placeholder for a response the MCP transport wrote itself.

    Both handlers below hand the raw ASGI ``send`` to the SDK, which emits the
    complete response. FastAPI still does ``await endpoint(request)`` followed
    by ``await response(...)``, so returning ``None`` raises ``TypeError:
    'NoneType' object is not callable`` and returning a real ``Response``
    starts a second response on a finished ASGI cycle. This satisfies FastAPI
    while putting nothing on the wire.
    """

    async def __call__(self, scope, receive, send) -> None:
        return


class _SendTracker:
    """ASGI ``send`` wrapper that records whether a response was started."""

    def __init__(self, send):
        self._send = send
        self.response_started = False

    async def __call__(self, message) -> None:
        if message.get("type") == "http.response.start":
            self.response_started = True
        await self._send(message)


async def handle_sse(request: Request):
    """Entry point for the legacy SSE connection."""
    logger.info("Legacy SSE client connected")
    sender = _SendTracker(request._send)
    try:
        async with sse.connect_sse(request.scope, request.receive, sender) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
    except anyio.EndOfStream:
        logger.debug("SSE client disconnected cleanly (stream ended)")
    except Exception as exc:
        logger.debug("SSE connection closed: %s", type(exc).__name__)
    finally:
        logger.info("SSE client disconnected — handler exited, resources freed")
    if sender.response_started:
        return _AlreadySentResponse()
    # connect_sse bailed out before writing anything (e.g. rejected origin).
    return Response(status_code=500, content="SSE connection could not be established")


async def handle_messages(request: Request):
    """Legacy endpoint for receiving messages from the client.

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

    # `handle_post_message` builds its own Request and awaits `.body()` again.
    # Starlette caches a body on the Request instance, not in the scope, so
    # handing it the raw `receive` would make it wait for a body that has
    # already been drained above — the POST hangs until the client gives up and
    # the message never reaches the session. Replay the buffered bytes instead.
    async def replay_receive() -> dict:
        return {"type": "http.request", "body": raw_body, "more_body": False}

    sender = _SendTracker(request._send)
    try:
        await sse.handle_post_message(request.scope, replay_receive, sender)
    except Exception as exc:
        logger.debug("Message handler closed: %s", type(exc).__name__)

    if sender.response_started:
        return _AlreadySentResponse()
    return Response(status_code=202, content="Accepted")
