"""
Guards the `mcp` low-level server API that `api/mcp_sse.py` is built on.

`mcp_sse` constructs `Server(..., on_list_tools=..., on_call_tool=...)` and
serves it via `Server.streamable_http_app()`. Both were introduced in mcp 2.x;
mcp 1.x instead used the `@mcp_server.list_tools()`/`@mcp_server.call_tool()`
decorators (removed in 2.0.0) and the deprecated SSE transport. Because a
version bump on either side of that line changes the required API silently,
this test states the contract directly rather than letting an unrelated test
module die on an AttributeError/TypeError at import time.
"""
import importlib.metadata as importlib_metadata
import inspect

import pytest
from packaging.version import Version

from mcp.server import Server

REQUIRED_CONSTRUCTOR_KWARGS = ("on_list_tools", "on_call_tool")


@pytest.mark.parametrize("kwarg", REQUIRED_CONSTRUCTOR_KWARGS)
def test_lowlevel_server_accepts_constructor_kwarg(kwarg):
    """api/mcp_sse.py cannot register its handlers without these."""
    params = inspect.signature(Server.__init__).parameters
    assert kwarg in params, (
        f"mcp.server.Server.__init__ has no {kwarg!r} parameter. The installed mcp "
        f"({importlib_metadata.version('mcp')}) is incompatible with "
        f"api/mcp_sse.py, which constructs Server(..., {kwarg}=...)."
    )


def test_lowlevel_server_exposes_streamable_http_app():
    """api/mcp_sse.py/app.py mount Server.streamable_http_app()."""
    assert hasattr(Server, "streamable_http_app"), (
        f"mcp.server.Server has no streamable_http_app(). The installed mcp "
        f"({importlib_metadata.version('mcp')}) is incompatible with app.py's mount."
    )


def test_installed_mcp_is_within_the_supported_range():
    """Fail loudly on a major bump rather than deep inside an unrelated module."""
    installed = Version(importlib_metadata.version("mcp"))
    assert Version("2") <= installed < Version("3"), (
        f"mcp {installed} is installed but api/mcp_sse.py targets the 2.x "
        f"low-level server API (on_list_tools/on_call_tool constructor kwargs, "
        f"streamable_http_app()). Port mcp_sse.py before relaxing the pin in "
        f"pyproject.toml."
    )


def test_mcp_sse_module_imports():
    """The regression itself: this module failed to import under mcp 2.0.0's
    predecessor API break, and would again under a future 3.x break."""
    import codegraphcontext.api.mcp_sse as mcp_sse

    assert mcp_sse.mcp_server is not None
