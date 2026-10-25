"""Go HTTP-server-route extraction (MULTI_REPO_LINKS).

Handles net/http, gin, and echo — the three route-registration shapes we see
most often. All emit :class:`HttpServerRecord` records with the same shape
as the Java and Python extractors, so PR #8's discovery step can merge on
the same ``(protocol, method, path)`` identity.

Patterns handled:

* ``http.HandleFunc("/path", handler)`` — verb ``*`` (net/http muxes on path only)
* ``mux.HandleFunc("/path", handler)`` — same shape via a custom mux var
* ``r.GET("/path", handler)`` / ``r.POST(...)`` — gin, echo, chi (identical form)
* ``e.GET("/path", handler)`` — echo (same as gin)
* ``router.HandleFunc("/path", h).Methods("GET")`` — gorilla mux
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.http_extractor import HttpServerRecord


@dataclass
class GoExtractionResult:
    servers: List[HttpServerRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.servers


_GO_TRIGGERS = (
    "net/http",
    "github.com/gin-gonic/gin",
    "github.com/labstack/echo",
    "github.com/go-chi/chi",
    "github.com/gorilla/mux",
    ".HandleFunc(",
)


def looks_like_go_http_source(source: str) -> bool:
    return any(t in source for t in _GO_TRIGGERS)


# `r.GET("/path", handler)` — gin/echo/chi verb methods.
_GIN_VERB_RE = re.compile(
    r"(?<![\w.])([A-Za-z_]\w*)\s*\.\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*"
    r"\(\s*\"([^\"]+)\"\s*,\s*([\w.]+)"
)
# `http.HandleFunc("/path", handler)` / `mux.HandleFunc(...)` (verb *)
_NET_HTTP_RE = re.compile(
    r"(?<![\w.])([A-Za-z_]\w*)\s*\.\s*HandleFunc\s*"
    r"\(\s*\"([^\"]+)\"\s*,\s*([\w.]+)"
)
# `router.HandleFunc("/path", h).Methods("GET")`
_GORILLA_METHODS_RE = re.compile(
    r"\.HandleFunc\s*\(\s*\"([^\"]+)\"\s*,\s*([\w.]+)\s*\)\s*"
    r"\.\s*Methods\s*\(\s*\"([A-Z]+)\""
)

_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_]\w*)", re.MULTILINE)


def _package(source: str) -> Optional[str]:
    m = _PACKAGE_RE.search(source)
    return m.group(1) if m else None


def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _classify(path: str, store: Optional[ConfigValueStore], profile: str):
    if "${" in path:
        if store is None:
            return path, path, "SYMBOLIC", "unresolved:no-store"
        r = store.resolve_placeholders(path, profile)
        if r.fully_resolved():
            if r.used:
                k, s = r.used[0]
                return path, r.output, "INFERRED", f"config:{k}({s})"
            return path, r.output, "INFERRED", "config:defaults"
        return path, r.output, "SYMBOLIC", f"unresolved:{r.unresolved[0] if r.unresolved else '?'}"
    return path, path, "EXTRACTED", "literal"


def extract_from_source(
    source: str,
    path: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
) -> GoExtractionResult:
    result = GoExtractionResult()
    if not looks_like_go_http_source(source):
        return result

    pkg = _package(source) or ""
    path_str = str(path)

    def _emit(off: int, verb: str, raw_path: str, handler: str, framework: str, prov: str) -> None:
        # Handler in Go is typically `handleFoo` or `pkg.Handler` or a struct method.
        # Represent the FQN as `package.handler` when possible.
        fqn = f"{pkg}.{handler.rsplit('.', 1)[-1]}" if pkg else handler
        _, resolved, tier, tier_prov = _classify(raw_path, store, active_profile)
        result.servers.append(HttpServerRecord(
            fqn=fqn,
            method=verb,
            path=resolved,
            path_raw=raw_path,
            confidence=tier,
            provenance=f"{tier_prov}|{prov}",
            source_file=path_str,
            line=_line(source, off),
            framework=framework,
        ))

    # gin / echo / chi
    for m in _GIN_VERB_RE.finditer(source):
        recv = m.group(1)
        verb = m.group(2)
        # net/http.ServeMux doesn't have `.GET(...)` — filter obvious false positives.
        if recv in {"http"}:
            continue
        _emit(m.start(), verb, m.group(3), m.group(4),
              framework="gin_or_echo_or_chi", prov=f"recv:{recv}")

    # gorilla mux (also handled by net/http fallback below if Methods() isn't called)
    for m in _GORILLA_METHODS_RE.finditer(source):
        _emit(m.start(), m.group(3), m.group(1), m.group(2),
              framework="gorilla_mux", prov="Methods()")

    # net/http (verb unknown → *)
    already_seen_paths = {(s.path_raw, s.method) for s in result.servers}
    for m in _NET_HTTP_RE.finditer(source):
        recv = m.group(1)
        p = m.group(2)
        # Skip if a gorilla-mux Methods() call already covered this exact path.
        # We keep the star entry if no method-specific one exists.
        gorilla_covered = any(pr == p for (pr, _mm) in already_seen_paths)
        if gorilla_covered:
            continue
        _emit(m.start(), "*", p, m.group(3),
              framework="net_http", prov=f"recv:{recv}")

    return result


__all__ = [
    "GoExtractionResult",
    "extract_from_source",
    "looks_like_go_http_source",
]
