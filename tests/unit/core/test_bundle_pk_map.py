"""_PK_MAP must cover every node table Kùzu declares (see issue #1322).

Kùzu/Ladybug reject a bare `CREATE (n:Label)` with
"Create node n expects primary key <field> as input", so a label missing from
_PK_MAP does not degrade — its import fails outright.
"""

import re
from pathlib import Path

import pytest

from codegraphcontext.core.cgc_bundle import CGCBundle

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "codegraphcontext"
    / "core"
    / "database_embedded_kuzu.py"
)


def _declared_node_tables() -> dict:
    """Parse (label -> pk field tuple) out of the Kùzu node_tables block."""
    source = SCHEMA_PATH.read_text(encoding="utf-8")
    block = source.split("node_tables = [", 1)[1].split("\n        ]", 1)[0]

    tables = {}
    for label, body in re.findall(r'\("(\w+)",\s*"([^"]+)"\)', block):
        match = re.search(r"PRIMARY KEY \(([^)]+)\)", body)
        if match:
            tables[label] = tuple(f.strip() for f in match.group(1).split(","))
    return tables


def test_schema_parse_found_the_tables():
    """Guard the parser itself — a silent empty parse would pass everything."""
    tables = _declared_node_tables()
    assert len(tables) > 20, f"only parsed {len(tables)} node tables"
    assert tables["Repository"] == ("path",)
    assert tables["DbColumn"] == ("name", "table_fqn")


def test_every_kuzu_node_table_has_a_pk_map_entry():
    tables = _declared_node_tables()
    missing = sorted(set(tables) - set(CGCBundle._PK_MAP))
    assert not missing, (
        "node labels declared in the Kùzu schema but absent from _PK_MAP "
        f"(their bundle import will fail): {missing}"
    )


def test_pk_map_fields_match_the_declared_primary_keys():
    tables = _declared_node_tables()
    mismatched = {
        label: {"schema": pk, "pk_map": CGCBundle._PK_MAP[label]}
        for label, pk in tables.items()
        if label in CGCBundle._PK_MAP and CGCBundle._PK_MAP[label] != pk
    }
    assert not mismatched, f"_PK_MAP disagrees with the schema: {mismatched}"


def test_pk_map_has_no_labels_the_schema_does_not_declare():
    tables = _declared_node_tables()
    extra = sorted(set(CGCBundle._PK_MAP) - set(tables))
    assert not extra, f"_PK_MAP entries with no matching node table: {extra}"


@pytest.mark.parametrize(
    "label,expected",
    [
        ("DbTable", ("name",)),
        ("ExternalClass", ("name",)),
        ("DbColumn", ("name", "table_fqn")),
        ("RedisKeyPattern", ("pattern", "datasource_name")),
        ("EnumMember", ("uid",)),
        ("Mixin", ("uid",)),
        ("Extension", ("uid",)),
        ("Object", ("uid",)),
        ("Datasource", ("name",)),
    ],
)
def test_labels_reported_in_1322_are_now_mapped(label, expected):
    assert CGCBundle._pk_fields(label) == expected


def test_unknown_label_reports_no_pk_fields():
    assert CGCBundle._pk_fields("NotARealLabel") == ()


def test_composite_key_lookup_carries_every_field():
    """Edge matching must keep both halves of a composite key."""
    bundle = object.__new__(CGCBundle)
    key = bundle._node_lookup_key(
        ["DbColumn"], {"name": "id", "table_fqn": "db.users", "type": "INT"}
    )

    assert key == ("DbColumn", (("name", "id"), ("table_fqn", "db.users")))


def test_lookup_is_none_when_a_composite_field_is_absent():
    bundle = object.__new__(CGCBundle)

    assert bundle._node_lookup_key(["DbColumn"], {"name": "id"}) is None
