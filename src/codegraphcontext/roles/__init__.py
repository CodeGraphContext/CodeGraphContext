# src/codegraphcontext/roles/__init__.py
"""Configurable AI role prompts for the MCP server.

Roles are loaded once at server startup and injected into the MCP
``initialize`` response (both ``instructions`` and
``serverInfo.systemPrompt``). When no role is configured the injection
is skipped entirely so existing users see byte-identical behaviour.

Precedence for role selection (highest first):

1. ``--role`` CLI flag on ``cgc mcp start``
2. ``CGC_MCP_ROLE`` environment variable
3. ``role`` key in ``.cgc/config.json``
4. Built-in default: *none* (no injection)

``--role-file`` overrides the *content* source regardless of which role
name was selected. Without an explicit role it implies ``custom``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Built-in role names that ship as .md files alongside this module.
BUILTIN_ROLES = frozenset({"reviewer", "architect", "auditor", "explainer"})

# Every valid --role value the user may pass.
VALID_ROLES = BUILTIN_ROLES | {"custom", "neutral"}

# Role files are injected into every MCP response, so they must stay small.
MAX_ROLE_FILE_BYTES = 64 * 1024  # 64 KB

# The documented default location for a user-authored custom role file.
DEFAULT_CUSTOM_ROLE_PATH = Path.home() / ".codegraphcontext" / "role.md"


def _builtin_role_path(role: str) -> Path:
    return Path(__file__).parent / f"{role}.md"


def load_builtin_role(role: str) -> str:
    """Load a built-in role .md file shipped with the package."""
    if role not in BUILTIN_ROLES:
        raise ValueError(
            f"Unknown built-in role {role!r}. Valid roles: {', '.join(sorted(VALID_ROLES))}"
        )
    path = _builtin_role_path(role)
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Built-in role file is empty: {path}")
    return content


def _is_role_path_allowed(path: Path) -> bool:
    """Check *path* against the path sandbox with documented exceptions.

    Role files are user configuration, not code to index, so the
    documented config directory ``~/.codegraphcontext/`` is always
    allowed regardless of ``CGC_ALLOWED_ROOTS``.

    The ``CGC_ALLOW_ALL_PATHS`` escape hatch from #1726 is honoured if
    present so role files work identically once that lands.
    """
    if os.environ.get("CGC_ALLOW_ALL_PATHS", "").strip().lower() in ("1", "true", "yes"):
        return True

    resolved = path.resolve()

    # Always allow the user config directory.
    config_dir = (Path.home() / ".codegraphcontext").resolve()
    try:
        resolved.relative_to(config_dir)
        return True
    except ValueError:
        pass

    # Otherwise apply the standard path sandbox.
    from ..utils.path_sandbox import is_path_allowed

    return is_path_allowed(resolved)


def load_role_file(path: Path | str) -> str:
    """Load a user-authored role file with validation.

    Raises ``ValueError`` with a clear message when the path is not a
    regular file, exceeds the size cap, is outside allowed roots, or is
    empty.
    """
    path = Path(path).expanduser()

    if not path.exists():
        raise ValueError(f"Role file not found: {path}")

    if not path.is_file():
        raise ValueError(
            f"Role path is not a regular file (directories and special files are not allowed): {path}"
        )

    if not _is_role_path_allowed(path):
        raise ValueError(
            f"Role file path is outside allowed roots: {path}. "
            f"Place it under ~/.codegraphcontext/ or add its directory to CGC_ALLOWED_ROOTS."
        )

    size = path.stat().st_size
    if size > MAX_ROLE_FILE_BYTES:
        raise ValueError(
            f"Role file too large: {size} bytes (max {MAX_ROLE_FILE_BYTES}). "
            f"Role files are injected into every MCP response and must stay small."
        )

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Role file is empty: {path}")

    return content


def resolve_role_prompt(
    cli_role: Optional[str] = None,
    cli_role_file: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """Resolve the effective role prompt text following the documented precedence.

    Returns ``None`` when no role is configured — callers must treat
    ``None`` as "inject nothing" to preserve byte-identical default
    behaviour.

    Raises ``ValueError`` for unknown role names or invalid role files.
    """
    # --- Select the role name ------------------------------------------------
    role_name: Optional[str] = None

    if cli_role:
        role_name = cli_role
    elif os.environ.get("CGC_MCP_ROLE"):
        role_name = os.environ["CGC_MCP_ROLE"]
    elif cli_role_file:
        # --role-file without an explicit --role implies custom.
        role_name = "custom"
    else:
        role_name = _role_from_project_config(project_root)

    # Normalise: None, empty, or "neutral" all mean "no injection".
    if role_name is None:
        return None
    role_name = role_name.strip().lower()
    if not role_name or role_name == "neutral":
        return None

    if role_name not in VALID_ROLES:
        raise ValueError(
            f"Unknown role {role_name!r}. Valid roles: {', '.join(sorted(VALID_ROLES))}"
        )

    # --- Resolve the content source -----------------------------------------
    if role_name == "custom":
        source = cli_role_file or str(DEFAULT_CUSTOM_ROLE_PATH)
        return load_role_file(source)

    # Built-in role: --role-file still overrides the content if given.
    if cli_role_file:
        return load_role_file(cli_role_file)

    return load_builtin_role(role_name)


def _role_from_project_config(project_root: Optional[Path]) -> Optional[str]:
    """Read the ``role`` key from ``.cgc/config.json``, if present."""
    try:
        from ..cli.project_config import load_project_config

        config = load_project_config(project_root)
        role = config.get("role")
        return str(role) if role else None
    except Exception:
        return None
