from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

IGNORE_DIRS = {
    '.git',
    'node_modules',
    '.venv',
    'venv',
    '__pycache__',
    'dist',
    'build',
    '.next',
    'target',
    'deps',
    '_build',
    '.cache',
    'backups',
    'logs',
}

PY_RE = [
    re.compile(r'^\s*import\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
    re.compile(r'^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+', re.MULTILINE),
]
JS_TS_RE = [
    re.compile(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"),
]
ELIXIR_RE = [
    re.compile(r'^\s*alias\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
    re.compile(r'^\s*import\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
    re.compile(r'^\s*use\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
]
MD_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)]+)\)')


@dataclass
class Node:
    id: str
    path: str
    type: str
    language: str
    size_bytes: int


def _is_ignored(rel_path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in rel_path.parts)


def _language_for(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    name = path.name.lower()
    if ext == '.py':
        return 'source', 'python'
    if ext in {'.js', '.jsx'}:
        return 'source', 'javascript'
    if ext in {'.ts', '.tsx'}:
        return 'source', 'typescript'
    if ext in {'.ex', '.exs'}:
        return 'source', 'elixir'
    if ext in {'.md', '.markdown'}:
        return 'doc', 'markdown'
    if ext == '.json':
        return 'config', 'json'
    if ext in {'.yaml', '.yml'}:
        return 'config', 'yaml'
    if ext in {'.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd'}:
        return 'script', 'shell'
    if ext in {'.toml', '.ini', '.cfg', '.conf'} or name in {
        'dockerfile', 'makefile', 'requirements.txt', 'pyproject.toml', 'mix.exs', 'package.json'
    }:
        return 'config', 'config'
    return 'other', 'unknown'


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return ''


def _extract_edges(rel_path: str, path: Path, text: str) -> list[dict[str, str]]:
    ext = path.suffix.lower()
    edges: list[dict[str, str]] = []

    if ext == '.py':
        for pattern in PY_RE:
            for match in pattern.finditer(text):
                token = match.group(1)
                edges.append({'source': rel_path, 'target': token, 'kind': 'import', 'evidence': token})
    elif ext in {'.js', '.jsx', '.ts', '.tsx'}:
        for pattern in JS_TS_RE:
            for match in pattern.finditer(text):
                token = match.group(1)
                edges.append({'source': rel_path, 'target': token, 'kind': 'import', 'evidence': token})
    elif ext in {'.ex', '.exs'}:
        for pattern in ELIXIR_RE:
            for match in pattern.finditer(text):
                token = match.group(1)
                edges.append({'source': rel_path, 'target': token, 'kind': 'elixir_ref', 'evidence': token})
    elif ext in {'.md', '.markdown'}:
        for match in MD_LINK_RE.finditer(text):
            token = match.group(1)
            edges.append({'source': rel_path, 'target': token, 'kind': 'markdown_link', 'evidence': token})

    # De-duplicate while keeping stable order.
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for edge in edges:
        key = (edge['source'], edge['target'], edge['kind'], edge['evidence'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def _agent_readme_text() -> str:
    return """# Agent Context Graph Protocol

Before task work:

1. Check for `.agent/graph/code_graph.json`.
2. Check for `.agent/context_index.md`.
3. If either is missing, run the graph builder.
4. Read `.agent/context_index.md`.
5. Identify the relevant graph neighborhood.
6. State the intended edit boundary.
7. Avoid unrelated files.
8. After edits, rerun the graph builder.
9. Add a short work note in `.agent/work_notes/`.
10. End with one next action only.
"""


def _work_notes_text() -> str:
    return """# Agent Work Notes

Each task should create:

`YYYYMMDD-HHMM-task-name.md`

Template:

## Task
-

## Graph checked
-

## Relevant graph neighborhood
-

## Intended edit boundary
-

## Files changed
-

## Validation
-

## One next action
-
"""


def build_agent_graph(project_root: Path) -> int:
    try:
        root = project_root.resolve()

        nodes: list[Node] = []
        edges: list[dict[str, str]] = []

        for file_path in sorted(root.rglob('*')):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if _is_ignored(rel):
                continue

            rel_posix = rel.as_posix()
            file_type, language = _language_for(file_path)
            nodes.append(
                Node(
                    id=rel_posix,
                    path=rel_posix,
                    type=file_type,
                    language=language,
                    size_bytes=file_path.stat().st_size,
                )
            )

            text = _safe_read(file_path)
            edges.extend(_extract_edges(rel_posix, file_path, text))

        generated_at = datetime.now(timezone.utc).isoformat()

        graph_data = {
            'project_root': str(root),
            'generated_at': generated_at,
            'nodes': [node.__dict__ for node in nodes],
            'edges': edges,
            'summary': {
                'node_count': len(nodes),
                'edge_count': len(edges),
                'language_counts': _count_languages(nodes),
            },
        }

        graph_dir = root / '.agent' / 'graph'
        _write(graph_dir / 'code_graph.json', json.dumps(graph_data, indent=2))
        _write(graph_dir / 'code_graph.md', _build_markdown_summary(graph_data))
        _write(graph_dir / 'code_graph.mmd', _build_mermaid(graph_data))
        _write(graph_dir / 'code_graph.dot', _build_dot(graph_data))
        _write(root / '.agent' / 'context_index.md', _build_context_index(graph_data))
        _write(root / '.agent' / 'README.md', _agent_readme_text())
        _write(root / '.agent' / 'work_notes' / 'README.md', _work_notes_text())

        print(f'[agent-graph] success: generated artifacts in {graph_dir}')
        return 0
    except Exception as exc:
        print(f'[agent-graph] failure: {exc}')
        return 1


def _count_languages(nodes: Iterable[Node]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node.language] = counts.get(node.language, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _build_markdown_summary(graph_data: dict) -> str:
    lines = [
        '# Code Graph Summary',
        '',
        f"- Generated: `{graph_data['generated_at']}`",
        f"- Project root: `{graph_data['project_root']}`",
        f"- Nodes: **{graph_data['summary']['node_count']}**",
        f"- Edges: **{graph_data['summary']['edge_count']}**",
        '',
        '## Languages',
    ]
    lang_counts = graph_data['summary'].get('language_counts', {})
    lines.extend([f"- `{lang}`: {count}" for lang, count in lang_counts.items()] or ['- None'])
    lines.extend(['', '## Sample Nodes'])
    lines.extend([f"- `{node['path']}` ({node['language']})" for node in graph_data['nodes'][:30]] or ['- None'])
    return '\n'.join(lines) + '\n'


def _build_mermaid(graph_data: dict) -> str:
    lines = ['flowchart TD']
    nodes = graph_data['nodes'][:80]
    known = {n['id'] for n in nodes}

    for node in nodes:
        node_id = re.sub(r'[^A-Za-z0-9_]', '_', node['id'])
        label = node['path'].replace('"', "'")
        lines.append(f'  {node_id}["{label}"]')

    for edge in graph_data['edges'][:400]:
        src = edge['source']
        if src not in known:
            continue
        # Only draw intra-node edges when target resolves to known node id/path.
        target = edge['target']
        if target in known:
            src_id = re.sub(r'[^A-Za-z0-9_]', '_', src)
            tgt_id = re.sub(r'[^A-Za-z0-9_]', '_', target)
            lines.append(f'  {src_id} --> {tgt_id}')

    return '\n'.join(lines) + '\n'


def _build_dot(graph_data: dict) -> str:
    lines = ['digraph code_graph {']
    nodes = graph_data['nodes'][:80]
    known = {n['id'] for n in nodes}
    for node in nodes:
        lines.append(f'  "{node["path"]}";')
    for edge in graph_data['edges'][:400]:
        if edge['source'] in known and edge['target'] in known:
            lines.append(f'  "{edge["source"]}" -> "{edge["target"]}";')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def _build_context_index(graph_data: dict) -> str:
    lines = [
        '# Context Index',
        '',
        '## Required Pre-Task Steps',
        '- Check `.agent/graph/code_graph.json`.',
        '- Check `.agent/context_index.md`.',
        '- If missing, run the graph builder command.',
        '- Identify relevant graph neighborhood before edits.',
        '',
        '## Recent Node Samples',
    ]
    lines.extend([f"- `{node['path']}`" for node in graph_data['nodes'][:20]] or ['- None'])
    return '\n'.join(lines) + '\n'
