# src/codegraphcontext/tools/languages/gradle.py
"""Parse build.gradle / build.gradle.kts files to extract Gradle build graph data (#888)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from codegraphcontext.utils.debug_log import error_logger, info_logger


def _gradle_tokens(source: str):
    """Tokenize static DSL values without interpreting comments or string contents."""
    index = 0
    while index < len(source):
        if source[index].isspace():
            index += 1
            continue
        if source.startswith('//', index):
            end = source.find('\n', index + 2)
            index = len(source) if end < 0 else end
            continue
        if source.startswith('/*', index):
            index += 2
            depth = 1
            while index < len(source) and depth:
                if source.startswith('/*', index):
                    depth += 1
                    index += 2
                elif source.startswith('*/', index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            continue
        if source[index] in ('"', "'"):
            quote = source[index]
            delimiter = quote * 3 if source.startswith(quote * 3, index) else quote
            index += len(delimiter)
            start = index
            while index < len(source) and not source.startswith(delimiter, index):
                index += 2 if source[index] == '\\' else 1
            if index < len(source):
                yield ('string', source[start:index])
                index += len(delimiter)
            continue
        match = re.match(r'[A-Za-z_$][\w$]*', source[index:])
        if match:
            yield ('identifier', match.group())
            index += len(match.group())
        else:
            yield ('punctuation', source[index])
            index += 1


def _dependency_notations(source: str):
    tokens = list(_gradle_tokens(source))
    blocks = []
    used = set()
    known = {'implementation', 'api', 'compile', 'testImplementation', 'runtimeOnly',
             'compileOnly', 'testRuntimeOnly', 'annotationProcessor', 'classpath'}
    wrappers = {'platform', 'enforcedPlatform', 'testFixtures'}
    for index, (kind, value) in enumerate(tokens):
        if value == '{' and kind == 'punctuation':
            blocks.append(tokens[index - 1][1] if index else '')
        elif value == '}' and kind == 'punctuation':
            if blocks:
                blocks.pop()
        if kind != 'identifier' or 'constraints' in blocks:
            continue
        if value not in known and 'dependencies' not in blocks:
            continue
        if index and tokens[index - 1][1] == '.':
            continue
        config = value
        cursor = index + 1
        if cursor < len(tokens) and tokens[cursor][1] == '(':
            cursor += 1
        if config == 'add' and cursor + 2 < len(tokens) and tokens[cursor][0] == 'string' and tokens[cursor + 1][1] == ',':
            config = tokens[cursor][1]
            cursor += 2
        while cursor + 1 < len(tokens) and tokens[cursor][0] == 'identifier' and tokens[cursor][1] in wrappers and tokens[cursor + 1][1] == '(':
            cursor += 2
        if cursor in used or cursor >= len(tokens):
            continue
        if tokens[cursor] == ('identifier', 'project'):
            cursor += 1
            if cursor < len(tokens) and tokens[cursor][1] == '(':
                cursor += 1
            if cursor < len(tokens) and tokens[cursor][0] == 'string':
                target = tokens[cursor][1]
                if target.startswith(':') and '$' not in target:
                    used.add(cursor)
                    yield config, 'project', target
            continue
        if tokens[cursor][0] == 'string':
            coordinate = tokens[cursor][1]
            parts = coordinate.split(':')
            if len(parts) >= 2 and all(re.fullmatch(r'[\w.\-]+', p) for p in parts[:2]) and '$' not in coordinate:
                used.add(cursor)
                yield config, 'external', coordinate
            continue
        # Literal named-argument notation in either DSL: group =/ : "g".
        fields = {}
        while cursor + 2 < len(tokens) and tokens[cursor][0] == 'identifier' and tokens[cursor + 1][1] in ('=', ':') and tokens[cursor + 2][0] == 'string':
            fields[tokens[cursor][1]] = tokens[cursor + 2][1]
            cursor += 3
            if cursor < len(tokens) and tokens[cursor][1] == ',':
                cursor += 1
            else:
                break
        if fields.get('group') and fields.get('name') and not any('$' in v for v in fields.values()):
            yield config, 'external', ':'.join((fields['group'], fields['name'], fields.get('version', '')))

def _parse_settings_includes(repo_root: Path) -> Dict[str, str]:
    """Parse settings.gradle(.kts) at *repo_root* and return a map of
    module directory (relative to repo_root, POSIX-separated, e.g.
    "feature/symptoms") -> canonical Gradle path (e.g. ":feature:symptoms").

    Parenthesized and bare include statements may span lines. Tokenization
    excludes comments and quoted documentation before reading literal arguments.
    """
    includes: Dict[str, str] = {}
    for fname in ("settings.gradle.kts", "settings.gradle"):
        settings_path = repo_root / fname
        if not settings_path.is_file():
            continue
        try:
            source = settings_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            error_logger(f"[GRADLE] Cannot read {settings_path}: {exc}")
            continue
        tokens = list(_gradle_tokens(source))
        for index, token in enumerate(tokens):
            if token != ('identifier', 'include'):
                continue
            cursor = index + 1
            if cursor < len(tokens) and tokens[cursor][1] == '(':
                cursor += 1
            while cursor < len(tokens) and tokens[cursor][0] == 'string':
                value = tokens[cursor][1]
                if value.startswith(':') and '$' not in value:
                    includes[value[1:].replace(':', '/')] = ':' + value[1:].replace('/', ':')
                cursor += 1
                if cursor < len(tokens) and tokens[cursor][1] == ',':
                    cursor += 1
                else:
                    break
    return includes


def _resolve_module_name(
    gradle_path: Path,
    repo_root: Optional[Path],
    module_includes: Optional[Dict[str, str]],
) -> str:
    """Resolve the canonical GradleModule identity for *gradle_path*.

    When *repo_root* is known and the module's directory maps to a
    settings.gradle include, use that canonical path (e.g.
    ":feature:symptoms"). When it doesn't (no matching include, or no
    settings file at all), fall back to the path relative to the root
    project so sibling modules that share a leaf directory name (e.g. two
    "impl" modules under different parents) still don't collide.

    The root project's own build.gradle (gradle_path.parent == repo_root)
    is not itself declared via include() under normal Gradle convention,
    so it keeps the original leaf-directory-name behaviour — this is the
    single-module / no-includes compatibility path.
    """
    if repo_root is not None:
        try:
            rel_dir = gradle_path.parent.relative_to(repo_root).as_posix()
        except ValueError:
            rel_dir = None
        if rel_dir not in (None, ".", ""):
            if module_includes and rel_dir in module_includes:
                return module_includes[rel_dir]
            return ":" + rel_dir.replace("/", ":")

    module_name = gradle_path.parent.name
    if module_name == "" or gradle_path.parent == gradle_path.parent.parent:
        module_name = "root"
    return module_name


class GradleParser:
    """Parses a build.gradle / build.gradle.kts and returns build graph records."""

    def parse(
        self,
        gradle_path: Path,
        repo_root: Optional[Path] = None,
        module_includes: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse *gradle_path* and return a dict with keys:
            modules             List[dict] — GradleModule node records
            inter_module_deps   List[dict] — MODULE_DEPENDS_ON records
            external_libs       List[dict] — ExternalLibrary + USES_LIBRARY records

        *repo_root* and *module_includes* (as produced by
        _parse_settings_includes) are optional; when omitted, module
        identity falls back to the original leaf-directory-name behaviour.
        """
        try:
            source = gradle_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            error_logger(f"[GRADLE] Cannot read {gradle_path}: {exc}")
            return None

        # Canonical Gradle module identity (":feature:symptoms"), derived
        # from settings.gradle includes when available; falls back to the
        # path relative to the root project, or to the leaf directory name
        # for the root module itself / when no repo context is given.
        module_name = _resolve_module_name(gradle_path, repo_root, module_includes)

        module_record = {
            "name": module_name,
            "build_file": str(gradle_path),
        }

        inter_module_deps: List[Dict[str, Any]] = []
        external_libs: List[Dict[str, Any]] = []

        for configuration, kind, value in _dependency_notations(source):
            if kind == 'project':
                target = ':' + value[1:].lstrip('/').replace('/', ':')
                inter_module_deps.append({'src_name': module_name, 'tgt_name': target,
                                          'configuration': configuration})
            else:
                parts = value.split(':')
                version = parts[2].split('@', 1)[0] if len(parts) > 2 else ''
                external_libs.append({
                    'src_name': module_name, 'group_id': parts[0],
                    'artifact_id': parts[1], 'version': version,
                    'configuration': configuration,
                })

        return {
            "modules": [module_record],
            "inter_module_deps": inter_module_deps,
            "external_libs": external_libs,
        }


def parse_repo_gradle(repo_root: Path) -> Dict[str, Any]:
    """Walk *repo_root* for build.gradle / build.gradle.kts and merge into one dict."""
    parser = GradleParser()
    merged: Dict[str, Any] = {
        "modules": [],
        "inter_module_deps": [],
        "external_libs": [],
    }

    module_includes = _parse_settings_includes(repo_root)

    for gradle_path in sorted(repo_root.rglob("build.gradle*")):
        if gradle_path.name not in ('build.gradle', 'build.gradle.kts'):
            continue
        relative = gradle_path.relative_to(repo_root)
        if any(part in ("build", ".gradle", ".git") for part in relative.parts):
            continue
        result = parser.parse(gradle_path, repo_root=repo_root, module_includes=module_includes)
        if result:
            for key in merged:
                merged[key].extend(result.get(key, []))

    info_logger(
        f"[GRADLE] Discovered {len(merged['modules'])} Gradle modules, "
        f"{len(merged['external_libs'])} external lib references."
    )
    return merged
