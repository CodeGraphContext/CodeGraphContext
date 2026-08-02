# src/codegraphcontext/api/telemetry.py
import asyncio
import json
import logging
from typing import Any, Dict, AsyncGenerator

logger = logging.getLogger(__name__)

class TelemetryEventBus:
    """
    A simple pub/sub event bus for telemetry events.
    Allows the backend to emit events (like 'node_created') and 
    FastAPI SSE endpoints to subscribe and stream them to clients.
    """
    def __init__(self):
        self._subscribers = set()
        # Maintain a snapshot of the latest metrics for new subscribers
        self._current_metrics = {
            "active_repositories": 0,
            "files_analyzed": 0,
            "graph_nodes_created": 0,
            "indexing_rate": 0
        }

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream. Yields JSON strings."""
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        
        # Immediately send the current metrics snapshot to the new subscriber
        try:
            snapshot_event = json.dumps({
                "event": "metrics_snapshot",
                "data": self._current_metrics
            })
            await queue.put(snapshot_event)
        except Exception as e:
            logger.error(f"Error sending snapshot: {e}")

        try:
            while True:
                msg = await queue.get()
                yield msg
        finally:
            self._subscribers.remove(queue)

    def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to all subscribers."""
        if not self._subscribers:
            return  # No point in serializing if no one is listening

        # Update snapshot if this is a metrics update
        if event_type == "metrics_update":
            self._current_metrics.update(data)

        message = json.dumps({
            "event": event_type,
            "data": data
        })

        for queue in self._subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Telemetry subscriber queue full, dropping message")

# Global singleton event bus
telemetry_bus = TelemetryEventBus()
