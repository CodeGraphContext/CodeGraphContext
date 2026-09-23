"""Kafka producer/consumer extraction from Java source (MULTI_REPO_LINKS).

This module walks Java source text and reports every place where a Kafka
topic is written to or read from, together with the FQN of the enclosing
method. A downstream writer (added in a later PR, gated on
``MULTI_REPO_LINKS=true``) will turn these records into ``PRODUCES_TO`` /
``CONSUMES_FROM`` edges between ``Function`` and ``Topic`` nodes.

The extractor is deliberately regex- + brace-tracking-based rather than
tree-sitter-driven. The set of Kafka call shapes we care about is small
(``KafkaTemplate.send``, ``Producer.send``, ``new ProducerRecord``, and
``@KafkaListener``), and running it as a pure function over strings makes
the surface trivial to unit-test with inline fixtures and keeps this PR
self-contained — no pipeline / TS-manager wiring.

Confidence tiers (mirrors :mod:`schema_contract.WIRE_CONFIDENCE_TIERS`):

* ``EXTRACTED`` — raw string literal, no placeholder
* ``INFERRED``  — ``${...}`` placeholder that ``ConfigValueStore`` resolved
* ``SYMBOLIC``  — ``${...}`` placeholder that could not be resolved
* ``AMBIGUOUS`` — ``topicPattern`` regex or an identifier we could not trace
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from codegraphcontext.wire.config_values import (
    BASE_PROFILE,
    ConfigValueStore,
    PlaceholderResolution,
)

# ── Public dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class KafkaProducerRecord:
    fqn: str                # e.g. "com.acme.orders.OrdersService.publish"
    topic_raw: str          # exact string arg from source (may contain ${...})
    topic_resolved: str     # after ConfigValueStore resolution (== raw if literal)
    confidence: str         # EXTRACTED | INFERRED | SYMBOLIC | AMBIGUOUS
    provenance: str         # short human tag: literal / config:<key> / unresolved:<key> / identifier:<name>
    source_file: str
    line: int               # 1-based
    call_shape: str         # "template.send" | "producer.send" | "new ProducerRecord"


@dataclass(frozen=True)
class KafkaConsumerRecord:
    fqn: str
    topic_raw: str
    topic_resolved: str
    confidence: str
    provenance: str
    source_file: str
    line: int
    is_pattern: bool = False   # True when the source used topicPattern=<regex>


@dataclass
class KafkaExtractionResult:
    producers: List[KafkaProducerRecord] = field(default_factory=list)
    consumers: List[KafkaConsumerRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.producers and not self.consumers


# ── Trigger detection ───────────────────────────────────────────────────────

_KAFKA_IMPORT_MARKERS = (
    "org.springframework.kafka",
    "org.apache.kafka",
)


def looks_like_kafka_source(source: str) -> bool:
    """Cheap pre-filter — skip files that clearly have no Kafka involvement.

    We do not want to classify unrelated `.send(...)` calls as producers, so
    files that neither import Kafka nor mention ``@KafkaListener`` are
    excluded outright.
    """
    if "@KafkaListener" in source:
        return True
    for marker in _KAFKA_IMPORT_MARKERS:
        if marker in source:
            return True
    return False


# ── Regexes for structural extraction ───────────────────────────────────────

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

# Producer call: `<recv>.send(<arg1>, ...)` — receiver is any identifier or
# chained access. We accept `<recv>.send(` and inspect the first argument.
_SEND_CALL_RE = re.compile(
    r"(?<![\w.])([A-Za-z_][\w]*)\s*\.\s*send\s*\(",
)

# `new ProducerRecord<...>(<arg1>, ...)` — first arg is topic.
_NEW_PRODUCER_RECORD_RE = re.compile(
    r"\bnew\s+ProducerRecord\s*(?:<[^>]*>)?\s*\(",
)

# `@KafkaListener(...)` block; the parenthesised body is captured separately
# with brace/paren tracking (a regex can't reliably balance parens with SpEL,
# arrays, and nested annotations inside).
_KAFKA_LISTENER_RE = re.compile(r"@KafkaListener\s*\(")

# Simple `String NAME = "...";` scan for identifier tracing.
# Deliberately narrow: package/import/local — we accept only string-literal
# assignments so we never invent a value out of a method call.
_STRING_CONST_RE = re.compile(
    r"(?:^|[\s;{])(?:public|private|protected|static|final|\s)*\s*String\s+([A-Za-z_]\w*)\s*=\s*\"([^\"]*)\"\s*;",
)

# Regex to find the next Java method name after `@KafkaListener(...)`.
# We consume any subsequent annotations, modifiers, generic parameters, and
# the return type, then capture the method identifier immediately before `(`.
# This is intentionally permissive — the goal is to find *some* method name
# even if the source formats the declaration across many lines.
_METHOD_NAME_AFTER_RE = re.compile(
    r"""
    \s*
    (?:@[\w.]+\s*(?:\([^)]*\))?\s*)*                    # trailing annotations
    (?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)*
    (?:<[^>]+>\s*)?                                     # generic parameters
    [\w.<>?,\s\[\]]+?\s+                                # return type (non-greedy)
    ([A-Za-z_]\w*)                                      # <-- method name
    \s*\(
    """,
    re.VERBOSE,
)


# ── Structural helpers ─────────────────────────────────────────────────────

@dataclass
class _ClassSpan:
    name: str
    start_offset: int   # position of the `{` after the class header
    end_offset: int     # position of the matching `}`
    depth: int          # nesting depth (outermost = 0)


def _find_matching_brace(text: str, open_pos: int) -> int:
    """Return the offset of the `}` that closes the `{` at ``open_pos``.

    Handles nested braces, // line comments, /* block comments */, ``"strings"``,
    ``'chars'``, and escape sequences inside strings. Returns ``-1`` if no
    matching close is found (malformed input).
    """
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        # Skip line comments
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            nl = text.find("\n", i)
            i = n if nl == -1 else nl
            continue
        # Skip block comments
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        # Skip strings
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        # Skip char literals
        if c == "'":
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_class_spans(source: str) -> List[_ClassSpan]:
    """Return spans of every ``class`` / ``interface`` / ``enum`` / ``@interface`` body.

    Nested types are included. Anonymous inner classes are ignored (they have
    no source-level name we could put into an FQN).
    """
    spans: List[_ClassSpan] = []
    # Match a class-like declaration up to the first `{`. We accept an
    # optional annotation-type-declaration marker (`@interface`).
    header_re = re.compile(
        r"\b(?:class|interface|enum|@interface)\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]*>)?"                         # generics
        r"(?:\s+extends\s+[\w.<>,\s]+?)?"          # extends
        r"(?:\s+implements\s+[\w.<>,\s]+?)?"       # implements
        r"(?:\s+permits\s+[\w.<>,\s]+?)?"          # sealed permits
        r"\s*\{",
        re.MULTILINE,
    )
    for m in header_re.finditer(source):
        name = m.group(1)
        open_brace = source.rfind("{", m.start(), m.end())
        if open_brace == -1:
            continue
        close_brace = _find_matching_brace(source, open_brace)
        if close_brace == -1:
            continue
        # Depth is derived at the end from the recorded start offsets.
        spans.append(_ClassSpan(name=name, start_offset=open_brace,
                                end_offset=close_brace, depth=0))
    # Compute nesting depth from containment.
    for s in spans:
        s.depth = sum(
            1 for other in spans
            if other is not s
            and other.start_offset < s.start_offset < other.end_offset
        )
    return spans


def _enclosing_class(spans: Sequence[_ClassSpan], offset: int) -> Optional[_ClassSpan]:
    """Return the innermost class span that contains ``offset``."""
    candidates = [s for s in spans if s.start_offset < offset < s.end_offset]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.depth)


def _offset_to_line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _extract_package(source: str) -> Optional[str]:
    m = _PACKAGE_RE.search(source)
    return m.group(1) if m else None


def _find_enclosing_method(
    source: str, class_span: _ClassSpan, offset: int
) -> Optional[str]:
    """Given a call-site offset inside a class, return the enclosing method name.

    We walk backward through the class body scanning for the last method
    declaration whose ``{`` opens before ``offset`` and whose matching ``}``
    closes after ``offset``.
    """
    # Look for method declarations inside this class only.
    method_re = re.compile(
        r"""
        (?:@[\w.]+\s*(?:\([^)]*\))?\s*)*                                # annotations
        (?:(?:public|private|protected|static|final|synchronized|abstract|default|native)\s+)*
        (?:<[^>]+>\s*)?                                                 # generics
        [\w.<>?,\s\[\]]+?\s+                                            # return type
        ([A-Za-z_]\w*)                                                  # method name
        \s*\([^)]*\)                                                    # params
        (?:\s*throws\s+[\w.,\s]+?)?                                     # throws
        \s*\{
        """,
        re.VERBOSE,
    )
    best: Optional[str] = None
    for m in method_re.finditer(source, class_span.start_offset, class_span.end_offset):
        brace = source.rfind("{", m.start(), m.end())
        if brace == -1 or brace >= offset:
            continue
        close = _find_matching_brace(source, brace)
        if close == -1 or close < offset:
            continue
        best = m.group(1)
    return best


# ── Value parsing (literal / placeholder / identifier) ─────────────────────

def _read_first_call_arg(source: str, open_paren_offset: int) -> Optional[str]:
    """Return the text of the first comma-separated argument.

    ``open_paren_offset`` is the offset of ``(`` after the callable. We
    respect nested parens, generic angle brackets, and string literals.
    """
    i = open_paren_offset + 1
    n = len(source)
    depth_paren = 0
    depth_angle = 0
    start = i
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "(":
            depth_paren += 1
        elif c == ")":
            if depth_paren == 0:
                return source[start:i].strip() or None
            depth_paren -= 1
        elif c == "<":
            depth_angle += 1
        elif c == ">":
            if depth_angle > 0:
                depth_angle -= 1
        elif c == "," and depth_paren == 0 and depth_angle == 0:
            return source[start:i].strip() or None
        i += 1
    return None


_STRING_LITERAL_RE = re.compile(r'^"([^"\\]*(?:\\.[^"\\]*)*)"$')


def _string_constants_in_class(source: str, class_span: _ClassSpan) -> dict:
    """Return a ``{IDENTIFIER: literal}`` map of trivial ``String X = "..."``
    field declarations inside the class."""
    body = source[class_span.start_offset:class_span.end_offset]
    result: dict = {}
    for m in _STRING_CONST_RE.finditer(body):
        result[m.group(1)] = m.group(2)
    return result


def _classify_arg(
    arg_text: str,
    store: Optional[ConfigValueStore],
    active_profile: str,
    string_consts: dict,
) -> Tuple[Optional[str], Optional[str], str, str]:
    """Turn a first-argument expression into ``(topic_raw, topic_resolved, confidence, provenance)``.

    Returns ``(None, None, "", "")`` when the expression is a shape we do not
    trace (method call, ternary, cast, etc.) so the caller can drop it.
    """
    text = arg_text.strip()

    # String literal — possibly containing placeholders.
    m = _STRING_LITERAL_RE.match(text)
    if m:
        raw = m.group(1)
        return _classify_literal(raw, store, active_profile)

    # Bare identifier — try to resolve against in-class string constants.
    if re.fullmatch(r"[A-Za-z_]\w*", text):
        const = string_consts.get(text)
        if const is not None:
            resolved_raw, resolved_val, tier, prov = _classify_literal(
                const, store, active_profile
            )
            return resolved_raw, resolved_val, tier, f"identifier:{text}→{prov}"
        return text, text, "AMBIGUOUS", f"identifier:{text}"

    # Anything else (`svc.getTopic()`, ternary, cast, string concat) — we do
    # not want to invent a value. Report as ambiguous with the raw text so
    # the caller sees a warning and can add a .cgc/wire.yml hint.
    return text, text, "AMBIGUOUS", "expression"


def _classify_literal(
    raw: str,
    store: Optional[ConfigValueStore],
    active_profile: str,
) -> Tuple[str, str, str, str]:
    """Classify a string-literal value (already unquoted)."""
    if "${" not in raw:
        return raw, raw, "EXTRACTED", "literal"
    if store is None:
        return raw, raw, "SYMBOLIC", "unresolved:no-store"
    resolution: PlaceholderResolution = store.resolve_placeholders(raw, active_profile)
    if resolution.fully_resolved():
        # Build a compact provenance tag from the first used key.
        if resolution.used:
            first_key, source_label = resolution.used[0]
            prov = f"config:{first_key}({source_label})"
        else:
            prov = "config:defaults"
        return raw, resolution.output, "INFERRED", prov
    first_unresolved = resolution.unresolved[0] if resolution.unresolved else "?"
    return raw, resolution.output, "SYMBOLIC", f"unresolved:{first_unresolved}"


# ── Consumer annotation parsing ─────────────────────────────────────────────

def _find_paren_end(source: str, open_paren_offset: int) -> int:
    """Return the offset of the ``)`` that closes the ``(`` at ``open_paren_offset``."""
    depth = 0
    i = open_paren_offset
    n = len(source)
    while i < n:
        c = source[i]
        if c == '"':
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


_ATTR_RE = re.compile(r"(topics|topicPattern)\s*=\s*")


def _parse_listener_topics(body: str) -> Tuple[List[str], bool]:
    """Given the parenthesised body of ``@KafkaListener(...)``, return
    ``([topic_raw, ...], is_pattern)``.

    Handles:
    * ``topics = "orders"``
    * ``topics = "${kafka.topic.orders}"``
    * ``topics = {"a", "b"}``
    * ``topicPattern = "orders.*"``
    * body with only a positional single-string value (rare, but treated as
      ``topics = <value>``)
    """
    m = _ATTR_RE.search(body)
    if not m:
        # Some Spring versions accept a positional value shape; fall back to
        # scanning for the first string literal.
        first = _first_literal_or_array(body)
        return first, False

    is_pattern = m.group(1) == "topicPattern"
    return _first_literal_or_array(body, start=m.end()), is_pattern


def _first_literal_or_array(text: str, start: int = 0) -> List[str]:
    """Return a list of string-literal payloads found at ``text[start:]``.

    Accepts a bare literal ``"x"`` or a brace array ``{"a", "b", ...}``.
    Returns ``[]`` when neither shape is present.
    """
    i = start
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return []
    if text[i] == "{":
        # Array literal — collect every quoted string.
        end = _find_matching_brace(text, i)
        if end == -1:
            end = n
        segment = text[i + 1 : end]
        return [s.group(1) for s in re.finditer(r'"((?:[^"\\]|\\.)*)"', segment)]
    if text[i] == '"':
        # Read one string literal.
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == '"':
                return [text[i + 1 : j]]
            j += 1
    return []


# ── Public entry points ────────────────────────────────────────────────────

def extract_from_source(
    source: str,
    path: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
) -> KafkaExtractionResult:
    """Extract Kafka producer/consumer records from a single Java file's text.

    ``path`` is used only for provenance (``source_file`` field); the extractor
    never reads it.
    """
    result = KafkaExtractionResult()
    if not looks_like_kafka_source(source):
        return result

    pkg = _extract_package(source)
    spans = _extract_class_spans(source)
    if not spans:
        result.warnings.append(f"{path}: no top-level class/interface found; skipping")
        return result

    path_str = str(path)
    # Cache in-class constants per span so we do not re-scan for every hit.
    class_consts_cache: dict = {}

    def _fqn(span: _ClassSpan, method: str) -> str:
        prefix = f"{pkg}." if pkg else ""
        return f"{prefix}{span.name}.{method}"

    # ── Producers: `<recv>.send(` ────────────────────────────────────────
    for m in _SEND_CALL_RE.finditer(source):
        span = _enclosing_class(spans, m.start())
        if span is None:
            continue
        method_name = _find_enclosing_method(source, span, m.start())
        if method_name is None:
            continue
        arg = _read_first_call_arg(source, m.end() - 1)  # `(` is at end-1
        if arg is None:
            continue
        # `.send(new ProducerRecord(...))` — the inner constructor is handled
        # by the ProducerRecord regex below; skip so we don't double-count.
        if arg.lstrip().startswith("new ProducerRecord"):
            continue
        consts = class_consts_cache.setdefault(
            id(span), _string_constants_in_class(source, span)
        )
        raw, resolved, tier, prov = _classify_arg(arg, store, active_profile, consts)
        if raw is None or resolved is None:
            continue
        result.producers.append(KafkaProducerRecord(
            fqn=_fqn(span, method_name),
            topic_raw=raw,
            topic_resolved=resolved,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
            call_shape="template.send" if m.group(1).lower().endswith("template")
                        else "producer.send",
        ))

    # ── Producers: `new ProducerRecord<...>(` ─────────────────────────────
    for m in _NEW_PRODUCER_RECORD_RE.finditer(source):
        span = _enclosing_class(spans, m.start())
        if span is None:
            continue
        method_name = _find_enclosing_method(source, span, m.start())
        if method_name is None:
            continue
        arg = _read_first_call_arg(source, m.end() - 1)
        if arg is None:
            continue
        consts = class_consts_cache.setdefault(
            id(span), _string_constants_in_class(source, span)
        )
        raw, resolved, tier, prov = _classify_arg(arg, store, active_profile, consts)
        if raw is None or resolved is None:
            continue
        result.producers.append(KafkaProducerRecord(
            fqn=_fqn(span, method_name),
            topic_raw=raw,
            topic_resolved=resolved,
            confidence=tier,
            provenance=prov,
            source_file=path_str,
            line=_offset_to_line(source, m.start()),
            call_shape="new ProducerRecord",
        ))

    # ── Consumers: `@KafkaListener(...)` ─────────────────────────────────
    for m in _KAFKA_LISTENER_RE.finditer(source):
        span = _enclosing_class(spans, m.start())
        if span is None:
            continue
        # `@KafkaListener(` — find the matching `)`.
        open_paren = m.end() - 1
        close_paren = _find_paren_end(source, open_paren)
        if close_paren == -1:
            result.warnings.append(
                f"{path}:{_offset_to_line(source, m.start())}: unbalanced @KafkaListener("
            )
            continue
        body = source[open_paren + 1:close_paren]

        # The method decl starts after `)`; find its identifier.
        after = source[close_paren + 1:]
        name_match = _METHOD_NAME_AFTER_RE.match(after)
        if name_match is None:
            result.warnings.append(
                f"{path}:{_offset_to_line(source, m.start())}: could not resolve method name after @KafkaListener"
            )
            continue
        method_name = name_match.group(1)

        topics, is_pattern = _parse_listener_topics(body)
        if not topics:
            result.warnings.append(
                f"{path}:{_offset_to_line(source, m.start())}: @KafkaListener with no readable topics= or topicPattern="
            )
            continue

        consts = class_consts_cache.setdefault(
            id(span), _string_constants_in_class(source, span)
        )
        for raw in topics:
            if is_pattern:
                # topicPattern is a regex, not a literal address — always AMBIGUOUS.
                result.consumers.append(KafkaConsumerRecord(
                    fqn=_fqn(span, method_name),
                    topic_raw=raw,
                    topic_resolved=raw,
                    confidence="AMBIGUOUS",
                    provenance="topicPattern",
                    source_file=path_str,
                    line=_offset_to_line(source, m.start()),
                    is_pattern=True,
                ))
                continue
            _, _, tier, prov = _classify_literal(raw, store, active_profile)
            resolved = _classify_literal(raw, store, active_profile)[1]
            result.consumers.append(KafkaConsumerRecord(
                fqn=_fqn(span, method_name),
                topic_raw=raw,
                topic_resolved=resolved,
                confidence=tier,
                provenance=prov,
                source_file=path_str,
                line=_offset_to_line(source, m.start()),
                is_pattern=False,
            ))

    return result


# ── Config-driven producer/consumer detection ───────────────────────────────
#
# Some services (Guice/Dropwizard-style, no Spring annotations) register
# Kafka producers/consumers entirely through YAML config: a `topicName` key
# sitting alongside a sibling `consumingEnabled` / `producingEnabled` /
# `publishingEnabled: true` flag, read generically at runtime by a queue
# manager. There is no Java-level literal or call site for the source-based
# extractor above to find — not "low confidence", but zero candidates.
#
# This walks the already-flattened ConfigValueStore (see config_scanner.py)
# for that shape directly, independent of any Java parsing.

_TOPIC_KEY_LEAVES = ("topicname", "topic")
_ENABLED_KEY_LEAVES = ("consumingenabled", "producingenabled", "publishingenabled")


def scan_config_kafka_bindings(store: ConfigValueStore) -> KafkaExtractionResult:
    """Detect `topicName` + `<...>Enabled: true` sibling pairs in config.

    Groups every flattened config entry by (source_file, parent_path) — the
    dotted/indexed key with its last segment stripped, e.g.
    ``clusterConfigs[1]`` for the key ``clusterConfigs[1].topicName`` — so
    that only genuine siblings (same YAML object) are matched together.
    """
    result = KafkaExtractionResult()
    groups: dict = {}
    for entry in store.all_entries():
        parent, sep, leaf = entry.key.rpartition(".")
        if not sep:
            continue
        groups.setdefault((entry.source_file, parent), {})[leaf.lower()] = entry

    for (source_file, parent), leaves in groups.items():
        topic_entry = next(
            (leaves[k] for k in _TOPIC_KEY_LEAVES if k in leaves), None
        )
        if topic_entry is None or not topic_entry.value:
            continue
        for enabled_leaf in _ENABLED_KEY_LEAVES:
            flag_entry = leaves.get(enabled_leaf)
            if flag_entry is None or flag_entry.value.strip().lower() != "true":
                continue
            # "config:" prefix marks a record with no backing Function node —
            # writer.py (CONFIG_ANCHOR_PREFIX) anchors its edge on :File instead.
            fqn = f"config:{parent}"
            provenance = f"config-pattern:{enabled_leaf}+{topic_entry.key}"
            if enabled_leaf == "consumingenabled":
                result.consumers.append(KafkaConsumerRecord(
                    fqn=fqn,
                    topic_raw=topic_entry.value,
                    topic_resolved=topic_entry.value,
                    confidence="INFERRED",
                    provenance=provenance,
                    source_file=source_file,
                    line=0,
                    is_pattern=False,
                ))
            else:
                result.producers.append(KafkaProducerRecord(
                    fqn=fqn,
                    topic_raw=topic_entry.value,
                    topic_resolved=topic_entry.value,
                    confidence="INFERRED",
                    provenance=provenance,
                    source_file=source_file,
                    line=0,
                    call_shape="config-binding",
                ))
    return result


__all__ = [
    "KafkaConsumerRecord",
    "KafkaExtractionResult",
    "KafkaProducerRecord",
    "extract_from_source",
    "looks_like_kafka_source",
    "scan_config_kafka_bindings",
]
