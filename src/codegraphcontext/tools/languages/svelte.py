# src/codegraphcontext/tools/languages/svelte.py
"""Svelte single-file component (SFC) parser.

A ``.svelte`` file combines markup, scoped styles, and a ``<script>`` block.
This parser extracts the script block(s) and reuses the existing
JavaScript/TypeScript parsers for symbol extraction, remapping line numbers
back to the original ``.svelte`` file. See ``sfc_common`` for the mechanics.
"""

from pathlib import Path
from typing import Any, Dict

from .sfc_common import parse_sfc, pre_scan_sfc


class SvelteTreeSitterParser:
    """A parser for Svelte single-file components using tree-sitter."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.language_name = "svelte"

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parse a Svelte SFC and return symbols extracted from its script block(s)."""
        return parse_sfc(
            self.generic_parser_wrapper,
            path,
            sfc_lang=self.language_name,
            is_dependency=is_dependency,
            index_source=index_source,
        )


def pre_scan_svelte(files: list[Path], parser_wrapper) -> dict:
    """Pre-scan Svelte files, mapping script symbol names to their file paths."""
    return pre_scan_sfc(files, parser_wrapper, sfc_lang="svelte")
