"""Graph schema contract: labels and relationship types used by indexing."""

from codegraphcontext.tools.indexing import schema_contract as sc


def test_node_labels_include_core_entities():
    assert "File" in sc.NODE_LABELS
    assert "Function" in sc.NODE_LABELS
    assert "Repository" in sc.NODE_LABELS


def test_relationship_types_include_core_edges():
    assert "CONTAINS" in sc.RELATIONSHIP_TYPES
    assert "CALLS" in sc.RELATIONSHIP_TYPES
    assert "IMPORTS" in sc.RELATIONSHIP_TYPES


def test_function_merge_keys_triple():
    assert sc.FUNCTION_MERGE_KEYS == ("name", "path", "line_number")
