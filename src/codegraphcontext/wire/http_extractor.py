"""HTTP server + client extraction from Java source (MULTI_REPO_LINKS).

Emits :class:`HttpServerRecord` for Spring MVC handlers (``@RestController`` /
``@Controller`` + ``@GetMapping`` / ``@PostMapping`` / …) and
:class:`HttpClientRecord` for outbound HTTP calls via ``RestTemplate`` and
``WebClient``.

Endpoint identity mirrors :data:`schema_contract.ENDPOINT_MERGE_KEYS`
``(protocol, method, path)`` — path templating (``{id}``, ``/*``) is kept as
written so the same wire address matches on both ends.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from codegraphcontext.wire.config_values import (
    BASE_PROFILE,
    ConfigValueStore,
    PlaceholderResolution,
)


HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")


@dataclass(frozen=True)
class HttpServerRecord:
    fqn: str
    method: str            # GET / POST / PUT / DELETE / PATCH / HEAD / OPTIONS / *
    path: str              # resolved path (may still contain {var})
    path_raw: str          # exact source form (may contain ${...})
    confidence: str
    provenance: str
    source_file: str
    line: int
    framework: str = "spring"


@dataclass(frozen=True)
class HttpClientRecord:
    fqn: str
    method: str
    path: str
    path_raw: str
    confidence: str
    provenance: str
    source_file: str
    line: int
    framework: str         # "restTemplate" | "webClient"


@dataclass
class HttpExtractionResult:
    servers: List[HttpServerRecord] = field(default_factory=list)
    clients: List[HttpClientRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.servers and not self.clients


# ── Trigger ────────────────────────────────────────────────────────────────

_HTTP_TRIGGERS = (
    "@RestController", "@Controller",
    "@GetMapping", "@PostMapping", "@PutMapping",
    "@DeleteMapping", "@PatchMapping", "@RequestMapping",
    "RestTemplate", "WebClient",
    "org.springframework.web",
)


def looks_like_http_source(source: str) -> bool:
    return any(t in source for t in _HTTP_TRIGGERS)


# ── Regexes ────────────────────────────────────────────────────────────────

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

_MAPPING_RE = re.compile(
    r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(\()?",
)
_CLASS_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\(",
)
_CONTROLLER_STEREOTYPE_RE = re.compile(r"@(RestController|Controller)\b")

_STRING_CONST_RE = re.compile(
    r"(?:^|[\s;{])(?:public|private|protected|static|final|\s)*\s*String\s+([A-Za-z_]\w*)\s*=\s*\"([^\"]*)\"\s*;",
)

_METHOD_NAME_AFTER_RE = re.compile(
    r"""
    \s*
    (?:@[\w.]+\s*(?:\([^)]*\))?\s*)*
    (?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)*
    (?:<[^>]+>\s*)?
    [\w.<>?,\s\[\]]+?\s+
    ([A-Za-z_]\w*)
    \s*\(
    """,
    re.VERBOSE,
)

# RestTemplate method → HTTP verb (only the deterministic ones).
_REST_TEMPLATE_VERB = {
    "getForObject": "GET", "getForEntity": "GET",
    "postForObject": "POST", "postForEntity": "POST", "postForLocation": "POST",
    "put": "PUT", "delete": "DELETE",
    "headForHeaders": "HEAD",
    "optionsForAllow": "OPTIONS",
}

# WebClient chain start: .get() .post() .put() .delete() .patch() .head() .options()
_WEB_CLIENT_VERB_CALL_RE = re.compile(
    r"(?<![\w.])(\w+)\s*\.\s*(get|post|put|delete|patch|head|options)\s*\(\s*\)"
)

_REST_TEMPLATE_CALL_RE = re.compile(
    r"(?<![\w.])(\w+)\s*\.\s*(getForObject|getForEntity|postForObject|postForEntity|"
    r"postForLocation|put|delete|headForHeaders|optionsForAllow|exchange)\s*\(",
)


@dataclass
class _ClassSpan:
    name: str
    start_offset: int
    end_offset: int
    depth: int


def _find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            nl = text.find("\n", i); i = n if nl == -1 else nl; continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2); i = n if end == -1 else end + 2; continue
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\": i += 2; continue
                if text[i] == '"': i += 1; break
                i += 1
            continue
        if c == "'":
            i += 1
            while i < n:
                if text[i] == "\\": i += 2; continue
                if text[i] == "'": i += 1; break
                i += 1
            continue
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return i
        i += 1
    return -1


def _find_paren_end(source: str, open_paren_offset: int) -> int:
    depth = 0
    i = open_paren_offset
    n = len(source)
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\": i += 2; continue
                if source[i] == '"': i += 1; break
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: return i
        i += 1
    return -1


def _extract_class_spans(source: str) -> List[_ClassSpan]:
    spans: List[_ClassSpan] = []
    header_re = re.compile(
        r"\b(?:class|interface|enum|@interface)\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]*>)?"
        r"(?:\s+extends\s+[\w.<>,\s]+?)?"
        r"(?:\s+implements\s+[\w.<>,\s]+?)?"
        r"(?:\s+permits\s+[\w.<>,\s]+?)?"
        r"\s*\{",
        re.MULTILINE,
    )
    for m in header_re.finditer(source):
        name = m.group(1)
        open_brace = source.rfind("{", m.start(), m.end())
        if open_brace == -1: continue
        close_brace = _find_matching_brace(source, open_brace)
        if close_brace == -1: continue
        spans.append(_ClassSpan(name=name, start_offset=open_brace,
                                end_offset=close_brace, depth=0))
    for s in spans:
        s.depth = sum(1 for o in spans if o is not s
                       and o.start_offset < s.start_offset < o.end_offset)
    return spans


def _enclosing_class(spans, offset: int) -> Optional[_ClassSpan]:
    cands = [s for s in spans if s.start_offset < offset < s.end_offset]
    return max(cands, key=lambda s: s.depth) if cands else None


def _offset_to_line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _extract_package(source: str) -> Optional[str]:
    m = _PACKAGE_RE.search(source)
    return m.group(1) if m else None


def _string_consts(source: str, span: _ClassSpan) -> dict:
    body = source[span.start_offset:span.end_offset]
    return {m.group(1): m.group(2) for m in _STRING_CONST_RE.finditer(body)}


def _find_enclosing_method(source: str, span: _ClassSpan, offset: int) -> Optional[str]:
    method_re = re.compile(
        r"""
        (?:@[\w.]+\s*(?:\([^)]*\))?\s*)*
        (?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)*
        (?:<[^>]+>\s*)?
        [\w.<>?,\s\[\]]+?\s+
        ([A-Za-z_]\w*)
        \s*\([^)]*\)
        (?:\s*throws\s+[\w.,\s]+?)?
        \s*\{
        """,
        re.VERBOSE,
    )
    best = None
    for m in method_re.finditer(source, span.start_offset, span.end_offset):
        brace = source.rfind("{", m.start(), m.end())
        if brace == -1 or brace >= offset: continue
        close = _find_matching_brace(source, brace)
        if close == -1 or close < offset: continue
        best = m.group(1)
    return best


_STRING_LITERAL_RE = re.compile(r'^"([^"\\]*(?:\\.[^"\\]*)*)"$')


def _classify_literal(raw: str, store: Optional[ConfigValueStore], profile: str
                      ) -> Tuple[str, str, str, str]:
    """Return (raw, resolved, confidence, provenance) for a literal path/URL."""
    if "${" not in raw:
        return raw, raw, "EXTRACTED", "literal"
    if store is None:
        return raw, raw, "SYMBOLIC", "unresolved:no-store"
    r: PlaceholderResolution = store.resolve_placeholders(raw, profile)
    if r.fully_resolved():
        if r.used:
            k, s = r.used[0]
            return raw, r.output, "INFERRED", f"config:{k}({s})"
        return raw, r.output, "INFERRED", "config:defaults"
    first = r.unresolved[0] if r.unresolved else "?"
    return raw, r.output, "SYMBOLIC", f"unresolved:{first}"


def _classify_expr(text: str, store, profile, consts) -> Tuple[Optional[str], Optional[str], str, str]:
    """Classify a first-arg expression that names a URL/path."""
    text = text.strip()
    m = _STRING_LITERAL_RE.match(text)
    if m:
        return _classify_literal(m.group(1), store, profile)
    if re.fullmatch(r"[A-Za-z_]\w*", text):
        c = consts.get(text)
        if c is not None:
            raw, resolved, tier, prov = _classify_literal(c, store, profile)
            return raw, resolved, tier, f"identifier:{text}→{prov}"
        return text, text, "AMBIGUOUS", f"identifier:{text}"
    return text, text, "AMBIGUOUS", "expression"


def _read_first_call_arg(source: str, open_paren_offset: int) -> Optional[str]:
    i = open_paren_offset + 1
    n = len(source)
    depth_paren = depth_angle = 0
    start = i
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\": i += 2; continue
                if source[i] == '"': i += 1; break
                i += 1
            continue
        if c == "(": depth_paren += 1
        elif c == ")":
            if depth_paren == 0: return source[start:i].strip() or None
            depth_paren -= 1
        elif c == "<": depth_angle += 1
        elif c == ">":
            if depth_angle > 0: depth_angle -= 1
        elif c == "," and depth_paren == 0 and depth_angle == 0:
            return source[start:i].strip() or None
        i += 1
    return None


def _annotation_path(args_body: str) -> Optional[str]:
    """Given the parens body of a mapping annotation, extract the path attr.

    Supports ``"literal"`` shorthand, ``path = "..."``, ``value = "..."``,
    and ``{"..."}`` arrays (returns the first entry).
    """
    body = args_body.strip()
    if body.startswith('"'):
        m = re.match(r'"((?:[^"\\]|\\.)*)"', body)
        return m.group(1) if m else None
    for attr in ("path", "value"):
        m = re.search(rf'{attr}\s*=\s*"((?:[^"\\]|\\.)*)"', body)
        if m: return m.group(1)
        m = re.search(rf'{attr}\s*=\s*\{{\s*"((?:[^"\\]|\\.)*)"', body)
        if m: return m.group(1)
    # Fallback: first string literal.
    m = re.search(r'"((?:[^"\\]|\\.)*)"', body)
    return m.group(1) if m else None


def _annotation_method(args_body: str) -> Optional[str]:
    """Extract ``method = RequestMethod.POST`` (or a bare token like POST)."""
    m = re.search(r"method\s*=\s*(?:RequestMethod\.)?([A-Z]+)", args_body)
    if m and m.group(1) in HTTP_METHODS:
        return m.group(1)
    return None


_MAPPING_ANNOTATION_TO_METHOD = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}


def _join_path(prefix: str, rest: str) -> str:
    if not prefix: return rest
    if not rest: return prefix
    if prefix.endswith("/") and rest.startswith("/"): return prefix[:-1] + rest
    if not prefix.endswith("/") and not rest.startswith("/"): return prefix + "/" + rest
    return prefix + rest


def _class_prefix(source: str, span: _ClassSpan) -> str:
    """Return the class-level @RequestMapping prefix, else ''."""
    header_end = span.start_offset
    header_start = max(0, header_end - 400)
    header = source[header_start:header_end]
    m = re.search(r"@RequestMapping\s*\(", header)
    if not m: return ""
    open_paren = header_start + m.end() - 1
    close = _find_paren_end(source, open_paren)
    if close == -1: return ""
    body = source[open_paren + 1:close]
    p = _annotation_path(body)
    return p or ""


def _class_has_controller_annotation(source: str, span: _ClassSpan) -> bool:
    header = source[max(0, span.start_offset - 400):span.start_offset]
    return bool(_CONTROLLER_STEREOTYPE_RE.search(header))


# ── Public entry ───────────────────────────────────────────────────────────

def extract_from_source(
    source: str,
    path: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
) -> HttpExtractionResult:
    result = HttpExtractionResult()
    if not looks_like_http_source(source):
        return result
    pkg = _extract_package(source)
    spans = _extract_class_spans(source)
    if not spans:
        return result

    def _fqn(span: _ClassSpan, method: str) -> str:
        prefix = f"{pkg}." if pkg else ""
        return f"{prefix}{span.name}.{method}"

    consts_cache = {}
    path_str = str(path)

    # ── Server: @Get/PostMapping etc. ────────────────────────────────────
    for m in _MAPPING_RE.finditer(source):
        ann_name = m.group(1)
        span = _enclosing_class(spans, m.start())
        if span is None: continue
        if not _class_has_controller_annotation(source, span):
            continue
        has_paren = m.group(2) == "("
        if has_paren:
            open_paren = m.end() - 1
            close_paren = _find_paren_end(source, open_paren)
            if close_paren == -1:
                result.warnings.append(f"{path}:{_offset_to_line(source, m.start())}: unbalanced @{ann_name}(")
                continue
            body = source[open_paren + 1:close_paren]
            method_path = _annotation_path(body) or ""
            method_verb = (
                _annotation_method(body)
                if ann_name == "RequestMapping"
                else _MAPPING_ANNOTATION_TO_METHOD[ann_name]
            )
            after = source[close_paren + 1:]
        else:
            # `@GetMapping` marker annotation (no parens) — verb from name, empty path.
            method_path = ""
            method_verb = _MAPPING_ANNOTATION_TO_METHOD.get(ann_name)
            after = source[m.end():]

        if method_verb is None:
            # @RequestMapping with no explicit method — Spring default is *any*.
            method_verb = "*"

        name_m = _METHOD_NAME_AFTER_RE.match(after)
        if name_m is None:
            continue
        method_name = name_m.group(1)

        prefix = _class_prefix(source, span)
        full_path_raw = _join_path(prefix, method_path)
        _, resolved, tier, prov = _classify_literal(full_path_raw, store, active_profile)

        result.servers.append(HttpServerRecord(
            fqn=_fqn(span, method_name),
            method=method_verb,
            path=resolved,
            path_raw=full_path_raw,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
        ))

    # ── Client: RestTemplate methods ─────────────────────────────────────
    for m in _REST_TEMPLATE_CALL_RE.finditer(source):
        span = _enclosing_class(spans, m.start())
        if span is None: continue
        method_name = _find_enclosing_method(source, span, m.start())
        if method_name is None: continue
        arg = _read_first_call_arg(source, m.end() - 1)
        if arg is None: continue

        method_call = m.group(2)
        verb = _REST_TEMPLATE_VERB.get(method_call)

        if method_call == "exchange":
            # `restTemplate.exchange(url, HttpMethod.POST, ...)` — take second arg.
            args_all = _read_rest_template_exchange_args(source, m.end() - 1)
            if args_all is None or len(args_all) < 2:
                verb = "*"
            else:
                second = args_all[1].strip()
                mv = re.match(r"HttpMethod\.([A-Z]+)", second)
                verb = mv.group(1) if mv and mv.group(1) in HTTP_METHODS else "*"

        consts = consts_cache.setdefault(id(span), _string_consts(source, span))
        raw, resolved, tier, prov = _classify_expr(arg, store, active_profile, consts)
        if raw is None: continue
        result.clients.append(HttpClientRecord(
            fqn=_fqn(span, method_name),
            method=verb or "*",
            path=resolved,
            path_raw=raw,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
            framework="restTemplate",
        ))

    # ── Client: WebClient chain ──────────────────────────────────────────
    for m in _WEB_CLIENT_VERB_CALL_RE.finditer(source):
        # Filter: receiver name should look like a WebClient variable, OR the
        # file must import WebClient. Second check is cheap enough.
        if "WebClient" not in source:
            continue
        span = _enclosing_class(spans, m.start())
        if span is None: continue
        method_name = _find_enclosing_method(source, span, m.start())
        if method_name is None: continue
        verb = m.group(2).upper()

        # Look for the next .uri("...") after m.end(), constrained to same method.
        uri_re = re.compile(r"\.\s*uri\s*\(")
        uri_m = uri_re.search(source, m.end(), min(len(source), m.end() + 500))
        if uri_m is None:
            continue
        open_paren = uri_m.end() - 1
        arg = _read_first_call_arg(source, open_paren)
        if arg is None: continue
        consts = consts_cache.setdefault(id(span), _string_consts(source, span))
        raw, resolved, tier, prov = _classify_expr(arg, store, active_profile, consts)
        if raw is None: continue
        result.clients.append(HttpClientRecord(
            fqn=_fqn(span, method_name),
            method=verb,
            path=resolved,
            path_raw=raw,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
            framework="webClient",
        ))

    return result


def _read_rest_template_exchange_args(source: str, open_paren_offset: int) -> Optional[List[str]]:
    """Split top-level comma-separated args from a call `(a, b, c, ...)`."""
    i = open_paren_offset + 1
    n = len(source)
    depth_paren = depth_angle = 0
    start = i
    args: List[str] = []
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\": i += 2; continue
                if source[i] == '"': i += 1; break
                i += 1
            continue
        if c == "(": depth_paren += 1
        elif c == ")":
            if depth_paren == 0:
                args.append(source[start:i])
                return args
            depth_paren -= 1
        elif c == "<": depth_angle += 1
        elif c == ">":
            if depth_angle > 0: depth_angle -= 1
        elif c == "," and depth_paren == 0 and depth_angle == 0:
            args.append(source[start:i])
            start = i + 1
        i += 1
    return None


__all__ = [
    "HTTP_METHODS",
    "HttpClientRecord",
    "HttpExtractionResult",
    "HttpServerRecord",
    "extract_from_source",
    "looks_like_http_source",
]
