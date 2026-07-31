"""Regression tests for the offline visualization fallback."""
import inspect
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.cli import cli_helpers


class _Session:
    def __init__(self, records):
        self._records = records

    def run(self, query, **params):
        return iter(self._records)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Record(list):
    def values(self):
        return list(self)


def _db_manager(records):
    manager = MagicMock()
    manager.get_driver.return_value.session.return_value = _Session(records)
    return manager


# --- Kùzu / Ladybug shape: plain dicts with _id / _label / _src / _dst --------

KUZU_RECORDS = [
    _Record([
        {"_id": "0:1", "_label": "File", "path": "/repo/a.py", "name": "a.py"},
        {"_src": "0:1", "_dst": "0:2", "_label": "CONTAINS"},
        {"_id": "0:2", "_label": "Function", "name": "alpha", "path": "/repo/a.py",
         "line_number": 3},
    ])
]

# --- Ladybug shape: same dicts but with UPPERCASE internal keys (#1458) ------

LADYBUG_RECORDS = [
    _Record([
        {"_ID": "0:1", "_LABEL": "File", "path": "/repo/a.py", "name": "a.py"},
        {"_SRC": "0:1", "_DST": "0:2", "_LABEL": "CONTAINS"},
        {"_ID": "0:2", "_LABEL": "Function", "name": "alpha", "path": "/repo/a.py",
         "line_number": 3},
    ])
]

# --- Neo4j / Falkor shape: driver objects ------------------------------------

class _Node(dict):
    def __init__(self, element_id, labels, **props):
        super().__init__(**props)
        self.element_id = element_id
        self.labels = labels


class _Rel:
    def __init__(self, rel_type, start, end):
        self.type = rel_type
        self.start_node = start
        self.end_node = end


_N1 = _Node("4:1", ["File"], path="/repo/a.py", name="a.py")
_N2 = _Node("4:2", ["Function"], name="alpha", path="/repo/a.py", line_number=3)
NEO4J_RECORDS = [_Record([_N1, _Rel("CONTAINS", _N1, _N2), _N2])]

# --- Real FalkorDB shape: driver objects with `.labels` but NOT dict-like,
# properties live in `.properties`, and edges use `.src_node`/`.dest_node`/
# `.relation` instead of Neo4j's `.start_node`/`.end_node`/`.type`. -----------

class _FalkorNode:
    def __init__(self, node_id, labels, properties):
        self.id = node_id
        self.labels = labels
        self.properties = properties


class _FalkorEdge:
    def __init__(self, src_node, relation, dest_node, properties=None):
        # The real falkordb.Edge carries the bare integer node id here, NOT
        # a Node object — confirmed against an actual query result:
        # `r.src_node` is `<class 'int'>`, not `falkordb.node.Node`.
        self.src_node = src_node
        self.relation = relation
        self.dest_node = dest_node
        self.properties = properties or {}


_FN1 = _FalkorNode(1, ["File"], {"path": "/repo/a.py", "name": "a.py"})
_FN2 = _FalkorNode(2, ["Function"], {"name": "alpha", "path": "/repo/a.py", "line_number": 3})
FALKORDB_RECORDS = [_Record([_FN1, _FalkorEdge(_FN1.id, "CONTAINS", _FN2.id), _FN2])]


@pytest.mark.parametrize(
    "records,label",
    [
        (KUZU_RECORDS, "kuzu-style dicts"),
        (LADYBUG_RECORDS, "ladybug-style uppercase dicts"),
        (NEO4J_RECORDS, "neo4j-style objects"),
        (FALKORDB_RECORDS, "real falkordb-style objects"),
    ],
)
def test_offline_renderer_handles_both_driver_shapes(records, label, tmp_path, monkeypatch):
    """Kùzu/Ladybug return plain dicts carrying `_label`/`_src`/`_dst`. Neo4j
    returns driver objects with `.labels`/`.type` that are dict-convertible.
    FalkorDB also carries `.labels` but is NOT dict-convertible (properties
    live in `.properties`), and its edges use `.src_node`/`.dest_node`/
    `.relation` rather than `.start_node`/`.end_node`/`.type`. The renderer
    must understand all three shapes or it crashes (FalkorDB) or silently
    produces an empty graph."""
    monkeypatch.setattr("webbrowser.open", lambda *_a, **_k: True)
    out = tmp_path / "graph.html"

    cli_helpers._render_offline_visualization(
        _db_manager(records), repo_path="/repo", output_path=str(out)
    )

    assert out.exists(), f"no HTML rendered for {label}"
    html = out.read_text(encoding="utf-8")
    assert "alpha" in html, f"node data missing for {label}"
    assert "CONTAINS" in html, f"edge data missing for {label}"


def test_offline_renderer_is_self_contained(tmp_path, monkeypatch):
    """The point of the fallback is that it needs no bundled assets, so the
    page must not reference any external resource."""
    monkeypatch.setattr("webbrowser.open", lambda *_a, **_k: True)
    out = tmp_path / "graph.html"

    cli_helpers._render_offline_visualization(
        _db_manager(KUZU_RECORDS), output_path=str(out)
    )

    html = out.read_text(encoding="utf-8")
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "https://" not in html.replace("https://www.w3.org", "")


def test_offline_renderer_reports_an_empty_graph(monkeypatch, tmp_path):
    monkeypatch.setattr("webbrowser.open", lambda *_a, **_k: True)

    with pytest.raises(Exception):  # typer.Exit
        cli_helpers._render_offline_visualization(
            _db_manager([]), output_path=str(tmp_path / "x.html")
        )


def test_visualize_falls_back_instead_of_exiting():
    """`cgc visualize` used to `raise SystemExit(1)` when viz/dist was absent —
    which it always is, because the wheel never shipped it."""
    source = inspect.getsource(cli_helpers.visualize_helper)
    assert "_render_offline_visualization" in source, (
        "missing assets must degrade to the offline renderer, not exit"
    )


def test_sync_viz_dist_script_exists_and_is_executable():
    """The CLI error message told users to run ./scripts/sync_viz_dist.sh,
    which did not exist."""
    repo_root = Path(cli_helpers.__file__).resolve().parents[3]
    script = repo_root / "scripts" / "sync_viz_dist.sh"

    assert script.is_file(), f"{script} is referenced by the CLI but missing"
    assert os.access(script, os.X_OK), f"{script} is not executable"
    assert "viz/dist" in script.read_text(encoding="utf-8")
