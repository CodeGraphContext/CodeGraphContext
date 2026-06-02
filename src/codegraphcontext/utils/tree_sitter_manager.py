# src/codegraphcontext/utils/tree_sitter_manager.py
"""
Tree-sitter language and parser management module.

This module provides thread-safe, cached access to tree-sitter languages and parsers.
It handles the migration from tree-sitter-languages to tree-sitter-language-pack.

Key design principles:
1. Cache languages, not parsers (parsers are NOT thread-safe)
2. Handle language name aliasing
3. Provide clear error messages for missing languages
4. Support optional tree-sitter dependency
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
import threading
import sys

if TYPE_CHECKING:
    from tree_sitter import Language, Parser

Language = Any
Parser = Any
_tree_sitter_import_error: Optional[ImportError] = None
_Language = None
_Parser = None
_get_language = None


def _missing_tree_sitter_error(import_error: ImportError) -> ImportError:
    """Return an actionable error for optional tree-sitter dependencies."""
    if sys.version_info >= (3, 13):
        return ImportError(
            "Tree-sitter parsing is not available on Python 3.13 because "
            "tree-sitter-language-pack does not publish cp313 wheels. "
            "Install CodeGraphContext with Python 3.12 or 3.14 to use indexing/parsing."
        )
    return ImportError(
        "tree-sitter and tree-sitter-language-pack are required for code parsing. "
        "Install them with: pip install codegraphcontext[parsing]"
    )


def _load_tree_sitter_dependencies():
    """Load optional tree-sitter dependencies only when parsing is used."""
    global _tree_sitter_import_error, _Language, _Parser, _get_language

    if _Language is not None and _Parser is not None and _get_language is not None:
        return _Language, _Parser, _get_language

    try:
        from tree_sitter import Language as ImportedLanguage, Parser as ImportedParser
        try:
            from tree_sitter_language_pack import get_language as imported_get_language
            # Test it immediately using a version-agnostic pattern
            test_lang = imported_get_language('python')
            try:
                # 0.22+ style
                test_parser = ImportedParser(test_lang)
            except (TypeError, ValueError):
                # < 0.22 style
                test_parser = ImportedParser()
                test_parser.set_language(test_lang)
        except (ImportError, Exception):
            # Fallback to tree_sitter_languages
            from tree_sitter_languages import get_language as imported_get_language
    except ImportError as e:
        _tree_sitter_import_error = e
        raise _missing_tree_sitter_error(e) from e

    _Language = ImportedLanguage
    _Parser = ImportedParser
    _get_language = imported_get_language
    return _Language, _Parser, _get_language


# Language name aliases for compatibility
LANGUAGE_ALIASES = {
    # Common aliases
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "c++": "cpp",
    "c#": "c_sharp",
    "csharp": "c_sharp",
    "cs": "c_sharp",
    "rb": "ruby",
    "rs": "rust",
    "go": "go",
    "php": "php",
    ".php": "php",
    "lua": "lua",
    
    # Canonical names (map to themselves for consistency)
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "cpp": "cpp",
    "c_sharp": "c_sharp",
    "c": "c",
    "java": "java",
    "haskell": "haskell",
    "ruby": "ruby",
    "rust": "rust",
    "kt": "kotlin",
    "kotlin": "kotlin",
    "scala": "scala",
    ".scala": "scala",
    "swift": "swift",
    ".swift": "swift",
    "dart": "dart",
    "perl": "perl",
    "pl": "perl",
    "pm": "perl",
    "elixir": "elixir",
    "ex": "elixir",
    "exs": "elixir",
    "elisp": "elisp",
    "el": "elisp",
    ".el": "elisp",
    "emacs-lisp": "elisp",
    "emacs_lisp": "elisp",
    "html": "html",
    "css": "css",
}

# Canonical names that differ from tree-sitter-language-pack names
LANGUAGE_PACK_NAMES = {
    "c_sharp": "csharp",
}


class TreeSitterManager:
    """
    Manages tree-sitter language loading and parser creation.
    
    This class provides:
    - Thread-safe language caching
    - Language name aliasing
    - Parser lifecycle management
    - Clear error handling
    """
    
    def __init__(self):
        """Initialize the tree-sitter manager."""
        self._language_cache: Dict[str, Language] = {}
        self._cache_lock = threading.Lock()
    
    def _normalize_language_name(self, lang: str) -> str:
        """
        Normalize a language name to its canonical form.
        
        Args:
            lang: Language name (e.g., "py", "python", "c++")
            
        Returns:
            Canonical language name (e.g., "python", "cpp")
            
        Raises:
            ValueError: If language name is not recognized
        """
        normalized = LANGUAGE_ALIASES.get(lang.lower())
        if normalized is None:
            raise ValueError(
                f"Unknown language: {lang}. "
                f"Supported languages: {', '.join(sorted(set(LANGUAGE_ALIASES.values())))}"
            )
        return normalized
    
    def get_language_safe(self, lang: str) -> Language:
        """
        Get a cached Language object for the specified language.
        
        This method is thread-safe and caches languages to avoid repeated loading.
        
        Args:
            lang: Language name (supports aliases like "py", "c++", etc.)
            
        Returns:
            Tree-sitter Language object
            
        Raises:
            ValueError: If language is not supported
            Exception: If language loading fails
        """
        # Normalize the language name
        canonical_name = self._normalize_language_name(lang)
        _, _, load_language = _load_tree_sitter_dependencies()
        
        # Check cache first (fast path, no lock needed for reads)
        if canonical_name in self._language_cache:
            return self._language_cache[canonical_name]
        
        # Load language with lock (slow path)
        with self._cache_lock:
            # Double-check after acquiring lock
            if canonical_name in self._language_cache:
                return self._language_cache[canonical_name]
            
            try:
                # Map canonical name to language-pack name where they differ
                pack_name = LANGUAGE_PACK_NAMES.get(canonical_name, canonical_name)
                language = load_language(pack_name)
                
                self._language_cache[canonical_name] = language
                return language
            except (KeyError, ModuleNotFoundError):
                raise ValueError(
                    f"Language '{canonical_name}' is not available in tree-sitter-language-pack. "
                    f"This may be due to a missing or experimental grammar."
                )
            except Exception as e:
                raise Exception(
                    f"Failed to load language '{canonical_name}': {e}"
                )
    
    def create_parser(self, lang: str) -> Parser:
        """
        Create a new Parser instance for the specified language.
        
        IMPORTANT: Parsers are NOT thread-safe and should not be shared across threads.
        Each thread should create its own parser using this method.
        
        Args:
            lang: Language name (supports aliases)
            
        Returns:
            A new Parser instance configured for the language
            
        Raises:
            ValueError: If language is not supported
            Exception: If parser creation fails
        """
        _, parser_cls, _ = _load_tree_sitter_dependencies()
        language = self.get_language_safe(lang)
        
        # Determine if we need to use set_language (older tree-sitter)
        # In tree-sitter 0.22+, Parser takes language in constructor
        # In older versions, it must be set via set_language()
        try:
            parser = parser_cls(language)
            # Check if it actually worked by attempting a tiny parse
            # If language wasn't set, this usually returns None or fails
            if parser.parse(b"") is None:
                raise TypeError("Language not set")
        except (TypeError, ValueError, AttributeError):
            parser = parser_cls()
            parser.set_language(language)
        
        return parser
    
    def is_language_available(self, lang: str) -> bool:
        """
        Check if a language is available without raising exceptions.
        
        Args:
            lang: Language name
            
        Returns:
            True if language is available, False otherwise
        """
        try:
            self.get_language_safe(lang)
            return True
        except (ValueError, Exception):
            return False
    
    def get_supported_languages(self) -> list[str]:
        """
        Get a list of all supported language names.
        
        Returns:
            Sorted list of canonical language names
        """
        return sorted(set(LANGUAGE_ALIASES.values()))


# Global singleton instance
_manager_instance: Optional[TreeSitterManager] = None
_instance_lock = threading.Lock()


def get_tree_sitter_manager() -> TreeSitterManager:
    """
    Get the global TreeSitterManager instance (singleton pattern).
    
    Returns:
        The global TreeSitterManager instance
    """
    global _manager_instance
    
    if _manager_instance is not None:
        return _manager_instance
    
    with _instance_lock:
        if _manager_instance is None:
            _manager_instance = TreeSitterManager()
        return _manager_instance


# Convenience functions for backward compatibility
def get_language_safe(lang: str) -> Language:
    """Get a cached Language object. Thread-safe."""
    return get_tree_sitter_manager().get_language_safe(lang)


def create_parser(lang: str) -> Parser:
    """Create a new Parser for the language. Each call returns a new parser."""
    return get_tree_sitter_manager().create_parser(lang)


def execute_query(language: Language, query_string: str, node):
    """
    Execute a tree-sitter query and return captures in backward-compatible format.
    
    This function provides compatibility with the old tree-sitter 0.20.x API where
    you could call query.captures(node). The new 0.22+ API uses QueryCursor.
    
    Args:
        language: Tree-sitter Language object
        query_string: Query string in tree-sitter query syntax
        node: Tree-sitter Node to query
        
    Returns:
        List of (node, capture_name) tuples, compatible with old API
    """
    try:
        from tree_sitter import Query
    except ImportError as e:
        raise _missing_tree_sitter_error(e) from e
    
    # 1. Create the Query object
    try:
        # New API (0.22+)
        query = Query(language, query_string)
    except (TypeError, ValueError, AttributeError):
        # Old API (< 0.22)
        try:
            query = language.query(query_string)
        except Exception as e:
            raise Exception(f"Failed to create query: {e}")

    # 2. Execute the query
    try:
        from tree_sitter import QueryCursor
        # Modern API (0.22+)
        try:
            # 0.25.2 style: QueryCursor(query).captures(node) 
            # returns dict {name: [nodes]} in some versions or list of tuples in others
            cursor = QueryCursor(query)
            res = cursor.captures(node)
            
            if isinstance(res, dict):
                captures = []
                for name, nodes in res.items():
                    for n in nodes:
                        captures.append((n, name))
                return captures
            
            # Fallback for list of (node, capture_index) or (node, name)
            # Try to map indices back to names if they are integers
            if res and len(res) > 0 and isinstance(res[0][1], int):
                return [(n, query.capture_names[idx]) for n, idx in res]
            return res
            
        except (TypeError, ValueError):
            # 0.22 style: QueryCursor().captures(query, node)
            cursor = QueryCursor()
            res = cursor.captures(query, node)
            if isinstance(res, dict):
                captures = []
                for name, nodes in res.items():
                    for n in nodes:
                        captures.append((n, name))
                return captures
            if res and len(res) > 0 and isinstance(res[0][1], int):
                return [(n, query.capture_names[idx]) for n, idx in res]
            return res
        
    except (ImportError, AttributeError, NameError, TypeError):
        # Fallback to old API (< 0.22) or if QueryCursor failed
        try:
            return query.captures(node)
        except Exception as e:
            # Final failure if all paths fail
            raise Exception(
                f"Failed to execute query: {e}\n"
                f"Query string: {query_string[:100]}..."
            )

