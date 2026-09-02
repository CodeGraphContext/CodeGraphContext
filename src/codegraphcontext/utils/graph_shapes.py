"""Backend-agnostic classification of values returned by a graph driver.

CodeGraphContext renders the same graph through two independent paths — the
offline renderer in ``cli/cli_helpers.py`` and the live web server in
``viz/server.py``. Each supported backend hands back a different shape, so both
paths need to answer the same question: *is this value a node or a
relationship?*

Until now each path answered it separately, and they drifted:

* ``cli_helpers`` classified by **duck typing** (does the value expose
  ``.labels``? ``.relation``/``.src_node``?), which covers any driver.
* ``viz/server`` classified by **class name**, matching only
  ``Node``/``KuzuNode`` and ``Relationship``/``KuzuRelationship``.

FalkorDB's edge class is named ``Edge``, so it matched neither branch in the
server path and every FalkorDB relationship was silently discarded — on the
backend that is CGC's *default* on Unix under Python 3.12+. The server's own
``parse_rel`` already knew how to read a FalkorDB edge; it was simply never
reached.

Both paths now share the predicates below, so *classification* cannot drift
apart again. Id and property extraction are still duplicated between
``viz/server.parse_node``/``parse_rel`` and ``cli_helpers``' payload builders —
consolidating those is deliberately left out of this change.

Shapes, confirmed by querying each backend's real Python package:

``neo4j``
    ``Node`` carries ``.labels`` and is dict-convertible via the Mapping
    protocol. ``Relationship`` carries ``.type`` plus ``.start_node`` /
    ``.end_node`` (full ``Node`` objects).

``falkordb``
    ``Node`` carries ``.labels`` but is **not** dict-convertible — properties
    live in a plain ``.properties`` dict. ``Edge`` carries ``.relation`` plus
    ``.src_node`` / ``.dest_node``, which hold the bare integer node ids, and
    exposes no ``.labels`` and no ``.type``.

``kuzu`` / ``ladybug``
    Plain dicts. Nodes carry ``_id`` / ``_label``; relationships carry
    ``_src`` / ``_dst`` / ``_label``. Kùzu spells these keys lowercase and
    Ladybug spells the identical fields uppercase (``_ID`` / ``_LABEL`` /
    ``_SRC`` / ``_DST``), so every lookup here accepts either casing.
"""

from typing import Any

__all__ = ["has_meta", "meta", "is_node", "is_relationship"]


def has_meta(record: dict, key: str) -> bool:
    """True if ``record`` carries ``key`` in either Kùzu or Ladybug casing."""
    return key in record or key.upper() in record


def meta(record: dict, key: str, default: Any = None) -> Any:
    """Read an internal ``_``-prefixed field regardless of its casing."""
    if key in record:
        return record[key]
    return record.get(key.upper(), default)


def _is_driver_relationship(value: Any) -> bool:
    """True for a driver object that looks like a relationship.

    Neo4j exposes ``.type``; FalkorDB exposes ``.relation`` alongside
    ``.src_node``. Both are checked because neither driver implements the
    other's attribute.
    """
    if hasattr(value, "type"):
        return True
    return hasattr(value, "relation") and hasattr(value, "src_node")


def is_relationship(value: Any) -> bool:
    """True if ``value`` is a relationship from any supported backend."""
    # ``.labels`` is the unambiguous node marker across every driver, so it
    # settles the question before the relationship checks run.
    if hasattr(value, "labels"):
        return False
    if _is_driver_relationship(value):
        return True
    if isinstance(value, dict):
        # Kùzu and Ladybug relationships also carry ``_label``, so the
        # endpoints are what distinguish them from nodes.
        if has_meta(value, "_src") and has_meta(value, "_dst"):
            return True
        # A FalkorDB result mapped into a plain dict keeps the driver's
        # endpoint names.
        return "src_node" in value and "dest_node" in value
    return False


def _has_endpoint_marker(record: dict) -> bool:
    """True if a dict carries any relationship-endpoint field.

    A half-formed relationship — say ``_src`` present but ``_dst`` missing —
    is not a usable relationship, but it must not be mistaken for a node
    either: it also carries ``_label``, so a plain label check would turn it
    into a phantom node with a relationship's id. Values like that are
    classified as neither and skipped, which is what the offline renderer has
    always done.
    """
    return (
        has_meta(record, "_src")
        or has_meta(record, "_dst")
        or "src_node" in record
        or "dest_node" in record
    )


def is_node(value: Any) -> bool:
    """True if ``value`` is a node from any supported backend."""
    if hasattr(value, "labels"):
        return True
    if _is_driver_relationship(value):
        return False
    if isinstance(value, dict):
        if _has_endpoint_marker(value):
            return False
        return has_meta(value, "_label") or "labels" in value
    return False
