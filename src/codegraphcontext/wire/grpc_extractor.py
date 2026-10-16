"""gRPC server + client extraction from Java source (MULTI_REPO_LINKS).

Emits :class:`GrpcServerRecord` for classes extending
``<Service>Grpc.<Service>ImplBase`` and :class:`GrpcClientRecord` for calls
against ``<Service>Grpc.newBlockingStub(...)`` / ``newStub(...)`` /
``newFutureStub(...)`` chains.

Endpoint identity mirrors :data:`schema_contract.ENDPOINT_MERGE_KEYS`
``(protocol="grpc", method=<RpcName>, path="<Service>/<RpcName>")`` where
``Service`` is inferred from the ImplBase suffix or the ``Grpc.newXxxStub``
prefix.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore


@dataclass(frozen=True)
class GrpcServerRecord:
    fqn: str
    service: str            # "OrdersService"
    rpc: str                # "CreateOrder"
    path: str               # "OrdersService/CreateOrder"
    confidence: str         # EXTRACTED (always — we read Java-level identifiers)
    provenance: str
    source_file: str
    line: int


@dataclass(frozen=True)
class GrpcClientRecord:
    fqn: str
    service: str
    rpc: str
    path: str
    confidence: str
    provenance: str
    source_file: str
    line: int
    stub_kind: str          # "blockingStub" | "stub" | "futureStub"


@dataclass
class GrpcExtractionResult:
    servers: List[GrpcServerRecord] = field(default_factory=list)
    clients: List[GrpcClientRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.servers and not self.clients


_GRPC_TRIGGERS = ("ImplBase", "newBlockingStub", "newStub", "newFutureStub", "io.grpc")

# io.grpc.stub.AbstractStub decorator + accessor methods that MUST NOT be treated
# as RPCs (they return a re-decorated stub or a channel/options accessor).
_STUB_NON_RPC_METHODS = frozenset({
    "withDeadline", "withDeadlineAfter", "withInterceptors", "withCallCredentials",
    "withCompression", "withMaxInboundMessageSize", "withMaxOutboundMessageSize",
    "withOption", "withWaitForReady", "withChannel", "withExecutor",
    "withOnReadyThreshold",
    "getCallOptions", "getChannel",
})


def looks_like_grpc_source(source: str) -> bool:
    return any(t in source for t in _GRPC_TRIGGERS)


_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

# `class Impl extends OrdersServiceGrpc.OrdersServiceImplBase`
_IMPLBASE_RE = re.compile(
    r"class\s+([A-Za-z_]\w*)"
    r"(?:\s*<[^>]*>)?"
    r"\s+extends\s+"
    r"(?:[\w.]+\.)?([A-Za-z_]\w*)Grpc\s*\.\s*\1ImplBase|"
    r"class\s+([A-Za-z_]\w*)"
    r"(?:\s*<[^>]*>)?"
    r"\s+extends\s+"
    r"(?:[\w.]+\.)?([A-Za-z_]\w*)Grpc\s*\.\s*([A-Za-z_]\w*)ImplBase",
)


@dataclass
class _ClassSpan:
    name: str
    service: Optional[str]
    start_offset: int
    end_offset: int


def _find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0; i = open_pos; n = len(text)
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


def _extract_implbase_spans(source: str) -> List[_ClassSpan]:
    """Return spans of all classes that ``extends ...Grpc.<Svc>ImplBase``."""
    spans: List[_ClassSpan] = []
    header_re = re.compile(
        r"\b(?:public\s+|private\s+|protected\s+|abstract\s+|static\s+|final\s+)*"
        r"class\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]*>)?"
        r"\s+extends\s+"
        r"(?:[\w.]+\.)?"
        r"([A-Za-z_]\w*)Grpc\s*\.\s*([A-Za-z_]\w*)ImplBase"
        r"[^{]*\{",
        re.MULTILINE,
    )
    for m in header_re.finditer(source):
        cls_name = m.group(1)
        svc_name = m.group(2)
        # Group(3) is the inner class before ImplBase — typically equals svc_name
        # or the RPC bundle. Prefer the outer Grpc-class prefix (svc_name).
        open_brace = source.rfind("{", m.start(), m.end())
        if open_brace == -1: continue
        close = _find_matching_brace(source, open_brace)
        if close == -1: continue
        spans.append(_ClassSpan(name=cls_name, service=svc_name,
                                start_offset=open_brace, end_offset=close))
    return spans


def _extract_all_class_spans(source: str) -> List[_ClassSpan]:
    """All class/interface bodies — for FQN resolution on client calls."""
    spans: List[_ClassSpan] = []
    header_re = re.compile(
        r"\b(?:class|interface|enum|@interface)\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]*>)?"
        r"(?:\s+extends\s+[\w.<>,\s]+?)?"
        r"(?:\s+implements\s+[\w.<>,\s]+?)?"
        r"\s*\{",
        re.MULTILINE,
    )
    for m in header_re.finditer(source):
        name = m.group(1)
        open_brace = source.rfind("{", m.start(), m.end())
        if open_brace == -1: continue
        close = _find_matching_brace(source, open_brace)
        if close == -1: continue
        spans.append(_ClassSpan(name=name, service=None,
                                start_offset=open_brace, end_offset=close))
    return spans


def _enclosing(spans, offset: int) -> Optional[_ClassSpan]:
    cands = [s for s in spans if s.start_offset < offset < s.end_offset]
    if not cands: return None
    # Deepest wins.
    return min(cands, key=lambda s: s.end_offset - s.start_offset)


def _offset_to_line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _extract_package(source: str) -> Optional[str]:
    m = _PACKAGE_RE.search(source)
    return m.group(1) if m else None


# Server RPC methods: public void <rpc>(Request req, StreamObserver<Response> resp)
# Deliberately doesn't try to also match/skip any leading `@Annotation` lines:
# a `(?:@...)*` prefix here previously nested a quantified `[\w.]+` inside
# another quantifier with no unambiguous boundary between repetitions, which
# is a classic catastrophic-backtracking (ReDoS) shape (CodeQL flagged it on
# input like " @." repeated many times). Annotations aren't captured and
# finditer() below already matches this pattern at any offset in the body
# regardless of what precedes it, so skipping them explicitly added no
# functionality — only the reported line number could shift by the couple of
# lines an @Override/etc. annotation occupies, which is immaterial here.
_RPC_METHOD_RE = re.compile(
    r"public\s+(?:void|[\w.]+)\s+"
    r"([A-Za-z_]\w*)"
    r"\s*\([^)]*StreamObserver[^)]*\)",
)


# Client: `<recv>.newBlockingStub|newStub|newFutureStub(...)` at some earlier
# statement establishes the stub, and then the stub is called as `stub.rpc(...)`.
# We infer service from either:
#   * a variable declared as `SomeServiceGrpc.newBlockingStub(...)` — extract SomeService
#   * an inline expression like `OrdersServiceGrpc.newBlockingStub(chan).createOrder(...)`
_INLINE_STUB_CALL_RE = re.compile(
    r"(?:([A-Za-z_]\w*)Grpc)\s*\.\s*(newBlockingStub|newStub|newFutureStub)\s*\("
)
_STUB_VAR_DECL_RE = re.compile(
    r"([A-Za-z_]\w*)Grpc\s*\.\s*(?:newBlockingStub|newStub|newFutureStub)\s*\([^)]*\)"
    r"\s*[.\w]*\s*"
)


def extract_from_source(
    source: str,
    path: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
) -> GrpcExtractionResult:
    result = GrpcExtractionResult()
    if not looks_like_grpc_source(source):
        return result
    pkg = _extract_package(source)
    impl_spans = _extract_implbase_spans(source)
    all_spans = _extract_all_class_spans(source)
    if not impl_spans and not all_spans:
        return result

    def _fqn(span: _ClassSpan, method: str) -> str:
        prefix = f"{pkg}." if pkg else ""
        return f"{prefix}{span.name}.{method}"

    path_str = str(path)

    # ── Server RPCs ──────────────────────────────────────────────────────
    for span in impl_spans:
        body = source[span.start_offset:span.end_offset]
        for rm in _RPC_METHOD_RE.finditer(body):
            rpc = rm.group(1)
            # Skip Object-inherited names.
            if rpc in {"toString", "hashCode", "equals"}: continue
            svc = span.service or span.name
            result.servers.append(GrpcServerRecord(
                fqn=_fqn(span, rpc),
                service=svc,
                rpc=rpc,
                path=f"{svc}/{rpc}",
                confidence="EXTRACTED",
                provenance="ImplBase",
                source_file=path_str,
                line=_offset_to_line(source, span.start_offset + rm.start()),
            ))

    # ── Client calls ─────────────────────────────────────────────────────
    # (1) Inline: `OrdersServiceGrpc.newBlockingStub(chan).createOrder(req)`
    for m in _INLINE_STUB_CALL_RE.finditer(source):
        svc = m.group(1)
        stub_kind = m.group(2).replace("new", "").replace("Stub", "").lower() + "Stub"
        span = _enclosing(all_spans, m.start())
        if span is None: continue
        # Find enclosing method by walking backwards for the last `... name(...) {`
        method_name = _find_enclosing_method(source, span, m.start())
        if method_name is None: continue
        # Look for `.<rpc>(` immediately after the closing `)` of the stub call.
        stub_open = m.end() - 1
        stub_close = _find_paren_end(source, stub_open)
        if stub_close == -1: continue
        after = source[stub_close + 1:]
        rpc_m = re.match(r"\s*\.\s*([A-Za-z_]\w*)\s*\(", after)
        if rpc_m is None: continue
        rpc = rpc_m.group(1)
        if rpc in _STUB_NON_RPC_METHODS:
            continue
        result.clients.append(GrpcClientRecord(
            fqn=_fqn(span, method_name),
            service=svc,
            rpc=rpc,
            path=f"{svc}/{rpc}",
            confidence="EXTRACTED",
            provenance=f"inline-{stub_kind}",
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
            stub_kind=stub_kind,
        ))

    # (2) Variable form: `var stub = OrdersServiceGrpc.newBlockingStub(chan); ...
    # stub.createOrder(req);` — map each stub variable name → service.
    stub_vars = _find_stub_variable_bindings(source)
    if stub_vars:
        for varname, (svc, stub_kind) in stub_vars.items():
            call_re = re.compile(rf"(?<![\w.])" + re.escape(varname) + r"\s*\.\s*([A-Za-z_]\w*)\s*\(")
            for cm in call_re.finditer(source):
                span = _enclosing(all_spans, cm.start())
                if span is None: continue
                method_name = _find_enclosing_method(source, span, cm.start())
                if method_name is None: continue
                rpc = cm.group(1)
                if rpc in _STUB_NON_RPC_METHODS:
                    continue
                result.clients.append(GrpcClientRecord(
                    fqn=_fqn(span, method_name),
                    service=svc,
                    rpc=rpc,
                    path=f"{svc}/{rpc}",
                    confidence="EXTRACTED",
                    provenance=f"varstub:{varname}",
                    source_file=path_str,
                    line=_offset_to_line(source, cm.start()),
                    stub_kind=stub_kind,
                ))

    return result


def _find_stub_variable_bindings(source: str) -> dict:
    """Return ``{var_name: (service, stub_kind)}`` for stubs assigned to a name."""
    # `SomeServiceGrpc.SomeServiceBlockingStub stub = SomeServiceGrpc.newBlockingStub(chan);`
    # `var stub = SomeServiceGrpc.newBlockingStub(chan);`
    bindings: dict = {}
    typed_re = re.compile(
        r"([A-Za-z_]\w*)Grpc\s*\.\s*[A-Za-z_]\w*Stub\s+([A-Za-z_]\w*)\s*=\s*"
        r"([A-Za-z_]\w*)Grpc\s*\.\s*(newBlockingStub|newStub|newFutureStub)\s*\("
    )
    var_re = re.compile(
        r"(?:var|final\s+var)\s+([A-Za-z_]\w*)\s*=\s*"
        r"([A-Za-z_]\w*)Grpc\s*\.\s*(newBlockingStub|newStub|newFutureStub)\s*\("
    )
    for m in typed_re.finditer(source):
        varname = m.group(2)
        svc = m.group(3)
        stub_kind = m.group(4).replace("new", "").replace("Stub", "").lower() + "Stub"
        bindings[varname] = (svc, stub_kind)
    for m in var_re.finditer(source):
        varname = m.group(1)
        svc = m.group(2)
        stub_kind = m.group(3).replace("new", "").replace("Stub", "").lower() + "Stub"
        bindings.setdefault(varname, (svc, stub_kind))
    return bindings


def _find_paren_end(source: str, open_paren_offset: int) -> int:
    depth = 0; i = open_paren_offset; n = len(source)
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\": i += 2; continue
                if source[i] == '"': i += 1; break
                i += 1
            continue
        if c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: return i
        i += 1
    return -1


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


__all__ = [
    "GrpcClientRecord",
    "GrpcExtractionResult",
    "GrpcServerRecord",
    "extract_from_source",
    "looks_like_grpc_source",
]
