"""Read-query time ceilings.

core/read_timeout.py: ``read_driver`` wraps Neo4j/Nornic drivers so every
string statement becomes ``neo4j.Query(text, timeout=T)``; every other backend
gets its driver back unchanged. T is per tool (``current_tool``, set by
``server.handle_tool_call``), from ``TOOL_QUERY_TIMEOUTS``.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

neo4j = pytest.importorskip("neo4j")

from codegraphcontext.core import read_timeout as RT  # noqa: E402
from codegraphcontext.utils import tool_limits as TL  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_drivers_count_as_neo4j(monkeypatch, request):
    """The stubs below stand in for a neo4j.Driver (is_neo4j_driver has its own tests)."""
    if request.node.name != "test_only_real_neo4j_drivers_are_wrapped":
        monkeypatch.setattr(RT, "is_neo4j_driver", lambda d: True)


@pytest.fixture
def config(monkeypatch):
    """Set TOOL_QUERY_TIMEOUTS for the test (None: not configured)."""
    values = {}
    monkeypatch.setattr("codegraphcontext.cli.config_manager.get_config_value", lambda key: values.get(key))

    def set_timeouts(mapping):
        values["TOOL_QUERY_TIMEOUTS"] = json.dumps(mapping) if mapping is not None else None

    return set_timeouts


class _Result:
    def __init__(self, rows, fail=None):
        self.rows, self.fail = rows, fail

    def data(self):
        if self.fail:
            raise self.fail
        return list(self.rows)

    def single(self):
        if self.fail:
            raise self.fail
        return self.rows[0] if self.rows else None

    def __iter__(self):
        if self.fail:  # the server aborts before the first record
            raise self.fail
        yield from self.rows

    keys_value = ("a",)


class _Session:
    def __init__(self, log, fail=None):
        self.log, self.fail = log, fail
        self.entered = self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True
        return False

    def run(self, query, parameters=None, **kwargs):
        self.log.append((query, parameters, kwargs))
        return _Result([{"a": 1}], self.fail)

    def execute_read(self, fn, *a, **k):
        return ("execute_read", fn, a, k)

    def execute_write(self, fn, *a, **k):
        return ("execute_write", fn, a, k)

    def begin_transaction(self, **k):
        return ("tx", k)

    def close(self):
        return "closed"


class _Driver:
    def __init__(self, fail=None):
        self.log, self.fail, self.sessions = [], fail, []

    def session(self, **kwargs):
        s = _Session(self.log, self.fail)
        s.kwargs = kwargs
        self.sessions.append(s)
        return s

    def close(self):
        return "driver closed"


def _mgr(backend, driver):
    return SimpleNamespace(get_driver=lambda graph_name=None: driver, get_backend_type=lambda: backend)


_TIMEOUT_CODE = "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration"


def _timeout_error():
    """The driver's own exception for a client-configured timeout."""
    from neo4j.exceptions import Neo4jError

    hydrate = getattr(Neo4jError, "_hydrate_neo4j", None)
    if hydrate is not None:
        return hydrate(code=_TIMEOUT_CODE, message="The transaction has not completed within the timeout")

    class _Timeout(Exception):  # older drivers
        code = _TIMEOUT_CODE

    return _Timeout("timed out")


# ── the proxy ────────────────────────────────────────────────────────────────

def test_enter_exit_delegate_and_enter_returns_the_proxy(config):
    config(None)
    drv = _Driver()
    wrapped = RT.read_driver(_mgr("neo4j", drv))
    with wrapped.session(database="x") as s:
        assert isinstance(s, RT.TimeoutReadSession)
    inner = drv.sessions[0]
    assert inner.entered and inner.exited and inner.kwargs == {"database": "x"}


def test_string_query_becomes_a_query_with_the_ceiling(config):
    config(None)
    drv = _Driver()
    with RT.read_driver(_mgr("neo4j", drv)).session() as s:
        assert s.run("MATCH (n) RETURN n", {"p": 1}, q=2).data() == [{"a": 1}]
    query, params, kwargs = drv.log[0]
    assert isinstance(query, neo4j.Query)
    assert query.text == "MATCH (n) RETURN n" and query.timeout == TL.DEFAULT_TOOL_QUERY_TIMEOUT_S == 120
    assert params == {"p": 1} and kwargs == {"q": 2}


def test_query_object_passes_through_by_identity(config):
    config(None)
    drv = _Driver()
    own = neo4j.Query("RETURN 1", timeout=3)
    with RT.read_driver(_mgr("neo4j", drv)).session() as s:
        s.run(own)
    assert drv.log[0][0] is own


def test_managed_transactions_and_other_attributes_pass_through(config):
    config(None)
    drv = _Driver()
    wrapped = RT.read_driver(_mgr("nornic", drv))
    s = wrapped.session()
    fn = lambda tx: None  # noqa: E731
    assert s.execute_read(fn, 1) == ("execute_read", fn, (1,), {})
    assert s.execute_write(fn) == ("execute_write", fn, (), {})
    assert s.begin_transaction(timeout=5) == ("tx", {"timeout": 5})
    assert s.close() == "closed"
    assert wrapped.close() == "driver closed"
    assert drv.log == [], "managed transactions are not rewritten"


@pytest.mark.parametrize("backend", ["kuzudb", "ladybugdb", "falkordb", "falkordb-remote", "embedded"])
def test_other_backends_get_their_driver_unchanged(config, backend):
    config(None)
    drv = _Driver()
    assert RT.read_driver(_mgr(backend, drv)) is drv


def test_unknown_manager_is_never_wrapped(config):
    config(None)
    drv = _Driver()
    assert RT.read_driver(SimpleNamespace(get_driver=lambda graph_name=None: drv)) is drv


def test_zero_disables(config):
    config({"default": 0})
    drv = _Driver()
    assert RT.read_driver(_mgr("neo4j", drv)) is drv


def test_graph_name_is_forwarded(config):
    config(None)
    seen = []
    mgr = SimpleNamespace(get_driver=lambda graph_name=None: seen.append(graph_name) or _Driver(),
                          get_backend_type=lambda: "falkordb")
    RT.read_driver(mgr, "g1")
    assert seen == ["g1"]


@pytest.mark.parametrize("where", ["data", "single", "iter"])
def test_a_timeout_becomes_a_named_tool_error(config, where):
    config({"find_dead_code": 7})
    drv = _Driver(fail=_timeout_error())
    with RT.tool_scope("find_dead_code"):
        wrapped = RT.read_driver(_mgr("neo4j", drv))
    with wrapped.session() as s:
        res = s.run("MATCH (n) RETURN n")
        with pytest.raises(RT.ReadQueryTimeout) as info:
            if where == "iter":
                list(res)
            else:
                getattr(res, where)()
    assert info.value.timeout_s == 7 and info.value.tool == "find_dead_code"
    msg = str(info.value)
    assert "7s ceiling" in msg and "find_dead_code" in msg and "TOOL_QUERY_TIMEOUTS" in msg


def test_other_errors_are_not_translated(config):
    config(None)
    drv = _Driver(fail=ValueError("boom"))
    with RT.read_driver(_mgr("neo4j", drv)).session() as s:
        with pytest.raises(ValueError):
            s.run("RETURN 1").data()


def test_non_callable_result_attributes_pass_through(config):
    config(None)
    with RT.read_driver(_mgr("neo4j", _Driver())).session() as s:
        assert s.run("RETURN 1").keys_value == ("a",)


# ── per-tool ceilings ────────────────────────────────────────────────────────

def test_builtin_ceilings(config):
    config(None)
    assert TL.get_tool_query_timeout(None) == 120
    assert TL.get_tool_query_timeout("find_code") == 120
    for heavy in ("find_dead_code", "generate_report", "get_repository_stats", "export_diagram", "execute_cypher_query"):
        assert TL.get_tool_query_timeout(heavy) == 300, heavy


def test_configured_ceilings_resolution_order(config):
    config({"find_code": 5, "default": 30})
    assert TL.get_tool_query_timeout("find_code") == 5
    assert TL.get_tool_query_timeout("find_dead_code") == 300  # built-in per-tool entry beats "default" (N4)
    assert TL.get_tool_query_timeout("find_callers") == 30
    assert TL.get_tool_query_timeout(None) == 30
    config({"find_dead_code": 600, "default": 30})
    assert TL.get_tool_query_timeout("find_dead_code") == 600
    config({"find_code": "junk", "other": -1})
    assert TL.get_tool_query_timeout("find_code") == 120       # unparseable: ignored
    assert TL.get_tool_query_timeout("other") == 120           # negative: ignored
    config({})
    assert TL.get_tool_query_timeout("x", default=9) == 9


def test_config_validation():
    from codegraphcontext.cli.config_manager import validate_config_value

    assert validate_config_value("TOOL_QUERY_TIMEOUTS", '{"default": 60, "find_dead_code": 0}')[0]
    assert not validate_config_value("TOOL_QUERY_TIMEOUTS", '{"x": -1}')[0]
    assert not validate_config_value("TOOL_QUERY_TIMEOUTS", '{"x": "5"}')[0]
    assert not validate_config_value("TOOL_QUERY_TIMEOUTS", "[1]")[0]
    assert not validate_config_value("TOOL_QUERY_TIMEOUTS", "{")[0]


def test_current_tool_picks_the_ceiling(config):
    config({"find_code": 11})
    drv = _Driver()
    with RT.tool_scope("find_code"):
        with RT.read_driver(_mgr("neo4j", drv)).session() as s:
            s.run("RETURN 1")
    assert drv.log[0][0].timeout == 11
    assert RT.current_tool.get() is None   # scope restored


def test_server_sets_current_tool_for_the_handler_thread(config):
    """handle_tool_call runs the handler via asyncio.to_thread, which copies the context."""
    from codegraphcontext.server import MCPServer

    config(None)
    seen = []
    server = MCPServer.__new__(MCPServer)
    server.disabled_tools = set()
    server._context_note_pending = False
    server.find_code_tool = lambda **args: seen.append(RT.current_tool.get()) or {"ok": True}
    assert asyncio.run(server.handle_tool_call("find_code", {"query": "x"})) == {"ok": True}
    assert seen == ["find_code"]
    assert RT.current_tool.get() is None


def test_codefinder_driver_goes_through_read_driver(config):
    from codegraphcontext.tools.code_finder import CodeFinder

    config({"default": 13})
    drv = _Driver()
    finder = CodeFinder(_mgr("neo4j", drv))
    assert isinstance(finder.driver, RT.TimeoutReadDriver) and finder.driver.timeout_s == 13
    kuzu = _Driver()
    assert CodeFinder(_mgr("kuzudb", kuzu)).driver is kuzu


def test_execute_cypher_query_reports_the_timeout(config):
    from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query

    config({"execute_cypher_query": 2})
    drv = _Driver(fail=_timeout_error())
    with RT.tool_scope("execute_cypher_query"):
        out = execute_cypher_query(_mgr("neo4j", drv), cypher_query="MATCH (n) RETURN n")
    assert out["timeout_s"] == 2 and "2s ceiling" in out["error"]
    assert drv.sessions[0].kwargs == {"default_access_mode": "READ"}


def test_only_real_neo4j_drivers_are_wrapped(config):
    """A stub reporting a neo4j backend is returned unchanged; a real driver (or CGC's wrapper) is wrapped."""
    from codegraphcontext.core.database import Neo4jDriverWrapper

    config(None)
    stub = _Driver()
    assert RT.read_driver(_mgr("neo4j", stub)) is stub
    real = neo4j.GraphDatabase.driver("bolt://127.0.0.1:1", auth=("x", "y"))  # no connection is opened
    try:
        assert isinstance(RT.read_driver(_mgr("neo4j", real)), RT.TimeoutReadDriver)
        wrapped = Neo4jDriverWrapper(real)
        assert RT.is_neo4j_driver(wrapped)
        assert isinstance(RT.read_driver(_mgr("nornic", wrapped)), RT.TimeoutReadDriver)
    finally:
        real.close()


def test_next_and_close_translate_timeouts(config):
    """N3: iteration via next() and a timeout raised while closing the session are translated."""
    config(None)
    drv = _Driver(fail=_timeout_error())
    s = RT.read_driver(_mgr("neo4j", drv)).session()
    res = s.run("RETURN 1")
    with pytest.raises(RT.ReadQueryTimeout):
        next(iter(res))

    class _ClosingSession(_Session):
        def __exit__(self, *exc):
            raise _timeout_error()

        def close(self):
            raise _timeout_error()

    drv2 = _Driver()
    drv2.session = lambda **k: _ClosingSession([])
    with pytest.raises(RT.ReadQueryTimeout):
        with RT.read_driver(_mgr("neo4j", drv2)).session():
            pass
    with pytest.raises(RT.ReadQueryTimeout):
        RT.read_driver(_mgr("neo4j", drv2)).session().close()


def test_timeouts_are_logged_in_a_tool_call(config):
    config(None)
    drv = _Driver(fail=_timeout_error())
    with RT.tool_call_scope("find_code") as log:
        with RT.read_driver(_mgr("neo4j", drv)).session() as s:
            try:
                s.run("RETURN 1").data()
            except RT.ReadQueryTimeout:
                pass  # a handler that swallows it
    assert len(log) == 1 and log[0].tool == "find_code"
    assert RT.timeout_log.get() is None and RT.current_tool.get() is None
    err = RT.timeout_error(log[0], query="x")
    assert err["timed_out"] is True and err["timeout_s"] == 120 and err["query"] == "x"
