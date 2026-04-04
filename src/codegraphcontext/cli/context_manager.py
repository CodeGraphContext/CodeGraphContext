from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import re
import yaml


GLOBAL_CONFIG_DIR = Path.home() / ".codegraphcontext"
GLOBAL_CONFIG_YAML = GLOBAL_CONFIG_DIR / "config.yaml"
CONTEXTS_DIR = GLOBAL_CONFIG_DIR / "contexts"

VALID_MODES = {"global", "per-repo", "shared"}


DEFAULT_CONTEXT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "default_context_mode": "global",
    "default_shared_context": "default",
    "contexts": {},
    "database": {
        "default_backend": "falkordb",
    },
}


@dataclass
class ContextResolution:
    mode: str
    context_name: Optional[str]
    context_dir: Path
    source: str


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def ensure_global_context_layout() -> None:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)


def load_global_context_config() -> Dict[str, Any]:
    ensure_global_context_layout()
    if not GLOBAL_CONFIG_YAML.exists():
        save_global_context_config(DEFAULT_CONTEXT_CONFIG)
        return dict(DEFAULT_CONTEXT_CONFIG)

    try:
        raw = yaml.safe_load(GLOBAL_CONFIG_YAML.read_text()) or {}
        if not isinstance(raw, dict):
            return dict(DEFAULT_CONTEXT_CONFIG)
        merged = _deep_merge(DEFAULT_CONTEXT_CONFIG, raw)
        if merged.get("default_context_mode") not in VALID_MODES:
            merged["default_context_mode"] = "global"
        return merged
    except Exception:
        return dict(DEFAULT_CONTEXT_CONFIG)


def save_global_context_config(config: Dict[str, Any]) -> None:
    ensure_global_context_layout()
    merged = _deep_merge(DEFAULT_CONTEXT_CONFIG, config or {})
    if merged.get("default_context_mode") not in VALID_MODES:
        merged["default_context_mode"] = "global"
    GLOBAL_CONFIG_YAML.write_text(yaml.safe_dump(merged, sort_keys=False))


def sanitize_context_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip())
    cleaned = cleaned.strip(".-_")
    if not cleaned:
        raise ValueError("Context name cannot be empty")
    return cleaned


def _resolve_context_dir_from_registry(config: Dict[str, Any], name: str) -> Path:
    contexts = config.get("contexts") or {}
    entry = contexts.get(name)
    if isinstance(entry, dict) and entry.get("path"):
        return Path(str(entry["path"])).expanduser().resolve()
    if isinstance(entry, str) and entry.strip():
        return Path(entry).expanduser().resolve()
    return (CONTEXTS_DIR / name).resolve()


def find_local_context_dir(start: Optional[Path] = None, max_levels: int = 8) -> Optional[Path]:
    current = (start or Path.cwd()).resolve()
    for _ in range(max_levels):
        candidate = current / ".codegraphcontext"
        if candidate.exists() and candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _target_repo_root(path_hint: Optional[Path]) -> Path:
    if path_hint:
        p = path_hint.resolve()
        return p if p.is_dir() else p.parent
    return Path.cwd().resolve()


def resolve_context(context_name: Optional[str] = None, path_hint: Optional[Path] = None) -> ContextResolution:
    cfg = load_global_context_config()

    if context_name:
        name = sanitize_context_name(context_name)
        context_dir = _resolve_context_dir_from_registry(cfg, name)
        context_dir.mkdir(parents=True, exist_ok=True)
        return ContextResolution(
            mode="shared",
            context_name=name,
            context_dir=context_dir,
            source="cli-override",
        )

    local_context_dir = find_local_context_dir(_target_repo_root(path_hint))
    if local_context_dir:
        return ContextResolution(
            mode="per-repo",
            context_name=None,
            context_dir=local_context_dir,
            source="local-context-dir",
        )

    mode = cfg.get("default_context_mode", "global")
    if mode == "per-repo":
        repo_root = _target_repo_root(path_hint)
        context_dir = repo_root / ".codegraphcontext"
        context_dir.mkdir(parents=True, exist_ok=True)
        return ContextResolution(
            mode="per-repo",
            context_name=None,
            context_dir=context_dir,
            source="global-default",
        )

    if mode == "shared":
        name = sanitize_context_name(cfg.get("default_shared_context", "default"))
        context_dir = _resolve_context_dir_from_registry(cfg, name)
        context_dir.mkdir(parents=True, exist_ok=True)
        return ContextResolution(
            mode="shared",
            context_name=name,
            context_dir=context_dir,
            source="global-default",
        )

    return ContextResolution(
        mode="global",
        context_name=None,
        context_dir=GLOBAL_CONFIG_DIR,
        source="global-default",
    )


def apply_context_environment(resolution: ContextResolution) -> None:
    resolution.context_dir.mkdir(parents=True, exist_ok=True)
    (resolution.context_dir / "logs").mkdir(parents=True, exist_ok=True)

    kuzu_path = resolution.context_dir / "kuzudb"
    falkor_path = resolution.context_dir / "falkordb.db"
    socket_path = resolution.context_dir / "falkordb.sock"
    log_path = resolution.context_dir / "logs" / "cgc.log"

    # Context-resolved defaults for backend storage locations.
    # Explicit shell vars can still override these later if needed.
    import os

    os.environ["CGC_CONTEXT_MODE"] = resolution.mode
    os.environ["CGC_CONTEXT_DIR"] = str(resolution.context_dir)
    os.environ["CGC_CONTEXT_SOURCE"] = resolution.source
    if resolution.context_name:
        os.environ["CGC_CONTEXT_NAME"] = resolution.context_name

    os.environ["KUZUDB_PATH"] = str(kuzu_path)
    os.environ["FALKORDB_PATH"] = str(falkor_path)
    os.environ["FALKORDB_SOCKET_PATH"] = str(socket_path)
    os.environ["LOG_FILE_PATH"] = str(log_path)

    # Shared contexts should use a context-scoped ignore file.
    if resolution.mode == "shared":
        os.environ["CGC_CONTEXT_CGCIGNORE"] = str(resolution.context_dir / ".cgcignore")
    else:
        os.environ.pop("CGC_CONTEXT_CGCIGNORE", None)


def set_default_context_mode(mode: str, shared_name: Optional[str] = None) -> Dict[str, Any]:
    mode = (mode or "").strip().lower()
    if mode not in VALID_MODES:
        raise ValueError("Invalid mode. Use: global, per-repo, shared")

    cfg = load_global_context_config()
    cfg["default_context_mode"] = mode
    if mode == "shared":
        if shared_name:
            cfg["default_shared_context"] = sanitize_context_name(shared_name)
        elif not cfg.get("default_shared_context"):
            cfg["default_shared_context"] = "default"

    save_global_context_config(cfg)
    return cfg
