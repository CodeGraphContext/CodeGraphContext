# src/codegraphcontext/tools/tree_sitter_parser.py
"""Tree-sitter parser dispatch by language name."""
import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language

from ..utils.tree_sitter_manager import get_tree_sitter_manager

_LANGUAGE_PARSER_MAP: dict[str, tuple[str, str]] = {
    "python":     (".languages.python",         "PythonTreeSitterParser"),
    "javascript": (".languages.javascript",     "JavascriptTreeSitterParser"),
    "go":         (".languages.go",              "GoTreeSitterParser"),
    "typescript": (".languages.typescript",      "TypescriptTreeSitterParser"),
    "tsx":        (".languages.typescriptjsx",   "TypescriptJSXTreeSitterParser"),
    "cpp":        (".languages.cpp",              "CppTreeSitterParser"),
    "rust":       (".languages.rust",             "RustTreeSitterParser"),
    "c":          (".languages.c",                "CTreeSitterParser"),
    "java":       (".languages.java",             "JavaTreeSitterParser"),
    "ruby":       (".languages.ruby",             "RubyTreeSitterParser"),
    "c_sharp":    (".languages.csharp",           "CSharpTreeSitterParser"),
    "php":        (".languages.php",              "PhpTreeSitterParser"),
    "lua":        (".languages.lua",              "LuaTreeSitterParser"),
    "kotlin":     (".languages.kotlin",           "KotlinTreeSitterParser"),
    "scala":      (".languages.scala",            "ScalaTreeSitterParser"),
    "swift":      (".languages.swift",            "SwiftTreeSitterParser"),
    "haskell":    (".languages.haskell",          "HaskellTreeSitterParser"),
    "dart":       (".languages.dart",              "DartTreeSitterParser"),
    "perl":       (".languages.perl",              "PerlTreeSitterParser"),
    "elixir":     (".languages.elixir",            "ElixirTreeSitterParser"),
    "elisp":      (".languages.elisp",             "ElispTreeSitterParser"),
    "html":       (".languages.html",              "HTMLTreeSitterParser"),
    "css":        (".languages.css",               "CSSTreeSitterParser"),
}

class TreeSitterParser:
    """A generic parser wrapper for a specific language using tree-sitter."""

    def __init__(self, language_name: str):
        self.language_name = language_name
        self.ts_manager = get_tree_sitter_manager()

        self.language: "Language" = self.ts_manager.get_language_safe(language_name)
        self.parser = self.ts_manager.create_parser(language_name)

        self.language_specific_parser = self._build_language_parser(language_name)

    def _build_language_parser(self, language_name: str):
        entry = _LANGUAGE_PARSER_MAP.get(language_name)
        if entry is None:
            # If the language is not known, raise an error with a message that includes the known languages.
            raise ValueError(
                f"No tree-sitter parser known for language "
                f"'{language_name}'. Known languages: "
                f"{sorted(_LANGUAGE_PARSER_MAP)}"
            )

        module_path, class_name = entry
        # only the module for the language actually being parsed gets imported.
        module = importlib.import_module(module_path, package=__package__)
        parser_cls = getattr(module, class_name)
        return parser_cls(self)
