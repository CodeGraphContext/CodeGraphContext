# src/codegraphcontext/tools/languages/maven.py
"""Parse pom.xml files to extract Maven build graph data (#888)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Any, Dict, Optional

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


def _find(element, tag):
    child = element.find(_ns(tag))
    return element.find(tag) if child is None else child


class MavenParser:
    """Read static POM declarations; repository membership is resolved in a second pass."""

    def parse(self, pom_path: Path) -> Optional[Dict[str, Any]]:
        try:
            root = ET.parse(pom_path).getroot()
        except Exception as exc:
            error_logger(f"[MAVEN] Cannot parse {pom_path}: {exc}")
            return None
        parent = _find(root, 'parent')
        parent_group = _text(parent, 'groupId') if parent is not None else ''
        parent_version = _text(parent, 'version') if parent is not None else ''
        group = _text(root, 'groupId') or parent_group
        artifact = _text(root, 'artifactId')
        version = _text(root, 'version') or parent_version
        if not artifact:
            return None
        properties = {}
        property_node = _find(root, 'properties')
        if property_node is not None:
            properties = {p.tag.rsplit('}', 1)[-1]: (p.text or '').strip() for p in property_node}
        values = {
            **properties,
            'project.groupId': group, 'pom.groupId': group,
            'project.artifactId': artifact, 'pom.artifactId': artifact,
            'project.version': version, 'pom.version': version,
            'project.parent.groupId': parent_group, 'parent.groupId': parent_group,
            'project.parent.version': parent_version, 'parent.version': parent_version,
            'project.basedir': str(pom_path.parent), 'basedir': str(pom_path.parent),
        }

        def resolve(text, seen=frozenset()):
            def substitute(match):
                key = match.group(1)
                if key in seen or key not in values:
                    return match.group(0)
                return resolve(values[key], seen | {key})
            return re.sub(r'\$\{([^}]+)\}', substitute, text)

        module = {
            'group_id': resolve(group), 'artifact_id': resolve(artifact),
            'version': resolve(version), 'packaging': resolve(_text(root, 'packaging') or 'jar'),
            'pom_path': str(pom_path),
        }
        dependencies = []
        container = _find(root, 'dependencies')
        if container is not None:
            for dependency in container:
                target = resolve(_text(dependency, 'artifactId'))
                if target:
                    dependencies.append({
                        'src_artifact_id': module['artifact_id'],
                        'group_id': resolve(_text(dependency, 'groupId')),
                        'artifact_id': target, 'version': resolve(_text(dependency, 'version')),
                        'scope': resolve(_text(dependency, 'scope')) or 'compile',
                    })
        children = []
        container = _find(root, 'modules')
        if container is not None:
            for child in container:
                directory = resolve((child.text or '').strip())
                if directory:
                    children.append({
                        'parent_artifact_id': module['artifact_id'],
                        'child_artifact_id': directory,
                        'child_pom_path': str((pom_path.parent / directory / 'pom.xml').resolve()),
                    })
        return {'modules': [module], 'inter_module_deps': [],
                'external_libs': dependencies, 'child_relations': children}


def parse_repo_maven(repo_root: Path) -> Dict[str, Any]:
    parser = MavenParser()
    parsed = []
    for path in sorted(repo_root.rglob('pom.xml')):
        if any(part in ('target', 'build', '.git') for part in path.relative_to(repo_root).parts):
            continue
        data = parser.parse(path)
        if data:
            parsed.append(data)
    modules = [module for data in parsed for module in data['modules']]
    by_coordinate = {}
    by_path = {}
    for module in modules:
        by_coordinate.setdefault((module['group_id'], module['artifact_id']), []).append(module)
        by_path[Path(module['pom_path']).resolve()] = module
    result = {'modules': modules, 'inter_module_deps': [], 'external_libs': [], 'child_relations': []}
    for data in parsed:
        for dependency in data['external_libs']:
            targets = by_coordinate.get((dependency['group_id'], dependency['artifact_id']), [])
            if len(targets) == 1 and not (
                dependency['version'] and targets[0]['version'] and dependency['version'] != targets[0]['version']
            ):
                result['inter_module_deps'].append({
                    'src_artifact_id': dependency['src_artifact_id'],
                    'tgt_artifact_id': targets[0]['artifact_id'], 'scope': dependency['scope'],
                })
            else:
                result['external_libs'].append(dependency)
        for relation in data['child_relations']:
            child = by_path.get(Path(relation['child_pom_path']))
            if child is not None:
                result['child_relations'].append({
                    'parent_artifact_id': relation['parent_artifact_id'],
                    'child_artifact_id': child['artifact_id'],
                })
    info_logger(f"[MAVEN] Discovered {len(modules)} Maven modules and {len(result['external_libs'])} external libraries.")
    return result
