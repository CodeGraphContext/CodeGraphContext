import pytest

from codegraphcontext.core.cgc_bundle import CGCBundle


class _FakeRecord(dict):
    pass


class _FakeResult:
    def single(self):
        return _FakeRecord(new_id="new-id")


class _FakeSession:
    def __init__(self):
        self.queries = []

    def run(self, query, **kwargs):
        self.queries.append((query, kwargs))
        return _FakeResult()


class _FakeDBManager:
    def get_backend_type(self):
        return "neo4j"


def test_import_node_batch_rejects_malicious_labels():
    bundle = CGCBundle(_FakeDBManager())
    session = _FakeSession()

    malicious_batch = [
        (["Function", "BadLabel} DETACH DELETE n //"], {"uid": "abc"}, "old-id"),
    ]

    with pytest.raises(ValueError, match="Invalid node label"):
        bundle._import_node_batch(session, malicious_batch, {})


def test_import_edge_batch_rejects_malicious_relationship_type():
    bundle = CGCBundle(_FakeDBManager())
    bundle._id_mapping = {"old-from": "from-id", "old-to": "to-id"}
    session = _FakeSession()

    malicious_edges = [
        {"from": "old-from", "to": "old-to", "type": "CALLS]->(x) DETACH DELETE x //"},
    ]

    with pytest.raises(ValueError, match="Invalid relationship type"):
        bundle._import_edge_batch(session, malicious_edges)
