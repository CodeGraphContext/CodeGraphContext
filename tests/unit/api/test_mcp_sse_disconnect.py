import pytest
import anyio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.scope = {}
    request.receive = AsyncMock()
    request._send = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_handle_sse_exits_cleanly_on_end_of_stream(mock_request):
    @asynccontextmanager
    async def _raise_end_of_stream(*args, **kwargs):
        raise anyio.EndOfStream()
        yield  # noqa: unreachable — required to make this an async generator

    with patch("codegraphcontext.api.mcp_sse.sse") as mock_sse:
        mock_sse.connect_sse = _raise_end_of_stream
        from codegraphcontext.api.mcp_sse import handle_sse
        await handle_sse(mock_request)  # must not raise


@pytest.mark.asyncio
async def test_handle_sse_exits_cleanly_on_generic_exception(mock_request):
    @asynccontextmanager
    async def _raise_generic(*args, **kwargs):
        raise RuntimeError("simulated connection drop")
        yield  # noqa: unreachable

    with patch("codegraphcontext.api.mcp_sse.sse") as mock_sse:
        mock_sse.connect_sse = _raise_generic
        from codegraphcontext.api.mcp_sse import handle_sse
        await handle_sse(mock_request)  # must not raise


@pytest.mark.asyncio
async def test_handle_messages_exits_cleanly_on_disconnect(mock_request):
    with patch("codegraphcontext.api.mcp_sse.sse") as mock_sse:
        mock_sse.handle_post_message = AsyncMock(side_effect=RuntimeError("client gone"))
        from codegraphcontext.api.mcp_sse import handle_messages
        await handle_messages(mock_request)  # must not raise
