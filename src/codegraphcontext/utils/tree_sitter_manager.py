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

from typing import Dict, Optional
import threading

from tree_sitter import Language, Parser
from tree_sitter_language_pack import get_language


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
    
    # Canonical names (map to themselves for consistency)
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
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
        
        # Check cache first (fast path, no lock needed for reads)
        if canonical_name in self._language_cache:
            return self._language_cache[canonical_name]
        
        # Load language with lock (slow path)
        with self._cache_lock:
            # Double-check after acquiring lock
            if canonical_name in self._language_cache:
                return self._language_cache[canonical_name]
            
            try:
                # Special handling for C# which is available as tree_sitter_c_sharp
                if canonical_name == "c_sharp":
                    import tree_sitter_c_sharp
                    # tree_sitter_c_sharp.language() returns a PyCapsule, wrap it in Language
                    capsule = tree_sitter_c_sharp.language()
                    language = Language(capsule)
                else:
                    # Load the language from tree-sitter-language-pack
                    language = get_language(canonical_name)
                
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
        language = self.get_language_safe(lang)
        # In tree-sitter 0.25+, Parser takes language in constructor
        parser = Parser(language)
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
    you could call query.captures(node). The new 0.25+ API uses QueryCursor.
    
    Args:
        language: Tree-sitter Language object
        query_string: Query string in tree-sitter query syntax
        node: Tree-sitter Node to query
        
    Returns:
        List of (node, capture_name) tuples, compatible with old API
        
    Example:
        >>> from tree_sitter_language_pack import get_language
        >>> lang = get_language('python')
        >>> parser = Parser(lang)
        >>> tree = parser.parse(b'def hello(): pass')
        >>> captures = execute_query(lang, '(function_definition) @func', tree.root_node)
        >>> for node, name in captures:
        ...     print(f'{name}: {node.type}')
    """
    from tree_sitter import Query, QueryCursor
    
    try:
        # Create query and cursor
        query = Query(language, query_string)
        cursor = QueryCursor(query)
        
        # Execute query and convert to old format
        captures = []
        
        # Use matches() which returns (pattern_index, captures_dict) tuples
        for pattern_index, captures_dict in cursor.matches(node):
            # captures_dict is {capture_name: [nodes]}
            for capture_name, nodes in captures_dict.items():
                for captured_node in nodes:
                    # Old format: (node, capture_name)
                    captures.append((captured_node, capture_name))
        
        return captures
        
    except Exception as e:
        # Provide helpful error message
        raise Exception(
            f"Failed to execute query: {e}\n"
            f"Query string: {query_string[:100]}..."
        )

