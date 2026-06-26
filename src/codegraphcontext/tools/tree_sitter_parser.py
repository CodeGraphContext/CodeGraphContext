# src/codegraphcontext/tools/tree_sitter_parser.py
"""Tree-sitter parser dispatch by language name."""

from pathlib import Path
from importlib import import_module
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from tree_sitter import Language

from ..utils.tree_sitter_manager import LANGUAGE_ALIASES, get_tree_sitter_manager


LANGUAGE_PARSER_CLASSES = {
    "python": ("codegraphcontext.tools.languages.python", "PythonTreeSitterParser"),
    "javascript": ("codegraphcontext.tools.languages.javascript", "JavascriptTreeSitterParser"),
    "go": ("codegraphcontext.tools.languages.go", "GoTreeSitterParser"),
    "typescript": ("codegraphcontext.tools.languages.typescript", "TypescriptTreeSitterParser"),
    "tsx": ("codegraphcontext.tools.languages.typescriptjsx", "TypescriptJSXTreeSitterParser"),
    "cpp": ("codegraphcontext.tools.languages.cpp", "CppTreeSitterParser"),
    "rust": ("codegraphcontext.tools.languages.rust", "RustTreeSitterParser"),
    "c": ("codegraphcontext.tools.languages.c", "CTreeSitterParser"),
    "java": ("codegraphcontext.tools.languages.java", "JavaTreeSitterParser"),
    "ruby": ("codegraphcontext.tools.languages.ruby", "RubyTreeSitterParser"),
    "c_sharp": ("codegraphcontext.tools.languages.csharp", "CSharpTreeSitterParser"),
    "php": ("codegraphcontext.tools.languages.php", "PhpTreeSitterParser"),
    "lua": ("codegraphcontext.tools.languages.lua", "LuaTreeSitterParser"),
    "kotlin": ("codegraphcontext.tools.languages.kotlin", "KotlinTreeSitterParser"),
    "scala": ("codegraphcontext.tools.languages.scala", "ScalaTreeSitterParser"),
    "swift": ("codegraphcontext.tools.languages.swift", "SwiftTreeSitterParser"),
    "haskell": ("codegraphcontext.tools.languages.haskell", "HaskellTreeSitterParser"),
    "dart": ("codegraphcontext.tools.languages.dart", "DartTreeSitterParser"),
    "perl": ("codegraphcontext.tools.languages.perl", "PerlTreeSitterParser"),
    "elixir": ("codegraphcontext.tools.languages.elixir", "ElixirTreeSitterParser"),
    "elisp": ("codegraphcontext.tools.languages.elisp", "ElispTreeSitterParser"),
    "html": ("codegraphcontext.tools.languages.html", "HTMLTreeSitterParser"),
    "css": ("codegraphcontext.tools.languages.css", "CSSTreeSitterParser"),
}


class TreeSitterParser:
    """A generic parser wrapper for a specific language using tree-sitter."""

    def __init__(self, language_name: str):
        self.language_name = LANGUAGE_ALIASES.get(language_name.lower())
        if self.language_name not in LANGUAGE_PARSER_CLASSES:
            supported_languages = ", ".join(sorted(LANGUAGE_PARSER_CLASSES))
            raise ValueError(
                f"Unsupported language parser: {language_name}. "
                f"Supported languages: {supported_languages}"
            )

        self.ts_manager = get_tree_sitter_manager()

        self.language: "Language" = self.ts_manager.get_language_safe(language_name)
        self.parser = self.ts_manager.create_parser(language_name)

        module_name, class_name = LANGUAGE_PARSER_CLASSES[self.language_name]
        parser_class = getattr(import_module(module_name), class_name)
        self.language_specific_parser = parser_class(self)

    def parse(self, path: Path, is_dependency: bool = False, **kwargs) -> Dict:
        """Dispatches parsing to the language-specific parser."""
        if self.language_specific_parser:
            return self.language_specific_parser.parse(path, is_dependency, **kwargs)
        raise NotImplementedError(f"No language-specific parser implemented for {self.language_name}")
