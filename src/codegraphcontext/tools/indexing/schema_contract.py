"""
Semantic graph contract: labels, relationship types, and merge keys used by indexing.

Backends must produce nodes/relationships consistent with this contract so MCP
and query tools remain stable. This module is documentation + test hooks only.
"""

# Node labels written by the indexing pipeline (excluding dynamic query-only uses)
NODE_LABELS = frozenset({
    "Repository",
    "Directory",
    "File",
    "Function",
    "Class",
    "Trait",
    "Variable",
    "Interface",
    "Macro",
    "Struct",
    "Enum",
    "Union",
    "Record",
    "Property",
    "Annotation",
    "Module",
    "Parameter",
})

RELATIONSHIP_TYPES = frozenset({
    "CONTAINS",
    "CALLS",
    "IMPORTS",
    "INHERITS",
    "HAS_PARAMETER",
    "INCLUDES",
    "IMPLEMENTS",
})

# Identity properties used in MERGE for code entities (path = absolute file path)
FUNCTION_MERGE_KEYS = ("name", "path", "line_number")
CLASS_MERGE_KEYS = ("name", "path", "line_number")
FILE_MERGE_KEYS = ("path",)
REPOSITORY_MERGE_KEYS = ("path",)
DIRECTORY_MERGE_KEYS = ("path",)
