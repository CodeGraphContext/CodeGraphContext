"""Backend-shape classification shared by both graph renderers.

CodeGraphContext renders the same graph twice — offline via
``cli/cli_helpers.py`` and live via ``viz/server.py``. Each answered "is this
value a node or a relationship?" separately, and they drifted:
``cli_helpers`` duck-typed, ``viz/server`` matched on class name.

FalkorDB's edge class is named ``Edge``, which the server's class-name check
did not list, so every FalkorDB relationship was silently discarded — on the
backend that is CGC's default on Unix under Python 3.12+. The server's
``parse_rel`` already read FalkorDB edges correctly; it was never reached.

The shapes below were confirmed against each backend's real Python package,
not inferred:

    >>> # falkordb 1.x
    >>> type(edge).__name__, hasattr(edge, "type"), hasattr(edge, "relation")
    ('Edge', False, True)
    >>> hasattr(edge, "labels"), isinstance(edge, dict)
    (False, False)

    >>> # kuzu 0.11.3, MATCH (n)-[e]->(m) RETURN n, e, m
    >>> list(node.keys()); list(rel.keys())
    ['_id', '_label', 'name']
    ['_src', '_dst', '_label', '_id']

    >>> # ladybug — identical fields, uppercased
    >>> list(node.keys()); list(rel.keys())
    ['_ID', '_LABEL', 'name', 'path']
    ['_SRC', '_DST', '_LABEL', '_ID']

The driver packages are optional extras, so the fakes below reproduce the
attribute surface each one exposes rather than importing them.
"""
import pytest

from codegraphcontext.utils import graph_shapes
from codegraphcontext.viz import server


# --- driver fakes -------------------------------------------------------------

class _Neo4jNode(dict):
    """Neo4j's Node: carries .labels and is dict-convertible via Mapping."""
    def __init__(self, labels, props):
        super().__init__(props)
        self.labels = labels
        self.element_id = "4:abc:1"


class _Neo4jRel:
    """Neo4j's Relationship: .type plus full Node endpoints."""
    def __init__(self, start, end, type_):
        self.start_node, self.end_node, self.type = start, end, type_


class _FalkorNode:
    """falkordb.Node: .labels, but properties live in .properties."""
    def __init__(self, node_id, labels, properties):
        self.id, self.labels, self.properties = node_id, labels, properties


class _FalkorEdge:
    """falkordb.Edge: .relation / .src_node / .dest_node, no .type, no .labels.

    Endpoints are bare integer node ids, not Node objects.
    """
    def __init__(self, src_node, relation, dest_node, edge_id=10):
        self.src_node, self.relation, self.dest_node = src_node, relation, dest_node
        self.id = edge_id


# The classifier that shipped before this change keyed on ``type(val).__name__``,
# so the fakes must carry the *real* driver class names or the regression below
# would not reproduce faithfully: falkordb names them ``Node`` and ``Edge``.
_FalkorNode.__name__ = "Node"
_FalkorEdge.__name__ = "Edge"


KUZU_NODE = {"_id": "0:1", "_label": "File", "path": "/repo/a.py", "name": "a.py"}
KUZU_REL = {"_src": "0:1", "_dst": "0:2", "_label": "CONTAINS", "_id": "1:0"}
LADYBUG_NODE = {"_ID": "0:1", "_LABEL": "File", "path": "/repo/a.py", "name": "a.py"}
LADYBUG_REL = {"_SRC": "0:1", "_DST": "0:2", "_LABEL": "CONTAINS", "_ID": "1:0"}


def _falkor_pair():
    a = _FalkorNode(1, ["File"], {"name": "a.py", "path": "/repo/a.py"})
    b = _FalkorNode(2, ["Function"], {"name": "alpha", "path": "/repo/a.py"})
    return a, _FalkorEdge(a.id, "CONTAINS", b.id), b


# --- classification -----------------------------------------------------------

@pytest.mark.parametrize("value", [
    pytest.param(_Neo4jNode(["File"], {"name": "a.py"}), id="neo4j"),
    pytest.param(_FalkorNode(1, ["File"], {"name": "a.py"}), id="falkordb"),
    pytest.param(KUZU_NODE, id="kuzu"),
    pytest.param(LADYBUG_NODE, id="ladybug"),
])
def test_nodes_classify_as_nodes(value):
    assert graph_shapes.is_node(value) is True
    assert graph_shapes.is_relationship(value) is False


@pytest.mark.parametrize("value", [
    pytest.param(_Neo4jRel("a", "b", "CONTAINS"), id="neo4j"),
    pytest.param(_FalkorEdge(1, "CONTAINS", 2), id="falkordb"),
    pytest.param(KUZU_REL, id="kuzu"),
    pytest.param(LADYBUG_REL, id="ladybug"),
])
def test_relationships_classify_as_relationships(value):
    assert graph_shapes.is_relationship(value) is True
    assert graph_shapes.is_node(value) is False


def test_half_formed_relationship_is_neither():
    """A relationship dict missing an endpoint must not become a phantom node.

    It still carries ``_label``, so a bare label check would admit it as a node
    whose id is a relationship id. Classifying it as neither drops it, which is
    what the offline renderer has always done.
    """
    half = {"_src": "0:1", "_label": "CONTAINS"}
    assert graph_shapes.is_relationship(half) is False
    assert graph_shapes.is_node(half) is False


def test_meta_reads_either_casing():
    assert graph_shapes.meta(KUZU_NODE, "_label") == "File"
    assert graph_shapes.meta(LADYBUG_NODE, "_label") == "File"
    assert graph_shapes.meta({}, "_label", "fallback") == "fallback"
    assert graph_shapes.has_meta(LADYBUG_REL, "_src") is True
    assert graph_shapes.has_meta({}, "_src") is False


# --- the regression this consolidation exists for -----------------------------

def test_server_renders_falkordb_edges():
    """Before the shared classifier, `parse_element` matched relationships by
    class name — ``Relationship``/``KuzuRelationship``. FalkorDB's class is
    ``Edge``, so it matched no branch and every FalkorDB relationship was
    dropped, producing an edgeless graph on CGC's default Unix backend.
    """
    a, edge, b = _falkor_pair()
    nodes, edges = {}, []
    for value in (a, edge, b):
        server.parse_element(value, nodes, edges)

    # Nodes always survived — falkordb's node class is named ``Node``, which the
    # old class-name check did list. Only the edge was lost.
    assert sorted(nodes) == ["1", "2"]
    assert edges == [{"id": "10", "source": "1", "target": "2", "type": "CONTAINS"}]
