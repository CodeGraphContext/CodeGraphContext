# src/codegraphcontext/tools/tree_sitter_parser.py
"""Tree-sitter parser dispatch by language name."""

from pathlib import Path
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from tree_sitter import Language

from ..utils.tree_sitter_manager import get_tree_sitter_manager

LANGUAGE_PARSERS = {
    "python": lambda self: __import__("src.codegraphcontext.tools.languages.python", fromlist=["PythonTreeSitterParser"]).PythonTreeSitterParser(self),
    "javascript": lambda self: __import__("src.codegraphcontext.tools.languages.javascript", fromlist=["JavascriptTreeSitterParser"]).JavascriptTreeSitterParser(self),
    "go": lambda self: __import__("src.codegraphcontext.tools.languages.go", fromlist=["GoTreeSitterParser"]).GoTreeSitterParser(self),
    "typescript": lambda self: __import__("src.codegraphcontext.tools.languages.typescript", fromlist=["TypescriptTreeSitterParser"]).TypescriptTreeSitterParser(self),
    "tsx": lambda self: __import__("src.codegraphcontext.tools.languages.typescriptjsx", fromlist=["TypescriptJSXTreeSitterParser"]).TypescriptJSXTreeSitterParser(self),
    "cpp": lambda self: __import__("src.codegraphcontext.tools.languages.cpp", fromlist=["CppTreeSitterParser"]).CppTreeSitterParser(self),
    "rust": lambda self: __import__("src.codegraphcontext.tools.languages.rust", fromlist=["RustTreeSitterParser"]).RustTreeSitterParser(self),
    "c": lambda self: __import__("src.codegraphcontext.tools.languages.c", fromlist=["CTreeSitterParser"]).CTreeSitterParser(self),
    "java": lambda self: __import__("src.codegraphcontext.tools.languages.java", fromlist=["JavaTreeSitterParser"]).JavaTreeSitterParser(self),
    "ruby": lambda self: __import__("src.codegraphcontext.tools.languages.ruby", fromlist=["RubyTreeSitterParser"]).RubyTreeSitterParser(self),
    "c_sharp": lambda self: __import__("src.codegraphcontext.tools.languages.csharp", fromlist=["CSharpTreeSitterParser"]).CSharpTreeSitterParser(self),
    "php": lambda self: __import__("src.codegraphcontext.tools.languages.php", fromlist=["PhpTreeSitterParser"]).PhpTreeSitterParser(self),
    "lua": lambda self: __import__("src.codegraphcontext.tools.languages.lua", fromlist=["LuaTreeSitterParser"]).LuaTreeSitterParser(self),
    "kotlin": lambda self: __import__("src.codegraphcontext.tools.languages.kotlin", fromlist=["KotlinTreeSitterParser"]).KotlinTreeSitterParser(self),
    "scala": lambda self: __import__("src.codegraphcontext.tools.languages.scala", fromlist=["ScalaTreeSitterParser"]).ScalaTreeSitterParser(self),
    "swift": lambda self: __import__("src.codegraphcontext.tools.languages.swift", fromlist=["SwiftTreeSitterParser"]).SwiftTreeSitterParser(self),
    "haskell": lambda self: __import__("src.codegraphcontext.tools.languages.haskell", fromlist=["HaskellTreeSitterParser"]).HaskellTreeSitterParser(self),
    "dart": lambda self: __import__("src.codegraphcontext.tools.languages.dart", fromlist=["DartTreeSitterParser"]).DartTreeSitterParser(self),
    "perl": lambda self: __import__("src.codegraphcontext.tools.languages.perl", fromlist=["PerlTreeSitterParser"]).PerlTreeSitterParser(self),
    "elixir": lambda self: __import__("src.codegraphcontext.tools.languages.elixir", fromlist=["ElixirTreeSitterParser"]).ElixirTreeSitterParser(self),
    "elisp": lambda self: __import__("src.codegraphcontext.tools.languages.elisp", fromlist=["ElispTreeSitterParser"]).ElispTreeSitterParser(self),
    "html": lambda self: __import__("src.codegraphcontext.tools.languages.html", fromlist=["HTMLTreeSitterParser"]).HTMLTreeSitterParser(self),
    "css": lambda self: __import__("src.codegraphcontext.tools.languages.css", fromlist=["CSSTreeSitterParser"]).CSSTreeSitterParser(self),
}


class TreeSitterParser:
    """A generic parser wrapper for a specific language using tree-sitter."""

    def __init__(self, language_name: str):
        self.language_name = language_name
        self.ts_manager = get_tree_sitter_manager()

        try:
           self.language_specific_parser = LANGUAGE_PARSERS[self.language_name](self)
        except KeyError:
         raise ValueError(f"Invalid language name: {self.language_name}")




    def parse(self, path: Path, is_dependency: bool = False, **kwargs) -> Dict:
        """Dispatches parsing to the language-specific parser."""
        if self.language_specific_parser:
            return self.language_specific_parser.parse(path, is_dependency, **kwargs)
        raise NotImplementedError(f"No language-specific parser implemented for {self.language_name}")
