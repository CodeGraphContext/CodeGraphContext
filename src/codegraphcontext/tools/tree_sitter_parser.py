# src/codegraphcontext/tools/tree_sitter_parser.py
"""Tree-sitter parser dispatch by language name."""

from pathlib import Path
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from tree_sitter import Language

from ..utils.tree_sitter_manager import get_tree_sitter_manager


class TreeSitterParser:
    """A generic parser wrapper for a specific language using tree-sitter."""

    def __init__(self, language_name: str):
        self.language_name = language_name
        self.ts_manager = get_tree_sitter_manager()

        self.language: "Language" = self.ts_manager.get_language_safe(language_name)
        self.parser = self.ts_manager.create_parser(language_name)

        LANGUAGE_PARSER_MAP = {
            "python":     (".languages.python",        "PythonTreeSitterParser"),
            "javascript": (".languages.javascript",    "JavascriptTreeSitterParser"),
            "go":         (".languages.go",            "GoTreeSitterParser"),
            "typescript": (".languages.typescript",    "TypescriptTreeSitterParser"),
            "tsx":        (".languages.typescriptjsx", "TypescriptJSXTreeSitterParser"),
            "cpp":        (".languages.cpp",           "CppTreeSitterParser"),
            "rust":       (".languages.rust",          "RustTreeSitterParser"),
            "c":          (".languages.c",             "CTreeSitterParser"),
            "java":       (".languages.java",          "JavaTreeSitterParser"),
            "ruby":       (".languages.ruby",          "RubyTreeSitterParser"),
            "c_sharp":    (".languages.csharp",        "CSharpTreeSitterParser"),
            "php":        (".languages.php",           "PhpTreeSitterParser"),
            "lua":        (".languages.lua",           "LuaTreeSitterParser"),
            "kotlin":     (".languages.kotlin",        "KotlinTreeSitterParser"),
            "scala":      (".languages.scala",         "ScalaTreeSitterParser"),
            "swift":      (".languages.swift",         "SwiftTreeSitterParser"),
            "haskell":    (".languages.haskell",       "HaskellTreeSitterParser"),
            "dart":       (".languages.dart",          "DartTreeSitterParser"),
            "perl":       (".languages.perl",          "PerlTreeSitterParser"),
            "elixir":     (".languages.elixir",        "ElixirTreeSitterParser"),
            "elisp":      (".languages.elisp",         "ElispTreeSitterParser"),
            "html":       (".languages.html",          "HTMLTreeSitterParser"),
            "css":        (".languages.css",           "CSSTreeSitterParser"),
            "svelte":     (".languages.svelte",        "SvelteTreeSitterParser"),
            "vue":        (".languages.vue",           "VueTreeSitterParser"),
            "solidity":   (".languages.solidity",      "SolidityTreeSitterParser"),
        }

        if language_name not in LANGUAGE_PARSER_MAP:
            supported = ", ".join(sorted(LANGUAGE_PARSER_MAP.keys()))
            raise ValueError(
                f"Invalid language name: '{language_name}'. "
                f"Supported languages are: {supported}"
            )

        module_path, class_name = LANGUAGE_PARSER_MAP[language_name]
        module = __import__(
            f"{__package__}{module_path}".replace("/", "."),
            fromlist=[class_name]
        )
        parser_class = getattr(module, class_name)
        self.language_specific_parser = parser_class(self)

    def parse(self, path: Path, is_dependency: bool = False, **kwargs) -> Dict:
        """Dispatches parsing to the language-specific parser."""
        return self.language_specific_parser.parse(path, is_dependency, **kwargs)
