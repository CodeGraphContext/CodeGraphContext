# src/codegraphcontext/tools/languages/maven.py
"""Parse pom.xml files to extract Maven build graph data (#888)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from codegraphcontext.utils.debug_log import error_logger, info_logger

_MVN_NS = "http://maven.apache.org/POM/4.0.0"


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag, e.g. 'groupId' -> '{http://...}groupId'."""
    return f"{{{_MVN_NS}}}{tag}"


def _text(element: Any, tag: str, default: str = "") -> str:
    child = element.find(_ns(tag))
    if child is None:
        child = element.find(tag)  # also try without namespace
    return (child.text or "").strip() if child is not None else default


class MavenParser:
    """Parses a pom.xml file and returns structured build graph data."""

    def parse(self, pom_path: Path) -> Optional[Dict[str, Any]]:
        """Parse *pom_path* and return a dict compatible with GraphWriter.write_maven_build_graph().

        Keys returned:
            modules         List[dict]  — MavenModule node records
            inter_module_deps  List[dict]  — inter-module MODULE_DEPENDS_ON records
            external_libs   List[dict]  — ExternalLibrary node + USES_LIBRARY records
            child_relations List[dict]  — CHILD_MODULE edge records
        """
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
        except Exception as exc:
            error_logger(f"[MAVEN] Cannot parse {pom_path}: {exc}")
            return None

        # Resolve effective groupId/version — may be inherited from parent
        parent_el = root.find(_ns("parent"))
        parent_group = _text(parent_el, "groupId") if parent_el is not None else ""
        parent_version = _text(parent_el, "version") if parent_el is not None else ""

        group_id = _text(root, "groupId") or parent_group
        artifact_id = _text(root, "artifactId")
        version = _text(root, "version") or parent_version
        packaging = _text(root, "packaging") or "jar"

        if not artifact_id:
            return None

        this_module = {
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "packaging": packaging,
            "pom_path": str(pom_path),
        }

        # ── Child modules declared in <modules> section ───────────────────
        child_artifact_ids: List[str] = []
        modules_el = root.find(_ns("modules"))
        if modules_el is None:
            modules_el = root.find("modules")
        if modules_el is not None:
            for mod_el in modules_el:
                child_dir = (mod_el.text or "").strip()
                if child_dir:
                    # Use directory name as a proxy for artifactId when we don't know yet
                    child_artifact_ids.append(child_dir)

        # ── Dependencies ─────────────────────────────────────────────────
        inter_module_deps: List[Dict[str, Any]] = []
        external_libs: List[Dict[str, Any]] = []

        # Property interpolation for common version placeholders
        properties: Dict[str, str] = {}
        props_el = root.find(_ns("properties"))
        if props_el is None:
            props_el = root.find("properties")
        if props_el is not None:
            for prop in props_el:
                tag = prop.tag.replace(f"{{{_MVN_NS}}}", "")
                properties[tag] = (prop.text or "").strip()

        def _resolve_version(v: str) -> str:
            if v.startswith("${") and v.endswith("}"):
                key = v[2:-1]
                return properties.get(key, v)
            return v

        deps_container = root.find(_ns("dependencies"))
        if deps_container is None:
            deps_container = root.find("dependencies")

        if deps_container is not None:
            for dep in deps_container:
                dep_group = _text(dep, "groupId")
                dep_artifact = _text(dep, "artifactId")
                dep_version = _resolve_version(_text(dep, "version"))
                dep_scope = _text(dep, "scope") or "compile"

                if not dep_artifact:
                    continue

                # Heuristic: if groupId matches this POM's group → inter-module dep
                if dep_group and dep_group == group_id:
                    inter_module_deps.append({
                        "src_artifact_id": artifact_id,
                        "tgt_artifact_id": dep_artifact,
                        "scope": dep_scope,
                    })
                else:
                    external_libs.append({
                        "src_artifact_id": artifact_id,
                        "group_id": dep_group,
                        "artifact_id": dep_artifact,
                        "version": dep_version,
                        "scope": dep_scope,
                    })

        child_relations = [
            {"parent_artifact_id": artifact_id, "child_artifact_id": c}
            for c in child_artifact_ids
        ]

        return {
            "modules": [this_module],
            "inter_module_deps": inter_module_deps,
            "external_libs": external_libs,
            "child_relations": child_relations,
        }


def parse_repo_maven(repo_root: Path) -> Dict[str, Any]:
    """Walk *repo_root* for all pom.xml files and merge into a single build graph dict."""
    parser = MavenParser()
    merged: Dict[str, Any] = {
        "modules": [],
        "inter_module_deps": [],
        "external_libs": [],
        "child_relations": [],
    }

    for pom_path in sorted(repo_root.rglob("pom.xml")):
        # Skip very deep paths (e.g. target/ directories)
        relative = pom_path.relative_to(repo_root)
        if any(part in ("target", "build", ".git") for part in relative.parts):
            continue
        result = parser.parse(pom_path)
        if result:
            for key in merged:
                merged[key].extend(result.get(key, []))

    info_logger(
        f"[MAVEN] Discovered {len(merged['modules'])} pom.xml modules, "
        f"{len(merged['external_libs'])} external lib references."
    )
    return merged
