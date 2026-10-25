"""Graph schema contract: labels and relationship types used by indexing."""

from codegraphcontext.tools.indexing import schema_contract as sc


def test_node_labels_include_core_entities():
    assert "File" in sc.NODE_LABELS
    assert "Function" in sc.NODE_LABELS
    assert "Repository" in sc.NODE_LABELS


def test_relationship_types_include_core_edges():
    assert "CONTAINS" in sc.RELATIONSHIP_TYPES
    assert "CALLS" in sc.RELATIONSHIP_TYPES
    assert "HEURISTIC_CALLS" in sc.RELATIONSHIP_TYPES
    assert "IMPORTS" in sc.RELATIONSHIP_TYPES


def test_function_merge_keys_include_occurrence_index():
    """Identity gained occurrence_index in #1393; the old triple was not unique."""
    assert sc.FUNCTION_MERGE_KEYS == ("name", "path", "line_number", "occurrence_index")
    assert sc.CLASS_MERGE_KEYS == ("name", "path", "line_number", "occurrence_index")


# ── MULTI_REPO_LINKS schema contract (PR #1) ─────────────────────────────────
# The next block encodes the non-breaking contract for the multi-repo wire-
# coupling feature: schema entries are RESERVED unconditionally, but no runtime
# behavior changes when the MULTI_REPO_LINKS flag is off (asserted separately
# in test_multi_repo_links_default.py).

# Frozen 0.6.13 baseline. If any of these leave the contract without a major
# version bump AND a deprecation cycle, the traversal semantics that existing
# users' MCP queries and Cypher rely on will silently drift. Adds are allowed
# (and expected); removes/renames must break this test loudly.
_BASELINE_NODE_LABELS = frozenset({
    "Repository", "Directory", "File", "Function", "Class", "Trait",
    "Variable", "Interface", "Macro", "Struct", "Enum", "EnumMember",
    "Union", "Record", "Property", "Annotation", "Module", "Parameter",
    "MavenModule", "GradleModule", "ExternalLibrary",
    "Datasource", "DbTable", "DbColumn", "RedisKeyPattern",
})

_BASELINE_RELATIONSHIP_TYPES = frozenset({
    "CONTAINS", "CALLS", "HEURISTIC_CALLS", "IMPORTS", "INHERITS",
    "HAS_PARAMETER", "INCLUDES", "IMPLEMENTS", "PARTIAL_OF", "PART_OF",
    "DECORATED_BY", "METACLASS", "COMPANION_OF", "EMBEDS",
    "INJECTS", "EXPOSES_ENDPOINT", "PROVIDES_BEAN",
    "MODULE_DEPENDS_ON", "USES_LIBRARY", "CHILD_MODULE", "FILE_BELONGS_TO",
    "READS", "WRITES", "MAPS_TO", "HAS_COLUMN", "STORED_IN",
})


def test_pre_multi_repo_baseline_never_shrinks():
    """0.6.13 labels/relationships must remain, verbatim, no matter what."""
    missing_labels = _BASELINE_NODE_LABELS - sc.NODE_LABELS
    missing_rels = _BASELINE_RELATIONSHIP_TYPES - sc.RELATIONSHIP_TYPES
    assert not missing_labels, (
        f"NODE_LABELS regression: {sorted(missing_labels)} were removed. "
        "The 0.6.13 baseline must not shrink; downstream Cypher queries depend on it."
    )
    assert not missing_rels, (
        f"RELATIONSHIP_TYPES regression: {sorted(missing_rels)} were removed. "
        "The 0.6.13 baseline must not shrink; downstream Cypher queries depend on it."
    )


def test_multi_repo_wire_node_labels_present():
    for label in ("Topic", "Endpoint", "ConfigValue", "HintFile", "IndexWarning", "Stub"):
        assert label in sc.NODE_LABELS, f"missing wire label: {label}"


def test_multi_repo_wire_relationship_types_present():
    for rel in (
        "PRODUCES_TO", "CONSUMES_FROM", "SERVES", "INVOKES",
        "ALIAS_OF", "SUPERSEDED_BY", "HINTED_BY", "RESOLVED_FROM",
    ):
        assert rel in sc.RELATIONSHIP_TYPES, f"missing wire relationship: {rel}"


def test_multi_repo_wire_confidence_tiers_ordered():
    """Priority order matters: earlier tiers win when both apply to a pair."""
    assert sc.WIRE_CONFIDENCE_TIERS == (
        "DECLARED", "EXTRACTED", "INFERRED", "NORMALIZED",
        "SYMBOLIC", "AMBIGUOUS", "SUPERSEDED",
    )


def test_multi_repo_wire_merge_keys_are_wire_address_not_path():
    """Cross-repo linkage relies on wire-address identity; paths would island the graph."""
    assert sc.TOPIC_MERGE_KEYS == ("system", "name")
    assert sc.ENDPOINT_MERGE_KEYS == ("protocol", "method", "path")
    assert "path" not in sc.TOPIC_MERGE_KEYS
    assert "repo" not in sc.TOPIC_MERGE_KEYS
    assert "path" in sc.ENDPOINT_MERGE_KEYS  # the WIRE path, not the file path


def test_multi_repo_links_flag_name_matches_config_default_key():
    """PR #1 wires the schema constant to the config-manager key by name."""
    from codegraphcontext.cli.config_manager import DEFAULT_CONFIG
    assert sc.MULTI_REPO_LINKS_FLAG == "MULTI_REPO_LINKS"
    assert sc.MULTI_REPO_LINKS_FLAG in DEFAULT_CONFIG

