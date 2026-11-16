"""Call/inheritance resolution must not depend on where the repository is on disk.

The FQN path-substring heuristic (CALLS tiers 6/7, INHERITS) tested an import
name against the candidate's *absolute* path. A JS file importing ``_t``,
indexed from a ``tempfile.mkdtemp()`` copy whose random suffix started with
``t``, flipped its calls from tier-8 HEURISTIC_CALLS to tier-7 CALLS; a Python
file importing ``re`` re-picked its targets when the suffix contained ``re``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports
from codegraphcontext.tools.indexing.resolution.calls import (
    build_function_call_groups,
    import_path_in_candidate,
)
from codegraphcontext.tools.indexing.resolution.inheritance import build_inheritance_and_csharp_files
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

FILES = {
    # caller imports `_t` and calls an ambiguous `load` (two candidates -> tier 8)
    "widgets/button.js": (
        'import { _t } from "@web/core/l10n/translation";\n'
        "export function onClick(model) {\n"
        "    model.load();\n"
        "    return _t('x');\n"
        "}\n"
    ),
    "reports/controller.js": "export function load() {\n    return 1;\n}\n",
    "reports/other_ctrl.js": "export function load() {\n    return 2;\n}\n",
    # Python INHERITS: a dotted base through an import whose name (`re`) is not
    # in either candidate's repository path, so it must stay unresolved
    "pkg/models.py": "class Base:\n    pass\n",
    "pkg/other.py": "class Base:\n    pass\n",
    "pkg/user.py": "import re\n\nclass Child(re.Base):\n    pass\n",
}

EXT = {".js": "javascript", ".py": "python"}


def _resolve(root: Path):
    parsers = {}

    def get_parser(ext):
        lang = EXT.get(ext)
        if lang and lang not in parsers:
            parsers[lang] = TreeSitterParser(lang)
        return parsers.get(lang)

    files = sorted((root / rel for rel in FILES), key=lambda p: p.as_posix())
    imports_map = pre_scan_for_imports(files, EXT.keys(), get_parser)
    file_data = []
    for f in files:
        data = get_parser(f.suffix).parse(f, False)
        data["repo_path"] = str(root)  # as GraphBuilder.parse_file sets it
        file_data.append(data)
    file_data.sort(key=lambda d: d["path"])

    def rel(p):
        if not p:
            return p
        resolved = Path(p).resolve()
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            return f"<outside>/{resolved.name}"  # e.g. the __external__ sentinel

    calls = set()
    for group in build_function_call_groups(file_data, imports_map, None):
        for r in group:
            calls.add((r["caller_name"], rel(r["caller_file_path"]), r["called_name"],
                       rel(r["called_file_path"]), r["line_number"], r["resolution_tier"]))
    inherits = {
        (r.get("child_name"), rel(r.get("path") or r.get("child_path")), r.get("parent_name"),
         rel(r.get("resolved_parent_file_path") or r.get("parent_path")))
        for r in build_inheritance_and_csharp_files(file_data, imports_map)[0]
    }
    return calls, inherits


def _materialise(parent: Path) -> Path:
    root = parent / "proj"
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_placement_invariance(tmp_path):
    """Named so pytest's tmp_path (which embeds the test name) holds no imported name."""
    if "_t" in str(tmp_path) or "re" in str(tmp_path):
        pytest.skip(f"the temp root itself contains an imported name: {tmp_path}")
    neutral = _materialise(tmp_path / "copy_zq1w2e3r")
    # random tempfile suffixes that put an imported name into the absolute path
    hostile_t = _materialise(tmp_path / "copy_tq1w2e3r")
    hostile_re = _materialise(tmp_path / "copy_req1w2e3")
    baseline = _resolve(neutral)
    assert ("onClick", "widgets/button.js", "load", "reports/controller.js", 3, 8) in baseline[0]
    # `re.Base`: neither candidate's repository path contains `re` -> not resolved into the repo
    assert [row[3] for row in baseline[1] if row[0] == "Child"] == ["<outside>/__external__"], baseline[1]
    assert _resolve(hostile_t) == baseline
    assert _resolve(hostile_re) == baseline


def test_import_path_match_ignores_the_checkout_location():
    root = "/tmp/copy_tq1w2e3r/proj"
    candidate = root + "/account_reports/static/src/controller.js"
    assert not import_path_in_candidate("_t", candidate, root)
    assert import_path_in_candidate("account_reports.static", candidate, root)
    # without a root the old (absolute) behaviour is kept for callers that have none
    assert import_path_in_candidate("_t", candidate, None)
    # a candidate outside the root is tested as given
    assert import_path_in_candidate("elsewhere", "/opt/elsewhere/x.js", root)


# ── the indexed root is itself the top-level package ─────────────────────────
# `add_package_to_graph` indexes a package directory (…/site-packages/requests)
# and `cgc index src/mypkg` does the same: imports name the package itself, so
# matching must keep the repository directory's own name in the path.

PKG_FILES = {
    "adapters.py": "def send(x):\n    return x\n",
    "aaa/wrong.py": "def send(x):\n    return -x\n",
}
PKG_CALLERS = {
    # `import mypkg.adapters [as ad]` records the module path `mypkg.adapters`:
    # the needle `mypkg/adapters` only matches if the package dir name is kept,
    # so these two catch a matcher that strips the whole root.
    "import-module-alias": "import mypkg.adapters as ad\n\ndef go():\n    return ad.send(1)\n",
    "import-module-noalias": "import mypkg.adapters\n\ndef go():\n    return mypkg.adapters.send(1)\n",
    # Control. `from mypkg import adapters` records only the imported name
    # (`adapters`, PythonTreeSitterParser._find_imports), so the needle never
    # contains the package name and cannot tell the two roots apart — it must
    # simply keep resolving correctly.
    "from-module-import": "from mypkg import adapters\n\ndef go():\n    return adapters.send(1)\n",
}


def _resolve_pkg(root: Path, caller: str):
    files = dict(PKG_FILES, **{"sessions.py": caller})
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    parser = TreeSitterParser("python")
    paths = sorted(root.rglob("*.py"))
    imports_map = pre_scan_for_imports(paths, [".py"], lambda _ext: parser)
    data = []
    for f in paths:
        d = parser.parse(f, False)
        d["repo_path"] = str(root)
        data.append(d)
    return sorted(
        (Path(r["called_file_path"]).resolve().relative_to(root.resolve()).as_posix(), r["resolution_tier"])
        for group in build_function_call_groups(data, imports_map, None) for r in group
        if r["caller_name"] == "go"
    )


@pytest.mark.parametrize("variant", sorted(PKG_CALLERS))
def test_package_root_keeps_its_own_name_in_the_match(tmp_path, variant):
    """Root = …/site-packages/mypkg: `import mypkg.adapters` resolves to mypkg/adapters.py
    (tier 7), not to the first `send` candidate (aaa/wrong.py, tier 8)."""
    root = tmp_path / "site-packages" / "mypkg"
    assert _resolve_pkg(root, PKG_CALLERS[variant]) == [("adapters.py", 7)]


@pytest.mark.parametrize("variant", sorted(PKG_CALLERS))
def test_package_root_placement_invariance(tmp_path, variant):
    """The package-root answer does not depend on where the package dir lives."""
    a = _resolve_pkg(tmp_path / "x" / "site-packages" / "mypkg", PKG_CALLERS[variant])
    b = _resolve_pkg(tmp_path / "copy_mypkgq1" / "mypkg", PKG_CALLERS[variant])
    assert a == b == [("adapters.py", 7)]
