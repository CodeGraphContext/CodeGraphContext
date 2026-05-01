"""Lightweight per-phase indexing profiling helpers.

Tracks query volume (`session.run`), batch-size behavior, wall-clock time, and
retry events during indexing runs. Instrumentation is environment-gated to keep
runtime overhead low outside experiments.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.Lock()
_PHASE = threading.local()
_STATE: Dict[str, Any] = {
    "enabled": False,
    "backend": None,
    "mode": None,
    "phase_counts": {},
    "phase_batch_totals": {},
    "phase_batch_samples": {},
    "phase_elapsed_s": {},
    "phase_start_times": {},
    "query_families": {},
    "oom_retries": 0,
    "deadlock_retries": 0,
}


def _is_enabled_env() -> bool:
    value = (os.getenv("CGC_INDEX_PROFILING", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    with _LOCK:
        return bool(_STATE.get("enabled"))


def reset_run(backend: Optional[str] = None, mode: Optional[str] = None) -> None:
    enabled = _is_enabled_env()
    with _LOCK:
        _STATE["enabled"] = enabled
        _STATE["backend"] = backend
        _STATE["mode"] = mode
        _STATE["phase_counts"] = {}
        _STATE["phase_batch_totals"] = {}
        _STATE["phase_batch_samples"] = {}
        _STATE["phase_elapsed_s"] = {}
        _STATE["phase_start_times"] = {}
        _STATE["query_families"] = {}
        _STATE["oom_retries"] = 0
        _STATE["deadlock_retries"] = 0
    set_phase("unscoped")


def set_phase(phase: str) -> None:
    """Set the current phase for this thread.  Also starts a wall-clock timer for
    the phase if it hasn't been seen before, so the first thread to enter a named
    phase owns its start time.
    """
    _PHASE.current = phase
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        starts = _STATE["phase_start_times"]
        if phase not in starts:
            starts[phase] = time.monotonic()


def get_phase() -> str:
    current = getattr(_PHASE, "current", None)
    return current or "unscoped"


@contextmanager
def phase_scope(phase: str):
    previous = get_phase()
    set_phase(phase)
    try:
        yield
    finally:
        _close_phase(phase)
        set_phase(previous)


def _close_phase(phase: str) -> None:
    """Record elapsed time for a phase when it finishes (idempotent)."""
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        starts = _STATE["phase_start_times"]
        if phase not in starts:
            return
        elapsed = time.monotonic() - starts.pop(phase)
        elapsed_map = _STATE["phase_elapsed_s"]
        elapsed_map[phase] = round(elapsed_map.get(phase, 0.0) + elapsed, 3)


def record_phase_elapsed(phase: str, elapsed_s: float) -> None:
    """Directly record elapsed time for a phase (use when timing is computed externally)."""
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        elapsed_map = _STATE["phase_elapsed_s"]
        elapsed_map[phase] = round(elapsed_map.get(phase, 0.0) + elapsed_s, 3)
        # Remove any pending start so phase_scope teardown doesn't double-count.
        _STATE["phase_start_times"].pop(phase, None)


def record_oom_retry() -> None:
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        _STATE["oom_retries"] = int(_STATE.get("oom_retries", 0)) + 1


def record_deadlock_retry() -> None:
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        _STATE["deadlock_retries"] = int(_STATE.get("deadlock_retries", 0)) + 1


def _query_family(query: Any) -> str:
    if not isinstance(query, str):
        return "unknown"
    line = " ".join(query.strip().split())
    if not line:
        return "unknown"
    upper = line.upper()
    if upper.startswith("UNWIND"):
        return "UNWIND"
    if upper.startswith("MATCH"):
        return "MATCH"
    if upper.startswith("MERGE"):
        return "MERGE"
    if upper.startswith("CREATE"):
        return "CREATE"
    if upper.startswith("RETURN"):
        return "RETURN"
    return upper.split(" ", 1)[0][:32]


def record_batch_size(size: int) -> None:
    if size <= 0:
        return
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        phase = get_phase()
        totals = _STATE["phase_batch_totals"]
        samples = _STATE["phase_batch_samples"]
        totals[phase] = int(totals.get(phase, 0)) + int(size)
        samples[phase] = int(samples.get(phase, 0)) + 1


def _maybe_record_batch_from_parameters(parameters: Dict[str, Any]) -> None:
    for key in ("batch", "rows"):
        value = parameters.get(key)
        if isinstance(value, list):
            record_batch_size(len(value))
            return


def record_session_run(query: Any, parameters: Optional[Dict[str, Any]] = None) -> None:
    with _LOCK:
        if not _STATE.get("enabled"):
            return
        phase = get_phase()
        phase_counts = _STATE["phase_counts"]
        phase_counts[phase] = int(phase_counts.get(phase, 0)) + 1

        family = _query_family(query)
        qf = _STATE["query_families"]
        qf[family] = int(qf.get(family, 0)) + 1

    if parameters:
        _maybe_record_batch_from_parameters(parameters)


def snapshot(top_n_families: int = 8) -> Dict[str, Any]:
    with _LOCK:
        phase_counts = dict(_STATE["phase_counts"])
        totals = dict(_STATE["phase_batch_totals"])
        samples = dict(_STATE["phase_batch_samples"])
        elapsed_map = dict(_STATE["phase_elapsed_s"])
        # Flush any still-open phases (e.g. long-running phases at snapshot time).
        starts = dict(_STATE["phase_start_times"])
        now = time.monotonic()
        for phase, start in starts.items():
            elapsed_map[phase] = round(elapsed_map.get(phase, 0.0) + (now - start), 3)
        qf = dict(_STATE["query_families"])
        enabled = bool(_STATE.get("enabled"))
        backend = _STATE.get("backend")
        mode = _STATE.get("mode")
        oom_retries = int(_STATE.get("oom_retries", 0))
        deadlock_retries = int(_STATE.get("deadlock_retries", 0))

    phases = sorted(set(phase_counts) | set(totals) | set(samples) | set(elapsed_map))
    by_phase: Dict[str, Dict[str, Any]] = {}
    for phase in phases:
        total = int(totals.get(phase, 0))
        sample_count = int(samples.get(phase, 0))
        entry: Dict[str, Any] = {
            "session_run_count": int(phase_counts.get(phase, 0)),
            "batch_sample_count": sample_count,
            "avg_batch_size": round(total / sample_count, 2) if sample_count else 0.0,
        }
        if phase in elapsed_map:
            entry["elapsed_s"] = elapsed_map[phase]
        by_phase[phase] = entry

    top_families = sorted(qf.items(), key=lambda kv: kv[1], reverse=True)[:top_n_families]
    result: Dict[str, Any] = {
        "enabled": enabled,
        "backend": backend,
        "mode": mode,
        "totals": {
            "session_run_count": int(sum(phase_counts.values())),
            "batch_sample_count": int(sum(samples.values())),
            "avg_batch_size": round(
                (sum(totals.values()) / sum(samples.values())) if sum(samples.values()) else 0.0,
                2,
            ),
        },
        "by_phase": by_phase,
        "top_query_families": [{"family": family, "count": int(count)} for family, count in top_families],
    }
    if oom_retries or deadlock_retries:
        result["retry_events"] = {
            "oom_batch_reductions": oom_retries,
            "deadlock_retries": deadlock_retries,
        }
    return result


def dump_snapshot(path: Path, top_n_families: int = 8) -> None:
    data = snapshot(top_n_families=top_n_families)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
