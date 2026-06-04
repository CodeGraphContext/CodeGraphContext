# src/codegraphcontext/tools/type_utils.py
"""Shared type-name normalization helpers for parser and resolver heuristics."""


def strip_type_modifiers(type_str: str) -> str:
    """Return the resolvable base type, e.g. 'List<T>?' -> 'List'."""
    stripped = type_str.strip()
    while stripped.endswith("?"):
        stripped = stripped[:-1].strip()
    bracket = stripped.find("<")
    if bracket != -1:
        stripped = stripped[:bracket].strip()
    return stripped
