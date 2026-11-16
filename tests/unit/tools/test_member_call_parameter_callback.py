"""The callback / parameter branch of build_function_call_groups, resolved in memory (no database).

The branch reads only a call OF a parameter: ``Math.max(v, max)`` inside
``function clamp(v, max)`` calls a property named ``max``, so it is no callback of
whatever callers pass as ``max``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python", ".js": "javascript"}


class _Builder:
    def __init__(self):
        self.parsers: Dict[str, TreeSitterParser] = {}

    def get_parser(self, ext):
        lang = EXT.get(ext)
        if lang and lang not in self.parsers:
            self.parsers[lang] = TreeSitterParser(lang)
        return self.parsers.get(lang)


def _resolve(tmp_path: Path, tree: Dict[str, str]) -> List[dict]:
    root = tmp_path / "repo"
    for rel, text in tree.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    files = sorted((root / rel for rel in tree), key=lambda p: p.as_posix())
    b = _Builder()
    imports_map = pre_scan_for_imports(files, EXT.keys(), b.get_parser)
    data = []
    for f in files:
        d = b.get_parser(f.suffix).parse(f, False)
        d["repo_path"] = str(root)
        data.append(d)
    return [r for group in build_function_call_groups(data, imports_map, None) for r in group]


def test_a_member_call_named_like_a_parameter_is_no_callback(tmp_path):
    rows = _resolve(tmp_path, {
        "a.js": ("export function clamp(v, max) { return Math.max(v, max); }\n"
                 "export function apply(fn) { return fn?.(1); }\n"
                 "export function handler() { return 0; }\n"
                 "export function main() { clamp(1, handler); apply(handler); }\n"),
        "b.py": ("from pathlib import Path\n"
                 "def scan(root, glob):\n    return Path(root).glob(glob)\n"
                 "def pattern():\n    return '*'\n"
                 "def main():\n    scan('.', pattern)\n"),
    })
    callbacks = {(r["caller_name"], r["called_name"]) for r in rows
                 if r.get("type") == "function" and r.get("resolution_tier") == 3}
    assert ("apply", "handler") in callbacks, rows          # `fn?.(1)` calls the parameter
    assert ("clamp", "handler") not in callbacks, rows      # `Math.max(…)` calls a property
    assert ("scan", "pattern") not in callbacks, rows       # `Path(root).glob(glob)` likewise
