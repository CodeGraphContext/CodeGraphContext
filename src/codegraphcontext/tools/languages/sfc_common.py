from pathlib import Path
from typing import Any, Dict, Type
import re

from codegraphcontext.utils.debug_log import warning_logger
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

from .javascript import JavascriptTreeSitterParser
from .typescript import TypescriptTreeSitterParser


_SCRIPT_TAG_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<content>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_LANG_TS_RE = re.compile(
    r"\blang\s*=\s*(?:\"|')?(?:ts|tsx|typescript)(?:\"|')?\b",
    re.IGNORECASE,
)
_LINE_FIELDS = {"line_number", "end_line", "function_line_number"}


class _ParserWrapper:
    """Lightweight wrapper to build language parsers outside GraphBuilder."""

    def __init__(self, language_name: str):
        manager = get_tree_sitter_manager()
        self.language_name = language_name
        self.language = manager.get_language_safe(language_name)
        self.parser = manager.create_parser(language_name)


def _extract_script_blocks(source_code: str) -> list[dict[str, Any]]:
    """Extract <script> blocks and metadata from SFC source text."""
    script_blocks = []

    for match in _SCRIPT_TAG_RE.finditer(source_code):
        attrs = match.group("attrs") or ""
        content = match.group("content") or ""

        script_blocks.append(
            {
                "content": content,
                "is_typescript": bool(_LANG_TS_RE.search(attrs)),
                # Count how many lines appear before the script body starts.
                "line_offset": source_code.count("\n", 0, match.start("content")),
            }
        )

    return script_blocks


def _apply_line_offset(value: Any, line_offset: int) -> None:
    """Recursively shift line-based fields by an offset."""
    if not line_offset:
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if key in _LINE_FIELDS and isinstance(item, int):
                value[key] = item + line_offset
            elif key == "context" and isinstance(item, tuple) and len(item) == 3 and isinstance(item[2], int):
                value[key] = (item[0], item[1], item[2] + line_offset)
            else:
                _apply_line_offset(item, line_offset)
    elif isinstance(value, list):
        for item in value:
            _apply_line_offset(item, line_offset)


class SingleFileComponentTreeSitterParser:
    """Shared parser for Vue/Svelte single-file components."""

    def __init__(self, generic_parser_wrapper, component_language: str):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = component_language

        self._javascript_parser = JavascriptTreeSitterParser(_ParserWrapper("javascript"))
        self._typescript_parser = TypescriptTreeSitterParser(_ParserWrapper("typescript"))

    def _parse_script_block(
        self,
        script_source: str,
        is_typescript: bool,
        index_source: bool,
    ) -> Dict[str, list[Dict[str, Any]]]:
        if is_typescript:
            parser = self._typescript_parser
            parser.index_source = index_source
            tree = parser.parser.parse(bytes(script_source, "utf8"))
            root = tree.root_node
            return {
                "functions": parser._find_functions(root),
                "classes": parser._find_classes(root),
                "interfaces": parser._find_interfaces(root),
                "type_aliases": parser._find_type_aliases(root),
                "variables": parser._find_variables(root),
                "imports": parser._find_imports(root),
                "function_calls": parser._find_calls(root),
            }

        parser = self._javascript_parser
        parser.index_source = index_source
        tree = parser.parser.parse(bytes(script_source, "utf8"))
        root = tree.root_node
        return {
            "functions": parser._find_functions(root),
            "classes": parser._find_classes(root),
            "variables": parser._find_variables(root),
            "imports": parser._find_imports(root),
            "function_calls": parser._find_calls(root),
        }

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()

        result: Dict[str, Any] = {
            "path": str(path),
            "functions": [],
            "classes": [],
            "interfaces": [],
            "type_aliases": [],
            "variables": [],
            "imports": [],
            "function_calls": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

        for block in _extract_script_blocks(source_code):
            parsed_block = self._parse_script_block(
                block["content"],
                is_typescript=block["is_typescript"],
                index_source=index_source,
            )
            _apply_line_offset(parsed_block, block["line_offset"])

            for key, values in parsed_block.items():
                if key not in result:
                    result[key] = []
                result[key].extend(values)

        return result


def pre_scan_sfc(
    files: list[Path],
    parser_wrapper,
    parser_cls: Type[SingleFileComponentTreeSitterParser],
) -> dict[str, list[str]]:
    """Generic pre-scan for SFC files, collecting symbols for import resolution."""
    imports_map: dict[str, list[str]] = {}
    parser = parser_cls(parser_wrapper)

    for path in files:
        try:
            file_data = parser.parse(path, is_dependency=False, index_source=False)

            for item_key in ("functions", "classes", "interfaces", "type_aliases"):
                for item in file_data.get(item_key, []):
                    name = item.get("name")
                    if not name:
                        continue

                    if name not in imports_map:
                        imports_map[name] = []

                    resolved_path = str(path.resolve())
                    if resolved_path not in imports_map[name]:
                        imports_map[name].append(resolved_path)
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")

    return imports_map
