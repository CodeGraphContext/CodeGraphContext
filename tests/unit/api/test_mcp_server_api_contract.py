"""
Guards the `mcp` low-level server API that `api/mcp_sse.py` is built on.

`mcp_sse` registers its handlers with the `@mcp_server.list_tools()` and
`@mcp_server.call_tool()` decorators. Both were removed from the low-level
`Server` in mcp 2.0.0. Because the dependency was pinned `mcp>=1.0.0` with no
upper bound, CI resolved 2.0.0 the day it was published and every job died
during collection with:

    AttributeError: 'Server' object has no attribute 'list_tools'

An import-time AttributeError inside an unrelated test module is a poor signal
for "your MCP dependency is too new", so this test states the contract directly.
"""
import importlib.metadata as importlib_metadata

import pytest
from packaging.version import Version

from mcp.server import Server


REQUIRED_DECORATORS = ("list_tools", "call_tool")


@pytest.mark.parametrize("decorator", REQUIRED_DECORATORS)
def test_lowlevel_server_exposes_decorator(decorator):
    """api/mcp_sse.py cannot register its handlers without these."""
    assert hasattr(Server, decorator), (
        f"mcp.server.Server has no {decorator!r}. The installed mcp "
        f"({importlib_metadata.version('mcp')}) is incompatible with "
        f"api/mcp_sse.py, which registers handlers via @mcp_server.{decorator}(). "
        f"Either keep mcp<2 or port mcp_sse.py to the 2.x server API."
    )


def test_installed_mcp_is_within_the_supported_range():
    """Fail loudly on a major bump rather than deep inside an unrelated module."""
    installed = Version(importlib_metadata.version("mcp"))
    assert installed < Version("2"), (
        f"mcp {installed} is installed but api/mcp_sse.py targets the 1.x "
        f"low-level server API. Port mcp_sse.py before relaxing the cap in "
        f"pyproject.toml."
    )


def test_mcp_sse_module_imports():
    """The regression itself: this module failed to import under mcp 2.0.0."""
    import codegraphcontext.api.mcp_sse as mcp_sse

    assert mcp_sse.mcp_server is not None
