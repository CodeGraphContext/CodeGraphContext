# src/codegraphcontext/tools/indexing/phase_timings.py
"""Wall-clock seconds per phase of one full indexing run.

The pipelines (``pipeline.run_tree_sitter_index_async``, ``scip_pipeline``)
wrap each of their existing phase blocks in ``timings.phase(name)``; the index
summary reports ``timings.as_dict()`` as ``phase_seconds``. Only phases that
ran appear, in ``INDEX_PHASES`` order (pipeline order).

Phases may nest: a nested phase's seconds are its own and are subtracted from
the enclosing phase, so every second is attributed to exactly one phase and
the phases never add up to more than the run. The writer uses this to split
the IMPORTS edges out of the per-file write (``write_imports`` inside
``write_nodes``): it cannot see the pipeline's ``PhaseTimings``, so the run
publishes it through a context variable (``recording``) and the writer opens
``active_phase("write_imports")``, a no-op outside an indexing run (the
watcher's incremental writes, tests). The context variable keeps two runs that
share one writer (concurrent MCP jobs of one ``GraphBuilder``) apart.

Phases are sequential within a run: a nested phase may be opened from a
worker thread while its parent is open on the event loop, but two phases are
never open side by side. Concurrent work inside one phase (the parse loop) is
timed as that phase's wall time, not as a sum of per-file CPU time.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from typing import Callable, ContextManager, Dict, Iterator, List, Optional, Sequence

#: Every phase a full index can report, in pipeline order. Tree-sitter path:
#: discover, pre_scan, parse, write_nodes/write_imports, inheritance, type_links,
#: decorated_by, calls_resolve, calls_write, framework_links and the optional
#: embeddings / inherit_reresolve. SCIP path:
#: discover, scip_index, pre_scan, write_nodes/write_imports, supplement,
#: inheritance, calls_resolve, calls_write, scip_calls.
INDEX_PHASES: tuple = (
    "discover",           # repository node + file discovery
    "scip_index",         # SCIP indexer run + index parse
    "pre_scan",           # imports map
    "parse",              # concurrent per-file parse (wall time)
    "write_nodes",        # per-file node / CONTAINS / parameter writes (IMPORTS excluded)
    "write_imports",      # per-file IMPORTS edges (and their Module nodes)
    "supplement",         # SCIP: Tree-sitter parse + write of the files SCIP missed
    "inheritance",        # INHERITS / IMPLEMENTS resolution + writes
    "type_links",         # EMBEDS, COMPANION_OF, PARTIAL_OF, PART_OF, METACLASS, BINDS, PREVIEWS
    "decorated_by",       # DECORATED_BY
    "calls_resolve",      # CALLS resolution
    "calls_write",        # CALLS writes
    "scip_calls",         # SCIP CALLS edges
    "framework_links",    # C++ class links, CONTAINS repair, Spring, Maven/Gradle, ORM, MyBatis
    "embeddings",         # ENABLE_VECTOR_RESOLVE
    "inherit_reresolve",  # ENABLE_INHERIT_RESOLVE
)

#: decimals of every reported duration (milliseconds)
SECONDS_DECIMALS = 3


class PhaseTimings:
    """Accumulated wall-clock seconds per phase name (``time.perf_counter``).

    ``phase(name)`` times a block (repeated blocks accumulate); ``add(name, s)``
    records seconds measured elsewhere. A name outside the vocabulary raises
    ``ValueError``: a typo must not become a phase of its own.
    """

    def __init__(self, phases: Sequence[str] = INDEX_PHASES,
                 clock: Callable[[], float] = time.perf_counter):
        self._order = tuple(phases)
        self._known = frozenset(self._order)
        self._clock = clock
        self._seconds: Dict[str, float] = {}
        self._open: List[str] = []
        self._lock = threading.Lock()
        self.started = clock()

    def _check(self, name: str) -> None:
        if name not in self._known:
            raise ValueError(f"unknown index phase {name!r}; known phases: {', '.join(self._order)}")

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Time the enclosed block as *name*, net of any phase nested in it."""
        self._check(name)
        with self._lock:
            self._open.append(name)
            self._seconds.setdefault(name, 0.0)
        start = self._clock()
        try:
            yield
        finally:
            elapsed = self._clock() - start
            with self._lock:
                self._open.pop()
                self._seconds[name] += elapsed
                if self._open:
                    self._seconds[self._open[-1]] -= elapsed

    def add(self, name: str, seconds: float) -> None:
        self._check(name)
        with self._lock:
            self._seconds[name] = self._seconds.get(name, 0.0) + max(0.0, float(seconds))

    def seconds(self, *names: str) -> float:
        """The summed seconds of *names* (phases that did not run count 0)."""
        for name in names:
            self._check(name)
        with self._lock:
            return sum(self._seconds.get(name, 0.0) for name in names)

    def elapsed(self) -> float:
        """Seconds since this object was created (the run's wall time so far)."""
        return self._clock() - self.started

    def as_dict(self) -> Dict[str, float]:
        """``{phase: seconds}`` of the phases that ran, in vocabulary order, rounded to ms."""
        with self._lock:
            return {
                name: round(max(0.0, self._seconds[name]), SECONDS_DECIMALS)
                for name in self._order
                if name in self._seconds
            }


_ACTIVE: ContextVar[Optional[PhaseTimings]] = ContextVar("cgc_index_phase_timings", default=None)


@contextmanager
def recording(timings: PhaseTimings) -> Iterator[PhaseTimings]:
    """Make *timings* the run's timings for ``active_phase`` (this context and the
    worker threads it starts with ``asyncio.to_thread``, which copies the context)."""
    token = _ACTIVE.set(timings)
    try:
        yield timings
    finally:
        _ACTIVE.reset(token)


def active_phase(name: str) -> ContextManager[None]:
    """``phase(name)`` of the indexing run in progress, or a no-op outside one."""
    timings = _ACTIVE.get()
    return timings.phase(name) if timings is not None else nullcontext()
