# src/codegraphcontext/tools/languages/sfc_common.py
"""Shared helpers for Vue and Svelte single-file component (SFC) parsers.

Vue and Svelte files mix template markup, scoped styles, and one or more
``<script>`` blocks. Rather than re-implementing symbol extraction for these
formats, the SFC parsers locate the ``<script>`` block(s) and delegate to the
existing JavaScript/TypeScript parsers. Line numbers reported by the delegated
parser are remapped so they point back to the original SFC file.

The remapping is done by feeding the delegated parser a temporary file whose
script content is padded with leading blank lines equal to the script block's
starting row. Because every tree-sitter line number is derived from the node's
``start_point``, this padding makes the delegated parser emit line numbers that
already match the original SFC without any per-symbol arithmetic.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

# Attribute values that mark a script block as TypeScript.
_TS_SCRIPT_LANGS = {"ts", "typescript"}


def _get_node_text(node) -> str:
    return node.text.decode("utf-8")


def _find_script_blocks(root_node) -> List[Any]:
    """Return all ``script_element`` nodes in document order.

    Both the Vue and Svelte grammars expose script blocks as ``script_element``
    nodes containing a ``start_tag``, a ``raw_text`` body, and an ``end_tag``.
    """
    blocks = []
    stack = [root_node]
    while stack:
        node = stack.pop()
        if node.type == "script_element":
            blocks.append(node)
            continue
        # Script blocks are top-level in an SFC, so we only need shallow recursion,
        # but walking children keeps this robust to grammar nesting differences.
        stack.extend(reversed(node.children))
    return blocks


def _script_lang(script_element) -> str:
    """Detect the script language ('typescript' or 'javascript') from ``lang=``."""
    start_tag = next(
        (c for c in script_element.children if c.type == "start_tag"), None
    )
    if start_tag is None:
        return "javascript"
    for child in start_tag.children:
        if child.type != "attribute":
            continue
        name_node = next(
            (c for c in child.children if c.type == "attribute_name"), None
        )
        if name_node is None or _get_node_text(name_node).lower() != "lang":
            continue
        value_node = next(
            (
                c
                for c in child.children
                if c.type in ("quoted_attribute_value", "attribute_value")
            ),
            None,
        )
        if value_node is None:
            continue
        value = _get_node_text(value_node).strip().strip("\"'").lower()
        if value in _TS_SCRIPT_LANGS:
            return "typescript"
        return "javascript"
    return "javascript"


def _script_content_and_offset(script_element) -> Optional[Tuple[str, int]]:
    """Return ``(script_source, start_row)`` for a script block, or ``None``.

    ``start_row`` is the 0-based row at which the script body starts, used to
    pad the delegated source so reported line numbers match the original SFC.
    """
    raw_text = next(
        (c for c in script_element.children if c.type == "raw_text"), None
    )
    if raw_text is None:
        return None
    content = _get_node_text(raw_text)
    if not content.strip():
        return None
    return content, raw_text.start_point[0]


def _build_delegate_parser(language_name: str):
    """Instantiate the JS/TS language-specific parser for the script block."""
    manager = get_tree_sitter_manager()

    class _Wrapper:
        pass

    wrapper = _Wrapper()
    wrapper.language_name = language_name
    wrapper.language = manager.get_language_safe(language_name)
    wrapper.parser = manager.create_parser(language_name)

    if language_name == "typescript":
        from .typescript import TypescriptTreeSitterParser

        return TypescriptTreeSitterParser(wrapper)
    from .javascript import JavascriptTreeSitterParser

    return JavascriptTreeSitterParser(wrapper)


def _parse_script_block(
    content: str, start_row: int, script_lang: str, original_path: Path, **kwargs
) -> Dict[str, Any]:
    """Parse one script block and return its delegated parser result.

    The script content is padded with ``start_row`` leading newlines and written
    to a temporary file so the delegated JS/TS parser emits line numbers that
    already line up with the original SFC.
    """
    delegate = _build_delegate_parser(script_lang)

    padded = ("\n" * start_row) + content
    tmp_path = None
    try:
        suffix = ".ts" if script_lang == "typescript" else ".js"
        fd, tmp_name = tempfile.mkstemp(suffix=suffix, prefix="cgc_sfc_")
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(padded)
        result = delegate.parse(tmp_path, **kwargs)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    # Repoint every emitted record at the original SFC file.
    result["path"] = str(original_path)
    for bucket in ("functions", "classes", "variables", "imports", "function_calls"):
        for item in result.get(bucket, []):
            if isinstance(item, dict) and "file_path" in item:
                item["file_path"] = str(original_path)
    return result


def parse_sfc(
    parser_wrapper,
    path: Path,
    sfc_lang: str,
    is_dependency: bool = False,
    index_source: bool = False,
) -> Dict[str, Any]:
    """Parse a Vue/Svelte SFC and return symbols extracted from its scripts.

    Parameters
    ----------
    parser_wrapper:
        The ``TreeSitterParser`` wrapper for the SFC language (``svelte``/``vue``).
    path:
        Path to the ``.svelte`` / ``.vue`` file.
    sfc_lang:
        Canonical SFC language name reported in the result (``"svelte"``/``"vue"``).
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        source_code = f.read()

    tree = parser_wrapper.parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    aggregate: Dict[str, Any] = {
        "path": str(path),
        "functions": [],
        "classes": [],
        "variables": [],
        "imports": [],
        "function_calls": [],
        "is_dependency": is_dependency,
        "lang": sfc_lang,
    }

    # Buckets that are metadata, not symbol lists, must not be merged.
    _NON_LIST_KEYS = {"path", "is_dependency", "lang"}

    for script_element in _find_script_blocks(root_node):
        extracted = _script_content_and_offset(script_element)
        if extracted is None:
            continue
        content, start_row = extracted
        script_lang = _script_lang(script_element)
        result = _parse_script_block(
            content,
            start_row,
            script_lang,
            path,
            is_dependency=is_dependency,
            index_source=index_source,
        )
        # Forward every list-valued bucket the delegated parser produced. This
        # preserves TypeScript-only buckets such as ``interfaces`` and
        # ``type_aliases`` (and ``components`` from the JS parser) without the
        # SFC parser needing to know each delegate's full output shape.
        for bucket, value in result.items():
            if bucket in _NON_LIST_KEYS or not isinstance(value, list):
                continue
            aggregate.setdefault(bucket, []).extend(value)

    return aggregate


def pre_scan_sfc(files: list[Path], parser_wrapper, sfc_lang: str) -> dict:
    """Pre-scan SFC files, mapping top-level script symbol names to file paths.

    Mirrors the language pre-scan contract used by the indexing pipeline so that
    cross-file symbol resolution works for SFC script blocks.
    """
    imports_map: dict = {}
    for file_path in files:
        try:
            result = parse_sfc(parser_wrapper, file_path, sfc_lang)
        except Exception:
            continue
        for bucket in ("functions", "classes", "variables", "interfaces", "type_aliases"):
            for item in result.get(bucket, []):
                name = item.get("name")
                if name:
                    imports_map.setdefault(name, []).append(str(file_path.resolve()))
    return imports_map
