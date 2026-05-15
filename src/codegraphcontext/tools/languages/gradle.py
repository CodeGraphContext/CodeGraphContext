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

# Matches: project(':module-name') or project(":module-name")
_PROJECT_DEP_PATTERN = re.compile(r"""project\(['"]:([\w.\-/]+)['"]\)""")

# Matches: rootProject.name = "name" or settings include(':module')
_SETTINGS_INCLUDE_PATTERN = re.compile(r"""include\(['"]:([\w.\-/]+)['"]\)""")

# configuration keyword for inter-module deps
_CONFIG_PREFIX_PATTERN = re.compile(
    r"""^(implementation|api|compile|testImplementation|runtimeOnly|compileOnly)\s+project""",
    re.MULTILINE,
)


class GradleParser:
    """Parses a build.gradle / build.gradle.kts and returns build graph records."""

    def parse(self, gradle_path: Path) -> Optional[Dict[str, Any]]:
        """Parse *gradle_path* and return a dict with keys:
            modules             List[dict] — GradleModule node records
            inter_module_deps   List[dict] — MODULE_DEPENDS_ON records
            external_libs       List[dict] — ExternalLibrary + USES_LIBRARY records
        """
        try:
            source = gradle_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            error_logger(f"[GRADLE] Cannot read {gradle_path}: {exc}")
            return None

        # Derive module name from directory name (mirrors Gradle convention)
        module_name = gradle_path.parent.name
        if module_name == "" or gradle_path.parent == gradle_path.parent.parent:
            module_name = "root"

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
        for m in re.finditer(r"""(\w+)\s+project\(['"]:([\w.\-/]+)['"]\)""", source):
            configuration = m.group(1)
            tgt_name = m.group(2).lstrip("/").replace("/", ":")
            # Derive simple name (last segment after colon)
            tgt_simple = tgt_name.split(":")[-1]
            inter_module_deps.append({
                "src_name": module_name,
                "tgt_name": tgt_simple,
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

    for gradle_path in sorted(repo_root.rglob("build.gradle*")):
        relative = gradle_path.relative_to(repo_root)
        if any(part in ("build", ".gradle", ".git") for part in relative.parts):
            continue
        result = parser.parse(gradle_path)
        if result:
            for key in merged:
                merged[key].extend(result.get(key, []))

    info_logger(
        f"[GRADLE] Discovered {len(merged['modules'])} Gradle modules, "
        f"{len(merged['external_libs'])} external lib references."
    )
    return merged
