# src/codegraphcontext/tools/languages/gradle.py
"""Parse build.gradle / build.gradle.kts files to extract Gradle build graph data (#888)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from codegraphcontext.utils.debug_log import error_logger, info_logger

# Matches: implementation("group:artifact:version") or compile 'g:a:v'
_DEP_PATTERN = re.compile(
    r"""(?:implementation|api|compile|testImplementation|runtimeOnly|compileOnly|testRuntimeOnly|annotationProcessor)\s*[\('"]([\w.\-]+):([\w.\-]+):?([\w.\-]*)['"\)]""",
    re.MULTILINE,
)

# Matches: project(':module-name') or project(":feature:module-name")
_PROJECT_DEP_PATTERN = re.compile(r"""project\(['"]:([\w.\-/:]+)['"]\)""")

# Matches a whole `include(...)` / `include ...` statement (parenthesized or
# bare Groovy form, single or comma-separated multi-arg) up to its closing
# quote, e.g.:
#   include(":feature:symptoms")
#   include ':app'
#   include(":a", ":b")
# The quoted tokens are pulled out separately with _QUOTED_STRING_PATTERN so
# that colon-delimited (`:feature:symptoms`) paths survive intact.
_INCLUDE_STATEMENT_PATTERN = re.compile(
    r"""\binclude\s*\(?\s*((?:['"][^'"]+['"]\s*,\s*)*['"][^'"]+['"])"""
)
_QUOTED_STRING_PATTERN = re.compile(r"""['"]([^'"]+)['"]""")

# configuration keyword for inter-module deps
_CONFIG_PREFIX_PATTERN = re.compile(
    r"""^(implementation|api|compile|testImplementation|runtimeOnly|compileOnly)\s+project""",
    re.MULTILINE,
)


def _parse_settings_includes(repo_root: Path) -> Dict[str, str]:
    """Parse settings.gradle(.kts) at *repo_root* and return a map of
    module directory (relative to repo_root, POSIX-separated, e.g.
    "feature/symptoms") -> canonical Gradle path (e.g. ":feature:symptoms").

    Known limitation: only single-line include statements are recognised
    (parenthesized or bare Groovy form, single or comma-separated
    multi-arg). Include lists spanning multiple lines are not parsed.
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
        for stmt_match in _INCLUDE_STATEMENT_PATTERN.finditer(source):
            for token in _QUOTED_STRING_PATTERN.findall(stmt_match.group(1)):
                if not token.startswith(":"):
                    continue
                rel_dir = token[1:].replace(":", "/")
                includes[rel_dir] = token
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

        # Extract external dependencies
        for m in _DEP_PATTERN.finditer(source):
            group_id, artifact_id, version = m.group(1), m.group(2), m.group(3)
            # Determine configuration from the full line
            line_start = source.rfind("\n", 0, m.start()) + 1
            line_text = source[line_start : source.find("\n", m.start())]
            cfg_match = re.match(r"\s*(\w+)\s", line_text)
            configuration = cfg_match.group(1) if cfg_match else "implementation"
            external_libs.append({
                "src_name": module_name,
                "group_id": group_id,
                "artifact_id": artifact_id,
                "version": version,
                "configuration": configuration,
            })

        # Extract inter-module project dependencies
        for m in re.finditer(r"""(\w+)\s+project\(['"]:([\w.\-/:]+)['"]\)""", source):
            configuration = m.group(1)
            # Canonical target identity — same construction as module_name,
            # so both endpoints of MODULE_DEPENDS_ON agree by construction.
            # (Not the settings-derived lookup: the target module's own
            # settings.gradle entry is what defines its canonical name, and
            # project(...) already spells it out directly.)
            tgt_name = ":" + m.group(2).lstrip("/").replace("/", ":")
            inter_module_deps.append({
                "src_name": module_name,
                "tgt_name": tgt_name,
                "configuration": configuration,
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
