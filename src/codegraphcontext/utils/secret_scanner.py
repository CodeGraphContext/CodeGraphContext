# src/codegraphcontext/utils/secret_scanner.py
"""Detect and optionally redact secrets in string values destined for the graph DB.

Uses a combination of regex patterns (inspired by gitleaks/trufflehog) and
Shannon entropy analysis to identify likely secrets in source-code string
literals and variable values before they are persisted.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import Counter
from typing import Optional, Tuple

REDACTED = "[REDACTED]"

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:api[_-]?secret|apisecret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:secret[_-]?key|secretkey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:access[_-]?token|accesstoken)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:auth[_-]?token|authtoken)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:private[_-]?key|privatekey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"sk-(?:live|test|proj)-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gho_[A-Za-z0-9]{36}"),
    re.compile(r"ghu_[A-Za-z0-9]{36}"),
    re.compile(r"ghs_[A-Za-z0-9]{36}"),
    re.compile(r"ghr_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
    re.compile(r"glpat-[A-Za-z0-9\-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{20,})"),
    re.compile(r"(?i)(?:password|passwd|pwd)\s*[=:]\s*['\"]([^\s'\"]{4,})['\"]"),
    re.compile(r"(?i)(?:db[_-]?password|database[_-]?password|db[_-]?pwd)\s*[=:]\s*['\"]([^\s'\"]{4,})['\"]"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)(?:mongodb|postgres|mysql|redis|amqp)://[^\s'\"]{8,}"),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
    re.compile(r"-----BEGIN\s+EC\s+PRIVATE\s+KEY-----"),
    re.compile(r"-----BEGIN\s+DSA\s+PRIVATE\s+KEY-----"),
    re.compile(r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"[sp]k_(?:live|test)_[A-Za-z0-9]{20,}"),
    re.compile(r"rk_(?:live|test)_[A-Za-z0-9]{20,}"),
    re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"),
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    re.compile(r"heroku[_-]?(?:api[_-]?)?key\s*[=:]\s*['\"]?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"),
    re.compile(r"npm_[A-Za-z0-9]{36,}"),
    re.compile(r"napi_[A-Za-z0-9]{36,}"),
    re.compile(r"twilio[_-]?(?:account[_-]?)?(?:sid|token)\s*[=:]\s*['\"]?([A-Za-z0-9]{20,})"),
    # Appended, so existing findings keep their regex:N label.
    re.compile(r"(?i)(?:client[_-]?secret|clientsecret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:refresh[_-]?token|id[_-]?token|session[_-]?token|sas[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(?:connection[_-]?string|shared[_-]?key|account[_-]?key)\s*[=:]\s*['\"]([A-Za-z0-9_\-+/=~.:;, ]{16,})['\"]"),
]

_KEY_HINT_RE = re.compile(
    r"(?i)(?:key|secret|token|password|passwd|pwd|credential|auth|private|access)",
)

_ENTROPY_THRESHOLD = 4.5
_ENTROPY_WITH_HINT_THRESHOLD = 3.8
_MIN_ENTROPY_LEN = 16


def _shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    length = len(data)
    counts = Counter(data)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def is_likely_secret(value: str) -> Tuple[bool, Optional[str]]:
    """Check whether *value* looks like a hardcoded secret.

    Returns
    -------
    (bool, str or None)
        ``(True, pattern_name)`` when a secret is detected, ``(False, None)`` otherwise.
    """
    if not value or not isinstance(value, str):
        return False, None

    for i, pat in enumerate(_SECRET_PATTERNS):
        if pat.search(value):
            return True, f"regex:{i}"

    stripped = value.strip().strip("'\"")
    if len(stripped) >= _MIN_ENTROPY_LEN:
        entropy = _shannon_entropy(stripped)
        has_hint = bool(_KEY_HINT_RE.search(stripped))
        if entropy >= _ENTROPY_THRESHOLD and not stripped.startswith(("http://", "https://", "ftp://")):
            if has_hint or entropy >= 5.0:
                return True, "entropy"
        elif has_hint and entropy >= _ENTROPY_WITH_HINT_THRESHOLD:
            return True, "entropy"

    return False, None


_BODY_KEYS = frozenset({"source", "docstring"})

_PEM_BEGIN = re.compile(r"-----BEGIN\s+(?:[A-Z0-9]+\s+)*PRIVATE\s+KEY(?:\s+BLOCK)?-----")
_PEM_END = re.compile(r"-----END\s+(?:[A-Z0-9]+\s+)*PRIVATE\s+KEY(?:\s+BLOCK)?-----")
_STRING_LITERAL = re.compile(r"""(["'`])((?:\\.|(?!\1)[^\\\n])*)\1""")
_TOKEN = re.compile(r"[A-Za-z0-9+/_~\-]{%d,}=*" % _MIN_ENTROPY_LEN)
_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
_HEX = re.compile(r"[0-9a-fA-F]+")
_UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
_NAME_BEFORE = re.compile(r"([A-Za-z_][\w.\-]*)['\"]?\s*[=:,(]\s*['\"]?\Z")

_MIN_CLASS_SWITCH_RATE = 0.3
_HEX_ENTROPY_WITH_HINT_THRESHOLD = 3.0


def _class_switches(chars: list[str]) -> int:
    """Count changes between digit, lower and upper case, not counting a capital starting a word."""
    classes = [0 if c.isdigit() else 1 if c.islower() else 2 for c in chars]
    return sum(a != b and (a, b) != (2, 1) for a, b in zip(classes, classes[1:]))


def _is_opaque_token(token: str, prefix: str) -> bool:
    """Apply the entropy test to one token rather than to the text around it.

    The token must mix letters and digits. Like ``is_likely_secret``, a hint word lowers the bar,
    but only in the name the token is assigned to, not anywhere in the body. Without one, the
    token must also switch between digit, lower and upper case often, which random strings do
    and identifiers, paths and prose do not, and must not be a UUID. Hex cannot exceed 4 bits, so
    a named hex token is held to a lower threshold.
    """
    chars = [c for c in token if c.isalnum()]
    if not (any(c.isdigit() for c in chars) and any(c.isalpha() for c in chars)):
        return False
    name = _NAME_BEFORE.search(prefix)
    named = bool(name and _KEY_HINT_RE.search(name.group(1)))
    entropy = _shannon_entropy(token)
    if entropy >= _ENTROPY_WITH_HINT_THRESHOLD:
        if named:
            return True
        if _UUID.fullmatch(token):
            return False
        return _class_switches(chars) >= _MIN_CLASS_SWITCH_RATE * (len(chars) - 1)
    return named and entropy >= _HEX_ENTROPY_WITH_HINT_THRESHOLD and bool(_HEX.fullmatch(token))


def _secret_spans(value: str) -> Tuple[list[Tuple[int, int]], Optional[str]]:
    spans: list[Tuple[int, int]] = []
    labels: list[str] = []

    for begin in _PEM_BEGIN.finditer(value):
        end = _PEM_END.search(value, begin.end())
        spans.append((begin.start(), end.end() if end else len(value)))
        labels.append("pem-block")

    for index, pattern in enumerate(_SECRET_PATTERNS):
        for match in pattern.finditer(value):
            if not pattern.groups:
                spans.append(match.span())
            elif (
                value[match.start(1) - 1] not in "'\""
                and _IDENTIFIER.fullmatch(match.group(1))
                and not _is_opaque_token(match.group(1), "")
            ):
                continue
            else:
                spans.append(match.span(1))
            labels.append(f"regex:{index}")

    literals = [match.span(2) for match in _STRING_LITERAL.finditer(value)]
    literal_starts = [start for start, _ in literals]
    for match in _TOKEN.finditer(value):
        start, end = match.span()
        index = bisect.bisect_right(literal_starts, start) - 1
        literal = literals[index] if index >= 0 and end <= literals[index][1] else None
        if literal is None and _IDENTIFIER.fullmatch(match.group(0)):
            continue
        line_start = value.rfind("\n", 0, start) + 1
        if _is_opaque_token(match.group(0), value[line_start:start]):
            spans.append(literal or (start, end))
            labels.append("entropy")

    return spans, (labels[0] if labels else None)


def scan_body_and_redact(value: str, redact: bool = False) -> Tuple[str, bool, Optional[str]]:
    """Scan a multi-line code body and optionally redact only the parts that hold a secret.

    A pattern match replaces its captured value, or the whole match when the pattern captures
    nothing; an unquoted captured value that is a plain identifier names a variable and is left
    alone unless it looks opaque. A private key is replaced from BEGIN through END, or to the end
    of the value when END is missing. An opaque token (see ``_is_opaque_token``) replaces the
    string literal it sits in, or only itself outside one; a bare identifier is never a candidate.

    Returns
    -------
    (str, bool, str or None)
        ``(result_value, was_secret, pattern_name)``
    """
    spans, label = _secret_spans(value)
    if not spans:
        return value, False, None
    if not redact:
        return value, True, label

    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    parts = []
    cursor = 0
    for start, end in merged:
        parts.append(value[cursor:start])
        parts.append(REDACTED)
        cursor = end
    parts.append(value[cursor:])
    return "".join(parts), True, label


def scan_and_redact(value: str, redact: bool = False) -> Tuple[str, bool, Optional[str]]:
    """Scan a string value for secrets and optionally redact it.

    Returns
    -------
    (str, bool, str or None)
        ``(result_value, was_secret, pattern_name)``
    """
    detected, pattern = is_likely_secret(value)
    if detected and redact:
        return REDACTED, True, pattern
    return value, detected, pattern


def scan_props_and_redact(
    props: dict,
    redact: bool = False,
    sensitive_keys: Optional[set[str]] = None,
) -> Tuple[dict, list[Tuple[str, Optional[str]]]]:
    """Scan all string values in *props* for secrets.

    Parameters
    ----------
    props : dict
        Node properties dict.
    redact : bool
        If ``True``, replace detected secrets with ``[REDACTED]``.
    sensitive_keys : set of str, optional
        Extra property keys to always entropy-check regardless of pattern match.

    Returns
    -------
    (dict, list of (key, pattern))
        The (possibly redacted) props dict and a list of ``(key, pattern)``
        tuples for every secret detected.
    """
    findings: list[Tuple[str, Optional[str]]] = []
    result = {}
    for key, val in props.items():
        if isinstance(val, str):
            scan = scan_body_and_redact if key in _BODY_KEYS and "\n" in val else scan_and_redact
            redacted_val, was_secret, pattern = scan(val, redact=redact)
            if was_secret:
                findings.append((key, pattern))
                result[key] = redacted_val
            else:
                result[key] = val
        elif isinstance(val, list):
            new_list = []
            for item in val:
                if isinstance(item, str):
                    redacted_item, was_secret, pattern = scan_and_redact(item, redact=redact)
                    if was_secret:
                        findings.append((key, pattern))
                        new_list.append(redacted_item)
                    else:
                        new_list.append(item)
                else:
                    new_list.append(item)
            result[key] = new_list
        else:
            result[key] = val
    return result, findings
