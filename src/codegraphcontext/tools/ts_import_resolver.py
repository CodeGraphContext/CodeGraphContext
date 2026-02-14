"""
TypeScript/JavaScript import path resolver.

Resolves import specifiers (e.g. './utils', '@/components/Button') to absolute
file paths on disk. Used during indexing to create Module nodes with resolved
paths instead of raw specifier strings.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..utils.debug_log import warning_logger

# Extensions to try, in priority order
_TS_EXTENSIONS = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs')
_INDEX_FILES = ('index.ts', 'index.tsx', 'index.js', 'index.jsx')


def _try_resolve_file(base_path: Path) -> Optional[str]:
    """Try to resolve a base path to an actual file on disk.

    Tries in order:
    1. Exact path (handles explicit extensions like ./data.json)
    2. base_path + each extension (.ts, .tsx, .js, .jsx, .mjs, .cjs)
    3. base_path/index.{ts,tsx,js,jsx}
    """
    # 1. Exact match
    if base_path.is_file():
        return str(base_path.resolve())

    # 2. Try extensions
    for ext in _TS_EXTENSIONS:
        candidate = base_path.with_suffix(ext)
        if candidate.is_file():
            return str(candidate.resolve())

    # 3. Try index files in directory
    if base_path.is_dir():
        for index_name in _INDEX_FILES:
            candidate = base_path / index_name
            if candidate.is_file():
                return str(candidate.resolve())

    # Also try index files even if directory doesn't exist yet as a dir
    # (handles case where base_path doesn't exist but base_path/index.ts does)
    for index_name in _INDEX_FILES:
        candidate = base_path / index_name
        if candidate.is_file():
            return str(candidate.resolve())

    return None


def _is_bare_specifier(import_source: str) -> bool:
    """Check if an import source is a bare specifier (npm package)."""
    if import_source.startswith('./') or import_source.startswith('../') or import_source.startswith('/'):
        return False
    return True


def _match_path_pattern(pattern: str, import_source: str) -> Optional[str]:
    """Match a tsconfig paths pattern against an import source.

    Pattern examples: "@/*", "#shared/*", "$config"
    Returns the wildcard capture if matched, or empty string for exact match, or None.
    """
    if '*' in pattern:
        prefix = pattern.split('*')[0]
        if import_source.startswith(prefix):
            return import_source[len(prefix):]
    elif import_source == pattern:
        return ''
    return None


def resolve_ts_import(
    import_source: str,
    importing_file_path: Path,
    project_root: Path,
    base_url: Optional[Path] = None,
    paths_map: Optional[Dict[str, List[str]]] = None,
) -> Optional[str]:
    """Resolve a TypeScript/JavaScript import specifier to an absolute file path.

    Args:
        import_source: Raw import specifier (e.g. './utils', '@/components/Button', 'react')
        importing_file_path: Absolute path of the file containing the import
        project_root: Project root directory
        base_url: Absolute path from tsconfig baseUrl (or None)
        paths_map: tsconfig compilerOptions.paths dict (or None)

    Returns:
        Resolved absolute file path as string, or None for bare/unresolvable specifiers.
    """
    if not import_source:
        return None

    # 1. Relative imports
    if import_source.startswith('./') or import_source.startswith('../'):
        base = importing_file_path.parent / import_source
        return _try_resolve_file(base)

    # 2. Alias imports (check paths_map before bare specifier detection)
    if paths_map:
        for pattern, replacements in paths_map.items():
            wildcard = _match_path_pattern(pattern, import_source)
            if wildcard is not None:
                resolve_base = base_url if base_url else project_root
                for replacement in replacements:
                    if '*' in replacement:
                        resolved_rel = replacement.replace('*', wildcard)
                    else:
                        resolved_rel = replacement
                    candidate = resolve_base / resolved_rel
                    result = _try_resolve_file(candidate)
                    if result:
                        return result

    # 3. Bare specifiers — skip (npm packages, Node builtins)
    if _is_bare_specifier(import_source):
        return None

    # 4. Absolute imports (rare, starting with /) — try resolve
    base = Path(import_source)
    return _try_resolve_file(base)


def parse_tsconfig_paths(project_root: Path) -> Tuple[Optional[Path], Dict[str, List[str]]]:
    """Parse tsconfig.json to extract baseUrl and paths mappings.

    Handles:
    - One level of 'extends'
    - JSON with // comments
    - Trailing commas

    Returns:
        (base_url_absolute, paths_map) or (None, {}) if no tsconfig found.
    """
    tsconfig_path = project_root / 'tsconfig.json'
    if not tsconfig_path.is_file():
        return None, {}

    try:
        base_url, paths_map = _parse_single_tsconfig(tsconfig_path, project_root)

        # Handle extends — load base config first, then overlay
        raw = _read_json_with_comments(tsconfig_path)
        extends = raw.get('extends')
        if extends:
            extends_path = (tsconfig_path.parent / extends).resolve()
            # Try adding .json if not present
            if not extends_path.is_file() and not extends_path.suffix:
                extends_path = extends_path.with_suffix('.json')
            if extends_path.is_file():
                parent_base_url, parent_paths = _parse_single_tsconfig(
                    extends_path, project_root
                )
                # Parent values are defaults; child overrides
                if base_url is None:
                    base_url = parent_base_url
                merged_paths = {**parent_paths, **paths_map}
                paths_map = merged_paths

        return base_url, paths_map
    except Exception as e:
        warning_logger(f"Failed to parse tsconfig.json at {tsconfig_path}: {e}")
        return None, {}


def _read_json_with_comments(path: Path) -> dict:
    """Read a JSON file that may contain // comments and trailing commas."""
    content = path.read_text(encoding='utf-8')
    # Strip single-line comments
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    # Strip trailing commas before } or ]
    content = re.sub(r',\s*([}\]])', r'\1', content)
    return json.loads(content)


def _parse_single_tsconfig(
    tsconfig_path: Path, project_root: Path
) -> Tuple[Optional[Path], Dict[str, List[str]]]:
    """Parse a single tsconfig.json file (without following extends)."""
    raw = _read_json_with_comments(tsconfig_path)
    compiler_options = raw.get('compilerOptions', {})

    # Parse baseUrl
    base_url = None
    base_url_raw = compiler_options.get('baseUrl')
    if base_url_raw is not None:
        base_url = (tsconfig_path.parent / base_url_raw).resolve()

    # Parse paths
    paths_map = compiler_options.get('paths', {})

    return base_url, paths_map
