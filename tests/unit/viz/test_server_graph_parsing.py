"""Regression tests for viz/server.py's driver-shape parsing.

KùzuDB and LadybugDB share the same embedded-graph wire format (plain dict
records), but LadybugDB spells its internal metadata fields uppercase
(``_ID``/``_LABEL``/``_SRC``/``_DST``) where KùzuDB spells them lowercase
(``_id``/``_label``/``_src``/``_dst``). Confirmed by querying each backend's
real Python package directly — this is not a guess:

    >>> # real ladybug package, MATCH (n)-[r]->(m) RETURN n, r, m
    >>> list(node_row.keys())
    ['_ID', '_LABEL', 'name', 'path']
    >>> list(rel_row.keys())
    ['_SRC', '_DST', '_LABEL', '_ID']

    >>> # real kuzu package, same query
    >>> list(node_row.keys())
    ['_id', '_label', 'name', 'path']
    >>> list(rel_row.keys())
    ['_src', '_dst', '_label', '_id']

`_get_eid`/`parse_node`/`parse_rel`/`parse_element` only checked the
lowercase spelling, so every LadybugDB row was silently dropped and the
live web graph rendered empty (issue #1458).
"""
from codegraphcontext.viz import server


# --- KùzuDB shape: lowercase internal keys -----------------------------------

KUZU_NODE_A = {"_id": "0:1", "_label": "File", "path": "/repo/a.py", "name": "a.py"}
KUZU_NODE_B = {"_id": "0:2", "_label": "Function", "name": "alpha", "path": "/repo/a.py"}
KUZU_REL = {"_src": "0:1", "_dst": "0:2", "_label": "CONTAINS", "_id": "1:0"}

# --- LadybugDB shape: uppercase internal keys, everything else identical -----

LADYBUG_NODE_A = {"_ID": "0:1", "_LABEL": "File", "path": "/repo/a.py", "name": "a.py"}
LADYBUG_NODE_B = {"_ID": "0:2", "_LABEL": "Function", "name": "alpha", "path": "/repo/a.py"}
LADYBUG_REL = {"_SRC": "0:1", "_DST": "0:2", "_LABEL": "CONTAINS", "_ID": "1:0"}


def test_meta_reads_both_casings():
    assert server._meta(KUZU_NODE_A, "label") == "File"
    assert server._meta(LADYBUG_NODE_A, "label") == "File"
    assert server._meta({}, "label") is None


def test_get_eid_handles_both_casings():
    assert server._get_eid(KUZU_NODE_A) == "0:1"
    assert server._get_eid(LADYBUG_NODE_A) == "0:1"


def test_parse_element_classifies_ladybug_node_and_rel():
    """Before the fix, a LadybugDB node/rel dict matched neither branch in
    `parse_element` (both checks were lowercase-only), so nothing was ever
    routed to `parse_node`/`parse_rel`."""
    nodes_dict, edges = {}, []
    server.parse_element(LADYBUG_NODE_A, nodes_dict, edges)
    server.parse_element(LADYBUG_REL, nodes_dict, edges)
    server.parse_element(LADYBUG_NODE_B, nodes_dict, edges)

    assert "0:1" in nodes_dict and "0:2" in nodes_dict
    assert nodes_dict["0:1"]["type"] == "File"
    assert len(edges) == 1
    assert edges[0] == {"id": "1:0", "source": "0:1", "target": "0:2", "type": "CONTAINS"}


def test_parse_element_classifies_kuzu_node_and_rel():
    nodes_dict, edges = {}, []
    server.parse_element(KUZU_NODE_A, nodes_dict, edges)
    server.parse_element(KUZU_REL, nodes_dict, edges)
    server.parse_element(KUZU_NODE_B, nodes_dict, edges)

    assert "0:1" in nodes_dict and "0:2" in nodes_dict
    assert len(edges) == 1
    assert edges[0] == {"id": "1:0", "source": "0:1", "target": "0:2", "type": "CONTAINS"}


def test_parse_node_extracts_ladybug_properties():
    nodes_dict = {}
    server.parse_node(LADYBUG_NODE_A, nodes_dict)
    node = nodes_dict["0:1"]
    assert node["type"] == "File"
    assert node["name"] == "a.py"
    assert node["file"] == "/repo/a.py"


def test_parse_rel_resolves_ladybug_src_dst():
    edges = []
    server.parse_rel(LADYBUG_REL, edges)
    assert edges == [{"id": "1:0", "source": "0:1", "target": "0:2", "type": "CONTAINS"}]
