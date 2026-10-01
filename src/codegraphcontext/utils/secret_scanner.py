# src/codegraphcontext/utils/secret_scanner.py
"""Detect and optionally redact secrets in string values destined for the graph DB.

Uses a combination of regex patterns (inspired by gitleaks/trufflehog) and
Shannon entropy analysis to identify likely secrets in source-code string
literals and variable values before they are persisted.
"""

from __future__ import annotations

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


# Spacing as tolerant as the BEGIN patterns above, or a block is tracked from nowhere.
_PEM_BEGIN = re.compile(r"-----BEGIN\s+(?:[A-Z]+\s+)*PRIVATE\s+KEY-----")
_PEM_END = re.compile(r"-----END\s+(?:[A-Z]+\s+)*PRIVATE\s+KEY-----")


def _scan_body(value: str, redact: bool) -> Tuple[str, bool, Optional[str]]:
    """Scan a multi-line value line by line and redact only the lines that carry a secret.

    Entropy is not applied here. A body of source clears its threshold on its own: any code
    containing one of the hint words scores above 3.8 bits, which is what made whole functions
    and classes disappear. Nothing replaces it for a body, which is a real reduction in what is
    detected -- see the pull request. A value with no newline never reaches here.
    """
    # `\s` matches a newline, so most patterns are written to span one: `password =` on one line
    # and its quoted value on the next is a single match here and none on any line. That has to be
    # checked whatever the line pass finds, or a second credential in the body switches it off.
    for index, pattern in enumerate(_SECRET_PATTERNS):
        match = pattern.search(value)
        if match and "\n" in match.group(0):
            return (REDACTED if redact else value), True, f"regex:{index}"

    lines = value.split("\n")
    found: Optional[str] = None
    in_key_block = False

    for index, line in enumerate(lines):
        if in_key_block:
            hit = "pem-block"
            in_key_block = not _PEM_END.search(line)
        elif _PEM_BEGIN.search(line):
            # The key material between BEGIN and END matches no pattern of its own.
            hit = "pem-block"
            in_key_block = not _PEM_END.search(line)
        else:
            hit = next((f"regex:{i}" for i, p in enumerate(_SECRET_PATTERNS) if p.search(line)), None)
        if hit:
            found = found or hit
            if redact:
                # split() leaves the \r of a CRLF body on the line it belongs to.
                lines[index] = REDACTED + ("\r" if line.endswith("\r") else "")

    if not found:
        return value, False, None
    return ("\n".join(lines) if redact else value), True, found


def scan_and_redact(value: str, redact: bool = False) -> Tuple[str, bool, Optional[str]]:
    """Scan a string value for secrets and optionally redact it.

    Returns
    -------
    (str, bool, str or None)
        ``(result_value, was_secret, pattern_name)``
    """
    if isinstance(value, str) and "\n" in value:
        # A body of code or documentation: replacing all of it over one line loses the rest.
        return _scan_body(value, redact)
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
            redacted_val, was_secret, pattern = scan_and_redact(val, redact=redact)
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
