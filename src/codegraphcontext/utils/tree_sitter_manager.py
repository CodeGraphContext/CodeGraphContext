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
            import tree_sitter_language_pack as language_pack

            # get_language in language-pack 1.20 performs cold-cache network
            # I/O while holding the GIL. prefetch releases it, so a parser
            # initialized by an indexing worker cannot freeze the gateway.
            # Older bundled packs may not expose prefetch and need no download.
            prefetch = getattr(language_pack, "prefetch", None)
            if prefetch is None:
                imported_get_language = language_pack.get_language
            else:
                def imported_get_language(name):
                    prefetch([name])
                    return language_pack.get_language(name)
        except ImportError:
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
    "hcl": "hcl",
    "terraform": "hcl",
    "tf": "hcl",

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
    "solidity": "solidity",
    "sol": "solidity",
    ".sol": "solidity",
    "html": "html",
    "css": "css",
    "svelte": "svelte",
    ".svelte": "svelte",
    "vue": "vue",
    ".vue": "vue",
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
                raise RuntimeError(
                    f"Failed to load language '{canonical_name}': {e}"
                ) from e
    
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


# Serialises query construction and execution across threads.
#
# `cgc index` runs parsers on a thread pool, and building a `Query` / running a
# `QueryCursor` concurrently on different languages crashes the native
# extension — a hard `Fatal Python error: Segmentation fault`, not a Python
# exception, so nothing above can catch or retry it (#1370). Reported
# tracebacks show three threads inside this function at once, on three
# different grammars.
#
# The lock is process-wide rather than per-language on purpose: the reports
# involve *different* languages crashing together, so a per-language lock would
# not have prevented them. Parsing itself (`parser.parse`) stays parallel; only
# the query step is serialised, and it is a small fraction of per-file work.
_QUERY_LOCK = threading.Lock()


def execute_query(language: Language, query_string: str, node):
    """
    Execute a tree-sitter query and return its captures in document order.

    Returns a list of ``(node, capture_name)`` tuples — the shape of the old
    0.20.x ``query.captures(node)`` — ordered by the captured node's position
    in the tree (pre-order: start byte, then outer before inner — longer span
    first, ancestor first when parent and child span the same bytes), then by
    pattern index, then by the capture's position in its match. That is the
    order tree-sitter's C cursor (``ts_query_cursor_next_capture``) yields in
    the common case: it walks the tree in pre-order and breaks a tie on one
    node by pattern index. It is *not* identical to it in every case: the C
    order also depends on *when* overlapping matches finish (e.g. a
    lower-index pattern on an inner node can be yielded before a higher-index
    pattern's capture of its parent when both matches finish together); here
    position always wins. The set of ``(node, name)`` pairs is exactly
    ``captures()``'s, each pair once, and the order in which each capture name
    is *first seen* matches ``captures()``'s dict key order (the only part of
    its answer that keeps the C order).

    Why not ``captures()``: py-tree-sitter 0.24+ returns ``{name: [nodes]}``,
    built through a per-name *set* of nodes, so the order of the nodes inside a
    name is the set's hash order — node ids, i.e. memory addresses — and differs
    on every parse of the same file.
    Flattening it also groups the captures by name, so a capture's neighbours
    were never its own match's other captures. Every consumer keeping the first
    or last match therefore attributed nondeterministically. ``matches()``
    returns its matches in a deterministic order and tags each with its pattern
    index; the result is sorted from it.

    The order is total and does not depend on hash seeds, memory layout,
    threads or the py-tree-sitter version: every API branch below goes through
    ``_ordered_captures``. Nothing else may call ``QueryCursor.captures`` /
    ``matches`` (enforced by tests/unit/utils/test_execute_query_order.py).

    Thread-safe: query construction and execution are serialised (see
    `_QUERY_LOCK`), because doing them concurrently segfaults the native
    extension.

    Args:
        language: Tree-sitter Language object
        query_string: Query string in tree-sitter query syntax
        node: Tree-sitter Node to query

    Returns:
        List of (node, capture_name) tuples in document order (see above).
    """
    try:
        from tree_sitter import Query
    except ImportError as e:
        raise _missing_tree_sitter_error(e) from e

    with _QUERY_LOCK:
        return _execute_query_locked(Query, language, query_string, node)


def _ordered_captures(matches, capture_names=None):
    """Flatten ``matches()`` output into document order (see `execute_query`).

    *matches* is a sequence of ``(pattern_index, captures)`` where *captures*
    is ``{name: [node, …]}`` (0.24/0.25), ``{name: node}`` (0.21–0.23) or a
    list of ``(node, name_or_index)`` pairs; *capture_names* maps integer
    capture indices to names.

    Sort key: ``(start_byte, -end_byte, depth, pattern_index, match ordinal,
    capture ordinal)`` — tree pre-order position: an outer node before an
    inner one that starts at the same byte, and, when parent and child span
    exactly the same bytes (``expression_statement`` around a ``call``), the
    ancestor first (``depth``, computed only for such equal spans); then
    pattern index for captures of one node; the two ordinals (positions in the
    deterministic ``matches()`` output) make the key total. Duplicate
    ``(node, name)`` pairs — one node captured under one name by several
    matches — keep their first occurrence.
    """
    entries = []
    for match_ordinal, (pattern_index, captures) in enumerate(matches):
        if isinstance(captures, dict):
            pairs = []
            for name, nodes in captures.items():
                if isinstance(nodes, (list, tuple)):
                    pairs.extend((n, name) for n in nodes)
                else:
                    pairs.append((nodes, name))
        else:
            pairs = list(captures)
        for capture_ordinal, (n, name) in enumerate(pairs):
            if isinstance(name, int) and capture_names is not None:
                name = capture_names[name]
            entries.append((n, name, pattern_index, match_ordinal, capture_ordinal))

    # Depth only breaks ties between *different* nodes with one span, so it is
    # computed only where such a tie exists (walking parents is O(depth)).
    span_nodes: dict = {}
    for n, *_ in entries:
        span_nodes.setdefault((n.start_byte, n.end_byte), set()).add(n.id)
    depth_cache: dict = {}

    def depth(n) -> int:
        if len(span_nodes[(n.start_byte, n.end_byte)]) < 2:
            return 0
        key = n.id
        if key not in depth_cache:
            d, cur = 0, n.parent
            while cur is not None:
                d, cur = d + 1, cur.parent
            depth_cache[key] = d
        return depth_cache[key]

    keyed = [((n.start_byte, -n.end_byte, depth(n), pattern_index, match_ordinal, capture_ordinal), n, name)
             for n, name, pattern_index, match_ordinal, capture_ordinal in entries]
    keyed.sort(key=lambda item: item[0])
    seen = set()
    ordered = []
    for _, n, name in keyed:
        ident = (n.start_byte, n.end_byte, n.type, name, n)
        if ident in seen:
            continue
        seen.add(ident)
        ordered.append((n, name))
    return ordered


def _execute_query_locked(Query, language: Language, query_string: str, node):
    """Body of `execute_query`; callers must hold `_QUERY_LOCK`."""

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

    capture_names = _capture_names(query)

    # 2. Execute the query: always through matches(), never captures() — see
    # execute_query for why. 0.25: QueryCursor(query).matches(node);
    # 0.24 and older: query.matches(node).
    try:
        try:
            from tree_sitter import QueryCursor
        except ImportError:
            QueryCursor = None
        if QueryCursor is not None:
            matches = QueryCursor(query).matches(node)
        else:
            matches = query.matches(node)
    except Exception as e:
        raise Exception(
            f"Failed to execute query: {e}\n"
            f"Query string: {query_string[:100]}..."
        )
    return _ordered_captures(matches, capture_names)


def _capture_names(query):
    """Capture index -> name, across py-tree-sitter versions (None if unavailable)."""
    names = getattr(query, "capture_names", None)
    if names is not None:
        return list(names)
    count = getattr(query, "capture_count", None)
    name_of = getattr(query, "capture_name", None)
    if isinstance(count, int) and callable(name_of):
        return [name_of(i) for i in range(count)]
    return None
