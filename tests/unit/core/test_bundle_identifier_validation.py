"""Security regression tests: a .cgc bundle must not be able to inject Cypher."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.cgc_bundle import (
    BundleValidationError,
    CGCBundle,
    _validate_cypher_identifier,
)

INJECTIONS = [
    "Evil) WITH n MATCH (v:Victim) DETACH DELETE v //",
    "Function` ) DETACH DELETE n //",
    "A:B",
    "A B",
    "A-B",
    "A{x:1}",
    "A)",
    "",
    "1StartsWithDigit",
    "MATCH (n) DETACH DELETE n",
]

VALID = ["Function", "Class", "_Private", "Repo2", "ExternalClass", "DbTable"]


class _RecordingSession:
    def __init__(self):
        self.queries = []

    def run(self, query, **params):
        self.queries.append(query)
        result = MagicMock()
        result.single.return_value = {"new_id": 1}
        return result


def _bundle():
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "falkordb"
    return CGCBundle(db_manager)


@pytest.mark.parametrize("value", INJECTIONS)
def test_invalid_identifiers_are_rejected(value):
    with pytest.raises(BundleValidationError):
        _validate_cypher_identifier(value, "node label")


@pytest.mark.parametrize("value", VALID)
def test_valid_identifiers_are_accepted(value):
    assert _validate_cypher_identifier(value, "node label") == value


def test_node_label_injection_never_reaches_the_driver():
    """Labels are interpolated into the query text (they cannot be
    parameterised), so an unvalidated label is executable Cypher. Before the
    fix this produced, and ran:

        CREATE (n:Evil) WITH n MATCH (v:Victim) DETACH DELETE v //) SET n = $props ...
    """
    session = _RecordingSession()
    payload = "Evil) WITH n MATCH (v:Victim) DETACH DELETE v //"

    with pytest.raises(BundleValidationError):
        _bundle()._import_node_batch(session, [([payload], {"name": "x"}, 1)], {})

    assert session.queries == [], "no query may be issued for an invalid label"


def test_relationship_type_injection_never_reaches_the_driver():
    session = _RecordingSession()
    edge = {
        "from": 1,
        "to": 2,
        "type": "R]->() WITH 1 AS x MATCH (v:Victim) DETACH DELETE v //",
        "properties": {},
    }

    bundle = _bundle()
    bundle._id_mapping = {1: 1, 2: 2}

    with pytest.raises(BundleValidationError):
        bundle._import_edge_batch(session, [edge])

    assert session.queries == []


def test_legitimate_labels_still_build_a_query():
    session = _RecordingSession()
    _bundle()._import_node_batch(session, [(["Function"], {"uid": "u1"}, 1)], {})

    assert len(session.queries) == 1
    assert "MERGE (n:Function" in session.queries[0]


def _write_bundle(tmp_path: Path, nodes, edges) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(json.dumps({"cgc_version": "0.1.0"}))
    (bundle_dir / "schema.json").write_text(json.dumps({}))
    (bundle_dir / "nodes.jsonl").write_text("\n".join(json.dumps(n) for n in nodes))
    (bundle_dir / "edges.jsonl").write_text("\n".join(json.dumps(e) for e in edges))
    return bundle_dir


def test_bundle_is_rejected_before_any_node_is_written(tmp_path):
    """The import writes in batches with no transaction, so a malicious label
    halfway through the file would execute after earlier nodes had committed.
    Validation must happen up front."""
    nodes = [
        {"_labels": ["Function"], "_id": 1, "uid": "ok"},
        {"_labels": ["Evil) WITH n MATCH (v:Victim) DETACH DELETE v //"], "_id": 2},
    ]
    bundle_dir = _write_bundle(tmp_path, nodes, [])

    ok, message = _bundle()._validate_bundle(bundle_dir)

    assert ok is False
    assert "invalid node label" in message


def test_bundle_with_bad_relationship_type_is_rejected(tmp_path):
    nodes = [{"_labels": ["Function"], "_id": 1, "uid": "ok"}]
    edges = [{"from": 1, "to": 1, "type": "CALLS]->() DETACH DELETE n //"}]
    bundle_dir = _write_bundle(tmp_path, nodes, edges)

    ok, message = _bundle()._validate_bundle(bundle_dir)

    assert ok is False
    assert "invalid relationship type" in message


def test_clean_bundle_passes_validation(tmp_path):
    nodes = [{"_labels": ["Function"], "_id": 1, "uid": "ok"}]
    edges = [{"from": 1, "to": 1, "type": "CALLS"}]
    bundle_dir = _write_bundle(tmp_path, nodes, edges)

    ok, _ = _bundle()._validate_bundle(bundle_dir)

    assert ok is True
