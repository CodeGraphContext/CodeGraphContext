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

        self.language_specific_parser = None
        if self.language_name == "python":
            from .languages.python import PythonTreeSitterParser

            self.language_specific_parser = PythonTreeSitterParser(self)
        elif self.language_name == "javascript":
            from .languages.javascript import JavascriptTreeSitterParser

            self.language_specific_parser = JavascriptTreeSitterParser(self)
        elif self.language_name == "go":
            from .languages.go import GoTreeSitterParser

            self.language_specific_parser = GoTreeSitterParser(self)
        elif self.language_name == "typescript":
            from .languages.typescript import TypescriptTreeSitterParser

            self.language_specific_parser = TypescriptTreeSitterParser(self)
        elif self.language_name == "tsx":
            from .languages.typescriptjsx import TypescriptJSXTreeSitterParser

            self.language_specific_parser = TypescriptJSXTreeSitterParser(self)
        elif self.language_name == "cpp":
            from .languages.cpp import CppTreeSitterParser

            self.language_specific_parser = CppTreeSitterParser(self)
        elif self.language_name == "rust":
            from .languages.rust import RustTreeSitterParser

            self.language_specific_parser = RustTreeSitterParser(self)
        elif self.language_name == "c":
            from .languages.c import CTreeSitterParser

            self.language_specific_parser = CTreeSitterParser(self)
        elif self.language_name == "java":
            from .languages.java import JavaTreeSitterParser

            self.language_specific_parser = JavaTreeSitterParser(self)
        elif self.language_name == "ruby":
            from .languages.ruby import RubyTreeSitterParser

            self.language_specific_parser = RubyTreeSitterParser(self)
        elif self.language_name == "c_sharp":
            from .languages.csharp import CSharpTreeSitterParser

            self.language_specific_parser = CSharpTreeSitterParser(self)
        elif self.language_name == "php":
            from .languages.php import PhpTreeSitterParser

            self.language_specific_parser = PhpTreeSitterParser(self)
        elif self.language_name == "lua":
            from .languages.lua import LuaTreeSitterParser

            self.language_specific_parser = LuaTreeSitterParser(self)
        elif self.language_name == "kotlin":
            from .languages.kotlin import KotlinTreeSitterParser

            self.language_specific_parser = KotlinTreeSitterParser(self)
        elif self.language_name == "scala":
            from .languages.scala import ScalaTreeSitterParser

            self.language_specific_parser = ScalaTreeSitterParser(self)
        elif self.language_name == "swift":
            from .languages.swift import SwiftTreeSitterParser

            self.language_specific_parser = SwiftTreeSitterParser(self)
        elif self.language_name == "haskell":
            from .languages.haskell import HaskellTreeSitterParser

            self.language_specific_parser = HaskellTreeSitterParser(self)
        elif self.language_name == "dart":
            from .languages.dart import DartTreeSitterParser

            self.language_specific_parser = DartTreeSitterParser(self)
        elif self.language_name == "perl":
            from .languages.perl import PerlTreeSitterParser

            self.language_specific_parser = PerlTreeSitterParser(self)
        elif self.language_name == "elixir":
            from .languages.elixir import ElixirTreeSitterParser

            self.language_specific_parser = ElixirTreeSitterParser(self)
        elif self.language_name == "html":
            from .languages.html import HTMLTreeSitterParser

            self.language_specific_parser = HTMLTreeSitterParser(self)
        elif self.language_name == "css":
            from .languages.css import CSSTreeSitterParser

            self.language_specific_parser = CSSTreeSitterParser(self)

    def parse(self, path: Path, is_dependency: bool = False, **kwargs) -> Dict:
        """Dispatches parsing to the language-specific parser."""
        if self.language_specific_parser:
            return self.language_specific_parser.parse(path, is_dependency, **kwargs)
        raise NotImplementedError(f"No language-specific parser implemented for {self.language_name}")
