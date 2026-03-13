from pathlib import Path

from .sfc_common import SingleFileComponentTreeSitterParser, pre_scan_sfc


class VueTreeSitterParser(SingleFileComponentTreeSitterParser):
    """Tree-sitter parser for Vue single-file components (.vue)."""

    def __init__(self, generic_parser_wrapper):
        super().__init__(generic_parser_wrapper, component_language="vue")


def pre_scan_vue(files: list[Path], parser_wrapper) -> dict[str, list[str]]:
    """Pre-scan Vue files for symbol-to-file import resolution."""
    return pre_scan_sfc(files, parser_wrapper, VueTreeSitterParser)
