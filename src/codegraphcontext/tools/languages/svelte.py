from pathlib import Path

from .sfc_common import SingleFileComponentTreeSitterParser, pre_scan_sfc


class SvelteTreeSitterParser(SingleFileComponentTreeSitterParser):
    """Tree-sitter parser for Svelte single-file components (.svelte)."""

    def __init__(self, generic_parser_wrapper):
        super().__init__(generic_parser_wrapper, component_language="svelte")


def pre_scan_svelte(files: list[Path], parser_wrapper) -> dict[str, list[str]]:
    """Pre-scan Svelte files for symbol-to-file import resolution."""
    return pre_scan_sfc(files, parser_wrapper, SvelteTreeSitterParser)
