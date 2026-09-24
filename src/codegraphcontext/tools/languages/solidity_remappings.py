# src/codegraphcontext/tools/languages/solidity_remappings.py
"""Foundry-style Solidity import remappings (parse-only; never executes Foundry)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class SolidityRemappingConfig:
    """Longest-prefix-first aliases: ``forge-std/`` → ``lib/forge-std/src/``."""

    aliases: Dict[str, str]


def parse_remapping_line(line: str) -> Optional[Tuple[str, str]]:
    trimmed = line.strip()
    if not trimmed or trimmed.startswith("#") or trimmed.startswith("//"):
        return None
    eq = trimmed.find("=")
    if eq <= 0:
        return None
    prefix = trimmed[:eq].strip()
    target = trimmed[eq + 1 :].strip().replace("\\", "/")
    if not prefix or not target:
        return None
    return prefix, target


def _load_remappings_txt(repo_path: Path, into: Dict[str, str]) -> None:
    path = repo_path / "remappings.txt"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for line in text.splitlines():
        parsed = parse_remapping_line(line)
        if parsed:
            into[parsed[0]] = parsed[1]


def _load_foundry_toml_remappings(repo_path: Path, into: Dict[str, str]) -> None:
    """Minimal foundry.toml remappings extractor — no TOML dependency."""
    path = repo_path / "foundry.toml"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    block = re.search(r"remappings\s*=\s*\[([\s\S]*?)\]", text)
    if not block:
        return
    for match in re.finditer(r"""["']([^"']+)["']""", block.group(1)):
        parsed = parse_remapping_line(match.group(1))
        if parsed:
            into[parsed[0]] = parsed[1]


def load_solidity_remappings(repo_path: Path) -> SolidityRemappingConfig:
    """Load remappings: foundry.toml first, then remappings.txt overrides."""
    aliases: Dict[str, str] = {}
    try:
        _load_foundry_toml_remappings(repo_path, aliases)
    except Exception:
        pass
    try:
        _load_remappings_txt(repo_path, aliases)
    except Exception:
        pass
    return SolidityRemappingConfig(aliases=aliases)


def apply_solidity_remapping(
    import_path: str, config: Optional[SolidityRemappingConfig]
) -> Optional[str]:
    """Apply longest-prefix remapping; return rewritten path or None."""
    if not config or not config.aliases:
        return None
    stripped = import_path.strip().strip("'\"").replace("\\", "/")
    if not stripped or stripped.startswith("."):
        return None

    best_prefix = ""
    best_target = ""
    for prefix, target in config.aliases.items():
        if stripped.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_target = target
    if not best_prefix:
        return None
    return best_target + stripped[len(best_prefix) :]


def find_solidity_project_root(start: Path, max_levels: int = 12) -> Optional[Path]:
    """Walk parents for foundry.toml or remappings.txt."""
    current = start if start.is_dir() else start.parent
    for _ in range(max_levels):
        if (current / "foundry.toml").is_file() or (current / "remappings.txt").is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def resolve_solidity_import_path(
    import_path: str,
    *,
    importer_file: Path,
    repo_path: Optional[Path] = None,
    config: Optional[SolidityRemappingConfig] = None,
) -> Tuple[str, Optional[str]]:
    """Return ``(effective_source, resolved_filesystem_path_or_none)``.

    Relative imports resolve against the importer directory. Remapped / bare
    imports resolve against the Foundry project root (or ``repo_path``).
    """
    raw = import_path.strip().strip("'\"").replace("\\", "/")
    project_root = repo_path
    if project_root is None:
        project_root = find_solidity_project_root(importer_file)

    cfg = config
    if cfg is None and project_root is not None:
        cfg = load_solidity_remappings(project_root)

    effective = raw
    remapped = apply_solidity_remapping(raw, cfg)
    if remapped:
        effective = remapped

    candidates: Iterable[Path]
    if effective.startswith("."):
        candidates = [(importer_file.parent / effective).resolve()]
    else:
        roots = []
        if project_root is not None:
            roots.append(project_root)
        if repo_path is not None and repo_path not in roots:
            roots.append(repo_path)
        roots.append(importer_file.parent)
        candidates = [(root / effective).resolve() for root in roots]

    for candidate in candidates:
        if candidate.is_file():
            return effective, candidate.as_posix()
        # Allow missing .sol suffix in remapping targets that already include it.
        if candidate.suffix == "" and candidate.with_suffix(".sol").is_file():
            return effective, candidate.with_suffix(".sol").as_posix()

    return effective, None
