# src/codegraphcontext/tools/indexing/schema_contract.py
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
    "EnumMember",
    "Union",
    "Record",
    "Property",
    "Annotation",
    "Module",
    "Parameter",
    # Build graph nodes (#888)
    "MavenModule",
    "GradleModule",
    "ExternalLibrary",
    # Datasource architecture graph (#843 scoped)
    "Datasource",
    "DbTable",
    "DbColumn",
    "RedisKeyPattern",
})

RELATIONSHIP_TYPES = frozenset({
    "CONTAINS",
    "CALLS",
    "IMPORTS",
    "INHERITS",
    "HAS_PARAMETER",
    "INCLUDES",
    "IMPLEMENTS",
    "PARTIAL_OF",
    "PART_OF",
    "DECORATED_BY",
    "METACLASS",
    "COMPANION_OF",
    "EMBEDS",
    # Spring DI semantic edges (#887)
    "INJECTS",
    "EXPOSES_ENDPOINT",
    "PROVIDES_BEAN",
    # Build graph edges (#888)
    "MODULE_DEPENDS_ON",
    "USES_LIBRARY",
    "CHILD_MODULE",
    "FILE_BELONGS_TO",
    # Datasource architecture graph (#843 scoped)
    "READS",
    "WRITES",
    "MAPS_TO",
    "HAS_COLUMN",
    "STORED_IN",
})

# Identity properties used in MERGE for code entities (path = absolute file path)
FUNCTION_MERGE_KEYS = ("name", "path", "line_number")
CLASS_MERGE_KEYS = ("name", "path", "line_number")
FILE_MERGE_KEYS = ("path",)
REPOSITORY_MERGE_KEYS = ("path",)
DIRECTORY_MERGE_KEYS = ("path",)
