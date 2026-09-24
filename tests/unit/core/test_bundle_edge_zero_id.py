"""
Regression tests for edges dropped when a node's new ID is `0`.

`_import_edge_batch` maps each edge endpoint through `_id_mapping` and skips the
edge when an endpoint is absent. The absence test was a truthiness test, so an
endpoint that mapped to a falsy-but-valid id was treated as missing.

FalkorDB's `id()` is 0-based and the Repository node is written first, so it
maps to `0` on every import: every `Repository -> *` edge was dropped. Nothing
surfaced it — `import_from_bundle` reports the edge count it *intended*, the
node counts match exactly, and a `cgc find name` style check never traverses
from Repository, so the graph looks whole until someone follows an edge out of
the repository root.

Neo4j (`elementId()` strings) and Kùzu/Ladybug (PK tuples) never produce a falsy
endpoint, which is why this only ever affected FalkorDB.
"""
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.cgc_bundle import CGCBundle


def _bundle(backend: str) -> CGCBundle:
    """A CGCBundle whose only real behaviour is its backend type."""
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = backend
    return CGCBundle(db_manager)


def _edge(from_id: str, to_id: str) -> dict:
    return {"from": from_id, "to": to_id, "type": "CONTAINS", "properties": {}}


def test_edge_from_node_mapped_to_zero_is_imported():
    """id 0 is a valid FalkorDB node id, not a missing mapping."""
    bundle = _bundle("falkordb")
    bundle._id_mapping = {"0": 0, "1": 1}
    session = MagicMock()

    bundle._import_edge_batch(session, [_edge("0", "1")])

    assert session.run.call_count == 1, (
        "edge out of the node mapped to id 0 was skipped; every Repository -> * "
        "edge is lost this way, silently"
    )


def test_edge_into_node_mapped_to_zero_is_imported():
    """The same endpoint check guards `to`, so cover both directions."""
    bundle = _bundle("falkordb")
    bundle._id_mapping = {"0": 0, "1": 1}
    session = MagicMock()

    bundle._import_edge_batch(session, [_edge("1", "0")])

    assert session.run.call_count == 1


def test_edge_with_unmapped_endpoint_is_still_skipped():
    """The guard must keep doing its job: a genuinely absent id is not an edge."""
    bundle = _bundle("falkordb")
    bundle._id_mapping = {"0": 0}
    session = MagicMock()

    bundle._import_edge_batch(session, [_edge("0", "does-not-exist")])

    assert session.run.call_count == 0


@pytest.mark.parametrize(
    "backend,mapping",
    [
        ("neo4j", {"0": "4:9f:0", "1": "4:9f:1"}),
        ("kuzudb", {"0": ("Repository", "path", "/r"), "1": ("File", "path", "/r/a")}),
    ],
)
def test_other_backends_are_unaffected(backend, mapping):
    """elementId strings and PK tuples were never falsy; keep it that way."""
    bundle = _bundle(backend)
    bundle._id_mapping = mapping
    session = MagicMock()

    bundle._import_edge_batch(session, [_edge("0", "1")])

    assert session.run.call_count == 1
