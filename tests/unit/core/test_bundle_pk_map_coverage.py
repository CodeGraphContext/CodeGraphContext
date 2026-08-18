"""
Regression tests for #1322 — `_PK_MAP` must cover the declared node tables.

A label absent from `_PK_MAP` does not degrade gracefully. `_import_node_batch`
falls through to `CREATE (n:Label) SET n = $props`, and Kùzu rejects that with
"Create node n expects primary key <field> as input", so importing any bundle
containing that label fails outright.

The coverage test derives its expectations from the schema itself, so adding a
node table without teaching the importer about it fails here rather than in a
user's bundle import.
"""
import re
from pathlib import Path

import pytest

from codegraphcontext.core.cgc_bundle import CGCBundle

SCHEMA_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "codegraphcontext" / "core" / "database_embedded_kuzu.py"
)

# Composite primary keys no longer exist in the Kùzu schema: Kùzu cannot
# declare them at all (the DDL fails to parse), so DbColumn and RedisKeyPattern
# are keyed on a synthesized uid like the positional code labels. Kept as an
# empty set so a future composite key re-fails this test loudly.
KNOWN_COMPOSITE_PK_LABELS = set()


def declared_node_tables():
    """(label, primary-key-fields) for every node table in the Kùzu schema."""
    text = SCHEMA_FILE.read_text()
    found = re.findall(r'\("(\w+)",\s*"[^"]*PRIMARY KEY \(([^)]+)\)"', text)
    assert found, "could not parse any node tables out of the Kùzu schema"
    return [(label, [f.strip() for f in keys.split(",")]) for label, keys in found]


@pytest.mark.parametrize(
    "label,pk_fields",
    [(l, k) for l, k in declared_node_tables() if l not in KNOWN_COMPOSITE_PK_LABELS],
)
def test_single_key_label_is_mapped(label, pk_fields):
    """Every single-PK node table must be importable."""
    assert len(pk_fields) == 1, (
        f"{label} has a composite PK; add it to KNOWN_COMPOSITE_PK_LABELS "
        f"or teach _PK_MAP about composite keys"
    )
    assert label in CGCBundle._PK_MAP, (
        f"{label} is a declared node table but missing from _PK_MAP; "
        f"importing a bundle containing it would fail"
    )
    assert CGCBundle._PK_MAP[label] == pk_fields[0], (
        f"{label} PK mismatch: schema says {pk_fields[0]!r}, "
        f"_PK_MAP says {CGCBundle._PK_MAP[label]!r}"
    )


def test_labels_reported_in_1322_are_mapped():
    """The two labels named in the issue report, pinned explicitly.

    DbTable moved from name to fqn: the writer merges DbTable on `fqn`
    (names collide across datasources), and the Kùzu table is keyed
    accordingly, so bundles must import it by fqn too.
    """
    assert CGCBundle._PK_MAP.get("DbTable") == "fqn"
    assert CGCBundle._PK_MAP.get("ExternalClass") == "name"


def test_uid_labels_can_derive_a_uid():
    """A 'uid' PK is synthesised from _UID_PARTS, so those parts must exist."""
    for label, field in CGCBundle._PK_MAP.items():
        if field == "uid":
            assert CGCBundle._UID_PARTS.get(label), (
                f"{label} uses a uid primary key but has no _UID_PARTS entry, "
                f"so its uid would be the empty string and all such nodes "
                f"would collapse onto one"
            )
