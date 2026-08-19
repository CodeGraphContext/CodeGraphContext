"""
Regression tests for the (name, path) lookup indexes in create_graph_schema.

The 11 positional-identity labels get a four-property identity from #1393 --
(name, path, line_number, occurrence_index) -- and that UNIQUE constraint's
backing index is the only composite index they have. But the relationship
passes and code_finder look those nodes up by (name, path) alone:
write_inheritance_links matches `(child:<Label> {name: ..., path: ...})` for
every label pair it enumerates, write_function_call_groups matches the callee
by (name, path) in both the batched and the single-row path, and code_finder's
who_calls_function / what_does_function_call / find_class_hierarchy /
find_all_callers / find_all_callees do the same.

Neo4j uses a composite index only when EVERY indexed property has a predicate,
so the identity index cannot serve a two-property lookup and the planner falls
back to NodeByLabelScan + Filter once per row. The fix is one plain
(name, path) index per label.

FalkorDB must NOT receive them: it indexes per attribute rather than per
property tuple, so name and path are already covered by the composite
CREATE INDEX statements in its own branch, and re-indexing an attribute there
raises an error.
"""

from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.schema import (
    POSITIONAL_IDENTITY_LABELS,
    create_graph_schema,
)


class _RecordingSession:
    """Records every statement passed to .run(), whitespace-normalized."""

    def __init__(self):
        self.statements: list[str] = []

    def run(self, statement, *_args, **_kwargs):
        self.statements.append(" ".join(statement.split()))
        return MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self, **_kwargs):
        return self._session


def _run_schema(backend_type: str) -> list[str]:
    session = _RecordingSession()
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = backend_type
    create_graph_schema(_FakeDriver(session), db_manager)
    return session.statements


def _name_path_statements(statements: list[str]) -> list[str]:
    return [s for s in statements if "_name_path" in s]


def test_neo4j_creates_a_name_path_index_for_every_positional_label():
    """Every label with a positional identity needs the two-property index:
    the writers template the label, so Struct/Interface/Trait/... take the
    same (name, path) lookup path that Function and Class do."""
    statements = _run_schema("neo4j")

    for label, var in POSITIONAL_IDENTITY_LABELS.items():
        expected = (
            f"CREATE INDEX {label.lower()}_name_path IF NOT EXISTS "
            f"FOR ({var}:{label}) ON ({var}.name, {var}.path)"
        )
        assert statements.count(expected) == 1, (
            f"expected exactly one {expected!r}; got "
            f"{[s for s in statements if f'{label.lower()}_name_path' in s]}"
        )

    assert len(_name_path_statements(statements)) == len(POSITIONAL_IDENTITY_LABELS)


@pytest.mark.parametrize("backend", ["falkordb", "falkordb-remote"])
def test_falkordb_backends_do_not_create_name_path_indexes(backend):
    """FalkorDB derives per-attribute indexes from the composite indexes it
    already creates, and re-indexing an attribute raises an error there."""
    extra = _name_path_statements(_run_schema(backend))
    assert extra == [], f"expected no (name, path) indexes for {backend!r}, got: {extra}"


def test_name_path_indexes_are_idempotent():
    """Re-running the schema on an existing database must be a no-op.

    Real idempotence is Neo4j's IF NOT EXISTS; a recording session can only
    pin that the clause is present and that a second call emits the identical
    DDL without raising.
    """
    first = _name_path_statements(_run_schema("neo4j"))
    second = _name_path_statements(_run_schema("neo4j"))

    assert first == second
    for statement in first:
        assert "IF NOT EXISTS" in statement, statement


def test_name_path_property_set_differs_from_the_identity_constraint():
    """The whole point of the index is that its property set is SHORTER than
    the identity constraint's. If someone "tidies" it to match, Neo4j stops
    using it for (name, path) lookups and the label scans come back."""
    statements = _run_schema("neo4j")

    for statement in _name_path_statements(statements):
        assert "line_number" not in statement, statement
        assert "occurrence_index" not in statement, statement

    for label in POSITIONAL_IDENTITY_LABELS:
        identity = [
            s
            for s in statements
            if s.startswith(f"CREATE CONSTRAINT {label.lower()}_identity ")
        ]
        assert len(identity) == 1, f"no identity constraint for {label}: {identity}"
        assert "line_number" in identity[0] and "occurrence_index" in identity[0]
