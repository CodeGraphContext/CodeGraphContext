"""The callback pre-pass of build_function_call_groups, resolved in memory (no database).

The pre-pass looked callees and callbacks up by name across every language: a
Python ``reg(handler)`` produced edges into JavaScript (and into CSS selector
"functions"). Both the callee and the callback candidates must now be
language-compatible with the call site.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx", ".css": "css"}


class _Builder:
    def __init__(self):
        self.parsers: Dict[str, TreeSitterParser] = {}

    def get_parser(self, ext):
        lang = EXT.get(ext)
        if lang and lang not in self.parsers:
            self.parsers[lang] = TreeSitterParser(lang)
        return self.parsers.get(lang)


def _resolve(tmp_path: Path, tree: Dict[str, str]) -> List[Tuple[str, str, str, str, int]]:
    """(caller file, call text, callee name, callee file, tier) of every resolved call."""
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
    base = root.resolve().as_posix() + "/"
    out = []
    for group in build_function_call_groups(data, imports_map, None):
        for r in group:
            out.append((r["caller_file_path"].replace(base, ""), r.get("full_call_name"), r["called_name"],
                        r["called_file_path"].replace(base, ""), r["resolution_tier"]))
    return sorted(out)


def test_callbacks_stay_in_the_call_sites_language(tmp_path):
    rows = _resolve(tmp_path, {
        "py/app.py": "def handler():\n    pass\n\ndef reg(fn):\n    fn()\n\ndef go():\n    reg(handler)\n",
        "js/app.js": "function handler() {}\nfunction reg(fn) { fn(); }\nfunction go() { reg(handler); }\n",
        "js/only.js": "function jsOnly(fn) { fn(); }\nfunction onlyCb() {}\n",
        "py/caller.py": "def use():\n    jsOnly(onlyCb)\n",
        "css/site.css": ".handler { color: red; }\n",
    })
    callback_edges = {(c, name, path) for c, call, name, path, tier in rows if tier == 3}
    assert ("py/app.py", "handler", "py/app.py") in callback_edges          # same language: kept
    assert ("js/app.js", "handler", "js/app.js") in callback_edges
    for caller, _, target in callback_edges:
        assert Path(caller).suffix == Path(target).suffix, callback_edges
    # a Python call cannot pass a JavaScript function to a JavaScript function
    assert not any(c == "js/only.js" for c, _, _ in callback_edges), callback_edges


def test_callback_candidates_are_filtered_by_the_call_sites_language(tmp_path):
    """The callee is in the call site's language; the callback name exists only in
    another language: no edge (the callback filter, apart from the callee filter)."""
    rows = _resolve(tmp_path, {
        "py/app.py": "def reg(fn):\n    fn()\n\ndef go():\n    reg(onlyJsCb)\n",
        "js/cb.js": "function onlyJsCb() {}\n",
    })
    assert not [r for r in rows if r[2] == "onlyJsCb"], rows
