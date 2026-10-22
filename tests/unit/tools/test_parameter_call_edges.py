"""Function->Parameter CALLS: a call of a parameter (`fn()` inside `def apply(fn)`).

The resolver emits such a call as a ``type: "parameter"`` row whose
``called_line_number`` is the enclosing function's line. The writer filtered the
target on ``called.line_number``, but a Parameter node has no ``line_number``; it
stores its function's line as ``function_line_number``. Kùzu/LadybugDB refused
every Function->Parameter batch (binder error, swallowed) and Neo4j/FalkorDB
matched nothing, so these edges were never written on any backend.

Only a call OF the parameter qualifies: ``Math.min(…)`` inside
``clamp(value, min, max)`` calls a property that merely shares the name.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

EXT = {".py": "python", ".js": "javascript", ".ts": "typescript"}


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


def test_parameter_calls_are_edges_into_the_parameter_member_calls_are_not(tmp_path):
    """Function->Parameter CALLS: `fn()` in `apply(fn)`; but `Math.min(…)` in
    `clamp(value, min, max)` is not a call of the parameter `min`."""
    rows = _resolve(tmp_path, {
        "a.py": "def apply(fn):\n    return fn()\n",
        "b.ts": "export function clamp(value, min, max) { return Math.min(Math.max(value, min), max); }\n"
                "export function run(cb) { return cb(1); }\n",
    })
    params = {(c, call) for c, call, name, path, tier in rows if path == c and tier == 2 and name in ("fn", "cb", "min", "max")}
    assert params == {("a.py", "fn"), ("b.ts", "cb(1)")}, rows


def test_parameter_call_batch_matches_function_line_number_falkordb():
    """The Function->Parameter CALLS batch matches the Parameter on function_line_number
    (it has no line_number) — the same statement on every backend."""
    session = MagicMock()
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    writer = GraphWriter(driver, SimpleNamespace(get_backend_type=lambda: "falkordb"))
    row = {"type": "parameter", "caller_name": "apply", "caller_file_path": "/r/a.py", "caller_line_number": 1,
           "called_name": "fn", "called_file_path": "/r/a.py", "called_line_number": 1, "line_number": 2,
           "args": [], "full_call_name": "fn", "confidence": 0.95, "confidence_label": "EXTRACTED",
           "resolution_tier": 2}
    writer.write_function_call_groups([], [], [], [], [], [], [], [], [row], [])
    sent = [c.args[0] for c in session.run.call_args_list if c.args and "called:Parameter" in c.args[0]]
    assert sent and all("called.function_line_number = row.called_line_number" in q for q in sent), sent
    assert not any("called.line_number" in q for q in sent)
