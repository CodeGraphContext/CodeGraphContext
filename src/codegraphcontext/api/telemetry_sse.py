# src/codegraphcontext/api/telemetry_sse.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
from .telemetry import telemetry_bus

router = APIRouter()

@router.get("/sse")
async def telemetry_stream():
    """
    SSE endpoint for realtime telemetry dashboard.
    Streams metrics and indexing events from the TelemetryEventBus.
    """
    async def event_generator():
        try:
            async for message in telemetry_bus.subscribe():
                # Server-Sent Events format:
                # data: <json>\n\n
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
