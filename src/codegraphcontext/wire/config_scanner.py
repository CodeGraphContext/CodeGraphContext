"""Scan a repository for Spring-style config files and populate a ConfigValueStore."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import yaml

from codegraphcontext.wire.config_values import (
    BASE_PROFILE,
    ConfigValue,
    ConfigValueStore,
    flatten_yaml,
)

DEFAULT_CONFIG_DIRS: tuple = (
    "src/main/resources",
    "src/main/resources/config",
    "resources",
    "config",
    ".",   # allow application.properties at the repo root
)

DEFAULT_MAX_FILE_KB = 512
_PROPERTIES_EXTS = (".properties",)
_YAML_EXTS = (".yml", ".yaml")

# application.properties / application-<profile>.properties
# application.yml         / application-<profile>.yml
_APPLICATION_STEM = re.compile(r"^application(?:-([a-zA-Z0-9_.-]+))?$")


def scan_repo_config(
    repo_root: Path,
    *,
    include_dirs: Sequence[str] = DEFAULT_CONFIG_DIRS,
    max_file_kb: int = DEFAULT_MAX_FILE_KB,
    extra_files: Optional[Sequence[Path]] = None,
) -> ConfigValueStore:
    """Walk the repo for common Spring config layouts and build a ConfigValueStore.

    Handles application.properties / application.yml plus their profile-suffixed
    siblings. Non-application files with the same extensions inside the scan
    directories are still ingested under BASE_PROFILE — many teams put
    Kafka topic definitions in dedicated files like `kafka.properties`.
    """
    repo_root = repo_root.resolve()
    store = ConfigValueStore(repo_root=str(repo_root))

    seen: set = set()
    for rel in include_dirs:
        d = (repo_root / rel).resolve()
        if not d.is_dir():
            continue
        for path in _walk_files(d, max_file_kb):
            if path in seen:
                continue
            seen.add(path)
            _ingest_file(path, repo_root, store)

    for path in extra_files or []:
        p = Path(path).resolve()
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        _ingest_file(p, repo_root, store)

    return store


def _walk_files(root: Path, max_file_kb: int) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _PROPERTIES_EXTS + _YAML_EXTS:
            continue
        try:
            if p.stat().st_size > max_file_kb * 1024:
                continue
        except OSError:
            continue
        yield p


def _ingest_file(path: Path, repo_root: Path, store: ConfigValueStore) -> None:
    profile = _profile_from_name(path)
    ext = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    if ext in _PROPERTIES_EXTS:
        entries = parse_properties(text)
        kind = "properties"
    else:
        entries = parse_yaml_kv(text)
        kind = "yaml"

    for key, value in entries:
        store.add(
            ConfigValue(
                repo_root=str(repo_root),
                key=key,
                value=value,
                source_file=str(path),
                source_kind=kind,
                profile=profile,
            )
        )


def _profile_from_name(path: Path) -> str:
    """Return the profile string for filenames of the shape `application-<profile>.<ext>`.

    Non-application files are treated as base configuration so downstream
    lookups still find their keys without requiring a fake profile name.
    """
    stem = path.stem
    m = _APPLICATION_STEM.match(stem)
    if not m:
        return BASE_PROFILE
    return m.group(1) or BASE_PROFILE


# ── Parsers ──────────────────────────────────────────────────────────────────

_PROPERTIES_LINE = re.compile(
    r"""^\s*                         # optional leading whitespace
        (?P<key>[^\s=:#!][^=:]*?)    # key: no leading whitespace/comment marker, up to = or :
        \s*[=:]\s*                   # separator (= or :)
        (?P<value>.*?)               # value (may be empty)
        \s*$""",
    re.VERBOSE,
)


def parse_properties(text: str) -> List[tuple]:
    """Parse a .properties file into (key, value) pairs.

    Supports `#` and `!` comments, backslash line continuations, and both
    `=` and `:` separators. Not a full spec-perfect parser — Unicode escapes
    and key/value trimming edge cases are deliberately left simple because
    the extractors only need literal string equality on the resolved value.
    """
    out: List[tuple] = []
    continuation: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line
        # Line continuation collapses into a single logical line.
        if continuation:
            line = continuation.pop() + line.lstrip()
        if line.rstrip().endswith("\\") and not line.rstrip().endswith("\\\\"):
            continuation.append(line.rstrip()[:-1])
            continue

        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        m = _PROPERTIES_LINE.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        value = m.group("value")
        if key:
            out.append((key, value))
    return out


def parse_yaml_kv(text: str) -> List[tuple]:
    """Parse a YAML document and flatten it into (dotted_key, str_value) pairs."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if doc is None:
        return []
    return list(flatten_yaml(doc))
