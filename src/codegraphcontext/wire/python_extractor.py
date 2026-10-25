"""Python HTTP-server-route extraction (MULTI_REPO_LINKS).

Handles Flask (``@app.route("/path", methods=["POST"])``) and FastAPI /
Starlette (``@app.get("/path")``, ``@router.post("/path")``) decorator styles.

The extractor emits :class:`HttpServerRecord` records with the same shape
that the Java HTTP extractor uses, so downstream discovery (PR #8) can
merge Python and Java handlers on the same ``(protocol, method, path)``
endpoint identity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.http_extractor import HttpServerRecord


@dataclass
class PythonExtractionResult:
    servers: List[HttpServerRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.servers


_PY_TRIGGERS = (
    "from flask", "import flask",
    "from fastapi", "import fastapi",
    "from starlette", "import starlette",
    "APIRouter",
    "@app.route", "@app.get", "@app.post", "@app.put", "@app.delete", "@app.patch",
    "@router.get", "@router.post", "@router.put", "@router.delete", "@router.patch",
)


def looks_like_python_http_source(source: str) -> bool:
    return any(t in source for t in _PY_TRIGGERS)


_FLASK_ROUTE_RE = re.compile(
    r"@\s*([A-Za-z_][\w]*)\s*\.\s*route\s*\(\s*(['\"])(.*?)\2"
    r"(?:\s*,\s*methods\s*=\s*\[([^\]]*)\])?"
    r"[^)]*\)"
)

# @app.get("/x"), @router.post("/x", ...)
_FASTAPI_ROUTE_RE = re.compile(
    r"@\s*([A-Za-z_][\w]*)\s*\.\s*(get|post|put|delete|patch|head|options)\s*\("
    r"\s*(['\"])(.*?)\3",
)

# `def name(` after a decorator — python uses indentation, but for our purposes
# the next `def` at any indentation captures the method name.
_DEF_AFTER_RE = re.compile(r"(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")

# Class context for FQN — we approximate by tracking `class Name:` blocks.
_CLASS_RE = re.compile(r"^(?P<indent>[ \t]*)class\s+([A-Za-z_]\w*)\b", re.MULTILINE)


def _module_name(path: Path) -> str:
    return path.stem


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _preceding_class(source: str, offset: int) -> Optional[str]:
    """Return the innermost class:name whose body brackets the offset by indent depth.

    Uses column-based indentation heuristics — good enough for handler methods.
    """
    best: Optional[str] = None
    best_indent = -1
    for m in _CLASS_RE.finditer(source, 0, offset):
        indent = len(m.group("indent"))
        # A class captures the offset if the offset column depth is > class indent
        # AND no smaller-indent class opens between them.
        if indent < best_indent:
            continue
        best = m.group(2)
        best_indent = indent
    return best


def _parse_methods_list(spec: str) -> List[str]:
    """Parse `["GET", "POST"]` or `['get','put']` payload — normalize to upper."""
    return [t.upper() for t in re.findall(r"['\"]([A-Za-z]+)['\"]", spec)]


def _classify(path: str, store: Optional[ConfigValueStore], profile: str
              ) -> tuple:
    if "${" in path:
        # Spring-style placeholders are unusual in Python but allowed by policy.
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
) -> PythonExtractionResult:
    result = PythonExtractionResult()
    if not looks_like_python_http_source(source):
        return result

    module = _module_name(path)
    path_str = str(path)

    def _emit(off: int, method_verb: str, raw_path: str, framework: str, provenance_extra: str = "") -> None:
        after = source[off:]
        d = _DEF_AFTER_RE.search(after)
        if d is None:
            result.warnings.append(f"{path}:{_line_number(source, off)}: decorator with no def")
            return
        method_name = d.group(1)
        cls = _preceding_class(source, off)
        fqn = f"{module}.{cls}.{method_name}" if cls else f"{module}.{method_name}"
        _, resolved, tier, prov = _classify(raw_path, store, active_profile)
        if provenance_extra:
            prov = f"{prov}|{provenance_extra}"
        result.servers.append(HttpServerRecord(
            fqn=fqn,
            method=method_verb,
            path=resolved,
            path_raw=raw_path,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_line_number(source, off),
            framework=framework,
        ))

    # Flask style: @<app>.route("/path", methods=[...])
    for m in _FLASK_ROUTE_RE.finditer(source):
        raw = m.group(3)
        methods = _parse_methods_list(m.group(4) or "") or ["GET"]
        for verb in methods:
            _emit(m.end(), verb, raw, framework="flask", provenance_extra=f"decorator:{m.group(1)}.route")

    # FastAPI / Starlette: @<app>.<verb>("/path", ...)
    for m in _FASTAPI_ROUTE_RE.finditer(source):
        verb = m.group(2).upper()
        raw = m.group(4)
        _emit(m.end(), verb, raw, framework="fastapi",
              provenance_extra=f"decorator:{m.group(1)}.{m.group(2)}")

    return result


__all__ = [
    "PythonExtractionResult",
    "extract_from_source",
    "looks_like_python_http_source",
]
