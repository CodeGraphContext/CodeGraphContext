# src/codegraphcontext/core/read_timeout.py
"""Per-statement time ceilings for read-only tool queries.

Without a ceiling one exponential read (``find_all_callers`` on a hub
function, a user's ``execute_cypher_query``) ran for tens of minutes. The MCP
server handles requests one at a time, so that single call also blocked every
later request until it finished.

``read_driver(db_manager, graph_name)`` is the one way a read path gets a
driver. For Neo4j-protocol backends (``neo4j``, ``nornic``) it returns a proxy
that sends every string statement as ``neo4j.Query(text, timeout=T)``; the
server then aborts the transaction after *T* seconds. Every other backend gets
the manager's own driver back unchanged: Kùzu, LadybugDB and FalkorDB have no
per-statement timeout in their drivers, and their session wrappers do not
accept ``neo4j.Query``.

Only a real ``neo4j.Driver`` (or CGC's ``Neo4jDriverWrapper`` /
``NornicDriverWrapper`` around one) is wrapped; a stub that merely reports a
``neo4j`` backend is not.

The ceiling *T* depends on the tool. ``server.handle_tool_call`` sets
:data:`current_tool` before it runs the handler in a worker thread
(``asyncio.to_thread`` copies the context), and ``read_driver`` reads it.
:func:`codegraphcontext.utils.tool_limits.get_tool_query_timeout` resolves the
value from the ``TOOL_QUERY_TIMEOUTS`` config. The read-only CLI commands go
through ``read_driver`` as well: CodeFinder-backed ones (``cgc analyze …``,
``cgc find …``), ``cgc query`` (the execute_cypher_query ceiling),
``cgc stats`` (get_repository_stats), ``cgc export`` (export_diagram, via
:func:`tool_scope`), the offline visualization and the ``cgc visualize`` web
server; the others get the default. Commands that write (index, clean,
bundle import) and connection probes do not
(tests/unit/tools/test_read_paths_use_read_driver.py lists them). A ceiling
of 0 disables the timeout, and ``read_driver`` then returns the driver
unchanged.

Session proxy:

* ``__enter__``/``__exit__`` delegate; ``__enter__`` returns the proxy.
* ``run(str, …)`` becomes ``run(Query(str, timeout=T), …)``.
* ``run(Query, …)`` passes the caller's Query object through unchanged: a
  caller that sets its own timeout keeps it.
* ``execute_read``, ``execute_write``, ``begin_transaction`` and every
  other attribute pass through via ``__getattr__``; ``close``/``__exit__``
  delegate and translate a timeout raised while closing. Managed transactions
  are not wrapped; CodeFinder and the read handlers don't use them.

Neo4j reports a client timeout when the result is consumed, not when ``run``
returns, so ``run`` returns a result proxy. The proxy turns the driver's
``TransactionTimedOut*`` error into :class:`ReadQueryTimeout`, whose message
names the tool, the ceiling and how to raise it.

Writes never come through here. The indexing pipeline, the watcher and bundle
import get their drivers from ``db_manager.get_driver()`` directly, and
CodeFinder only reads (``tests/unit/tools/test_read_paths_use_read_driver.py``
enforces both).
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator, Optional

#: The MCP tool whose handler is running in this context (None: CLI / library use).
current_tool: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("cgc_current_tool", default=None)

#: Every ReadQueryTimeout raised in this tool call is appended here (see
#: tool_call_scope): a handler that catches the error and wraps it — or falls
#: back to another query — cannot make a timed-out call look successful.
timeout_log: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar("cgc_read_timeouts", default=None)

#: Backends that speak the Neo4j protocol and honour ``Query(timeout=…)``.
TIMEOUT_BACKENDS = frozenset({"neo4j", "nornic"})

_TIMEOUT_CODE_MARKER = "TransactionTimedOut"


class ReadQueryTimeout(RuntimeError):
    """A read statement ran past its tool's ceiling and the database aborted it."""

    def __init__(self, tool: Optional[str], timeout_s: float, cause: Optional[BaseException] = None):
        self.tool = tool
        self.timeout_s = timeout_s
        self.cause = cause
        who = f"tool '{tool}'" if tool else "this command"
        super().__init__(
            f"Read query timed out: it exceeded the {timeout_s:g}s ceiling for {who} and the database "
            "aborted it. Narrow the query (pass repo_path or a file path, lower the depth) or raise the "
            "ceiling with the TOOL_QUERY_TIMEOUTS config key, e.g. "
            f"cgc config set TOOL_QUERY_TIMEOUTS '{{\"{tool or 'default'}\": {int(timeout_s * 2)}}}' "
            "(0 disables the ceiling)."
        )


def _timeout(tool: Optional[str], timeout_s: float, cause: BaseException) -> "ReadQueryTimeout":
    exc = ReadQueryTimeout(tool, timeout_s, cause)
    log = timeout_log.get()
    if log is not None:
        log.append(exc)
    return exc


def timeout_error(exc: "ReadQueryTimeout", **extra: Any) -> dict:
    """The one error shape every tool returns for a read timeout."""
    return {"error": str(exc), "timed_out": True, "timeout_s": exc.timeout_s, "tool": exc.tool, **extra}


def is_timeout_error(exc: BaseException) -> bool:
    """True for the Neo4j driver's client-configured transaction timeout."""
    code = getattr(exc, "code", None) or ""
    return _TIMEOUT_CODE_MARKER in str(code)


def _backend_of(db_manager: Any) -> Optional[str]:
    getter = getattr(db_manager, "get_backend_type", None)
    if not callable(getter):
        return None  # unknown manager (tests, stubs): never wrap
    try:
        backend = getter()
    except Exception:
        return None
    return backend if isinstance(backend, str) else None


def is_neo4j_driver(driver: Any) -> bool:
    """A ``neo4j.Driver``, or one of CGC's thin wrappers around one (``_driver``).

    Only such a driver honours ``Query(timeout=…)``; anything else (a stub, a
    test double, another library) is never handed a ``neo4j.Query``.
    """
    try:
        from neo4j import Driver
    except ImportError:
        return False
    for _ in range(3):
        if isinstance(driver, Driver):
            return True
        driver = getattr(driver, "_driver", None)
        if driver is None:
            return False
    return False


def read_driver(db_manager: Any, graph_name: Optional[str] = None, tool: Optional[str] = None):
    """The manager's driver for read-only queries, with the tool's ceiling applied.

    Returns ``db_manager.get_driver(graph_name)`` itself for backends other
    than neo4j/nornic, for anything that is not a Neo4j driver, and when the
    ceiling is 0.
    """
    driver = db_manager.get_driver(graph_name)
    if _backend_of(db_manager) not in TIMEOUT_BACKENDS or not is_neo4j_driver(driver):
        return driver
    from ..utils.tool_limits import get_tool_query_timeout

    tool = tool if tool is not None else current_tool.get()
    timeout_s = get_tool_query_timeout(tool)
    if not timeout_s:
        return driver
    return TimeoutReadDriver(driver, timeout_s, tool)


@contextlib.contextmanager
def tool_scope(tool: Optional[str]) -> Iterator[None]:
    """Run the block as *tool* (its ceiling applies), e.g. a CLI command."""
    token = current_tool.set(tool)
    try:
        yield
    finally:
        current_tool.reset(token)


@contextlib.contextmanager
def tool_call_scope(tool: Optional[str]) -> Iterator[list]:
    """One MCP tool call: *tool*'s ceiling applies, and the timeouts raised are collected.

    ``server.handle_tool_call`` wraps every handler in this; if the list is
    non-empty afterwards, the call's answer is :func:`timeout_error`.
    """
    log: list = []
    tool_token = current_tool.set(tool)
    log_token = timeout_log.set(log)
    try:
        yield log
    finally:
        timeout_log.reset(log_token)
        current_tool.reset(tool_token)


class TimeoutReadDriver:
    """Driver proxy whose sessions send string statements with a timeout."""

    def __init__(self, driver: Any, timeout_s: float, tool: Optional[str] = None):
        self._driver = driver
        self.timeout_s = timeout_s
        self.tool = tool

    @property
    def wrapped(self) -> Any:
        return self._driver

    def session(self, *args: Any, **kwargs: Any) -> "TimeoutReadSession":
        return TimeoutReadSession(self._driver.session(*args, **kwargs), self.timeout_s, self.tool)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._driver, name)


class TimeoutReadSession:
    """Session proxy: see the module docstring."""

    def __init__(self, session: Any, timeout_s: float, tool: Optional[str]):
        self._session = session
        self._timeout_s = timeout_s
        self._tool = tool

    def __enter__(self) -> "TimeoutReadSession":
        self._session.__enter__()
        return self

    def __exit__(self, *exc: Any) -> Any:
        try:
            return self._session.__exit__(*exc)
        except Exception as err:  # closing consumes an unread result: it can time out too
            if is_timeout_error(err):
                raise _timeout(self._tool, self._timeout_s, err) from err
            raise

    def close(self) -> Any:
        try:
            return self._session.close()
        except Exception as err:
            if is_timeout_error(err):
                raise _timeout(self._tool, self._timeout_s, err) from err
            raise

    def run(self, query: Any, parameters: Optional[dict] = None, **kwargs: Any) -> "TimeoutReadResult":
        if isinstance(query, str):
            from neo4j import Query

            query = Query(query, timeout=self._timeout_s)
        try:
            # forward exactly what the caller passed: some session shims accept
            # parameters only as keyword arguments
            if parameters is None:
                result = self._session.run(query, **kwargs)
            else:
                result = self._session.run(query, parameters, **kwargs)
        except Exception as exc:
            if is_timeout_error(exc):
                raise _timeout(self._tool, self._timeout_s, exc) from exc
            raise
        return TimeoutReadResult(result, self._timeout_s, self._tool)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


class TimeoutReadResult:
    """Result proxy: a timeout raised while consuming becomes ReadQueryTimeout."""

    def __init__(self, result: Any, timeout_s: float, tool: Optional[str]):
        self._result = result
        self._timeout_s = timeout_s
        self._tool = tool

    def _translate(self, exc: BaseException) -> BaseException:
        if is_timeout_error(exc):
            return _timeout(self._tool, self._timeout_s, exc)
        return exc

    def __iter__(self) -> "TimeoutReadResult":
        self._iter = None  # created lazily in __next__, inside the translation
        return self

    def __next__(self) -> Any:
        try:
            if getattr(self, "_iter", None) is None:
                self._iter = iter(self._result)
            return next(self._iter)
        except StopIteration:
            raise
        except Exception as exc:
            translated = self._translate(exc)
            if translated is exc:
                raise
            raise translated from exc

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._result, name)
        if not callable(attr):
            return attr

        def call(*args: Any, **kwargs: Any) -> Any:
            try:
                return attr(*args, **kwargs)
            except Exception as exc:
                translated = self._translate(exc)
                if translated is exc:
                    raise
                raise translated from exc

        return call
