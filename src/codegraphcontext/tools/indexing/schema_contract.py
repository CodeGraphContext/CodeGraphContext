# src/codegraphcontext/tools/indexing/schema_contract.py
"""
Semantic graph contract: labels, relationship types, and merge keys used by indexing.

Backends must produce nodes/relationships consistent with this contract so MCP
and query tools remain stable. This module is documentation + test hooks only.
"""

# Runtime-gate name for the MULTI_REPO_LINKS feature. Every wire-coupling
# extractor, writer, and CLI surface reads this key via get_config_value(...).
# When the value is "false" (default), nothing in this file's `WIRE_*` sections
# is materialized in the graph.
MULTI_REPO_LINKS_FLAG = "MULTI_REPO_LINKS"

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
    # Multi-repo wire-coupling graph (MULTI_REPO_LINKS, PR #1)
    # Nodes are only materialized when MULTI_REPO_LINKS=true at index time.
    # Their presence in this contract is unconditional so consumers reading
    # the schema can pre-declare filters without gating on runtime config.
    "Topic",         # Async message channel identity (system, name)
    "Endpoint",      # Sync wire address (protocol, method, path)
    "ConfigValue",   # Resolved application config entry backing a topic/endpoint
    "HintFile",      # Provenance node for a loaded .cgc/wire.yml (or CLI hint set)
    "IndexWarning",  # Non-fatal diagnostic surfaced from an index run
    "Stub",          # Sub-label on Function/Class placeholder for un-indexed symbol
})

RELATIONSHIP_TYPES = frozenset({
    "CONTAINS",
    "CALLS",
    "HEURISTIC_CALLS",
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
    # Multi-repo wire-coupling edges (MULTI_REPO_LINKS, PR #1)
    # Only materialized when MULTI_REPO_LINKS=true at index time.
    "PRODUCES_TO",     # Function -> Topic          (Kafka/SQS/Rabbit/PubSub producer)
    "CONSUMES_FROM",   # Function -> Topic          (@KafkaListener, @SqsListener, ...)
    "SERVES",          # Function -> Endpoint       (HTTP handler / gRPC ImplBase override)
    "INVOKES",         # Function -> Endpoint       (RestTemplate / WebClient / Feign / gRPC stub)
    "ALIAS_OF",        # Topic|Endpoint <-> Topic|Endpoint  (normalized identity link)
    "SUPERSEDED_BY",   # Wire edge -> Wire edge     (auto-discovered edge overridden by a DECLARED hint)
    "HINTED_BY",       # Wire edge|node -> HintFile (provenance for DECLARED-tier edges)
    "RESOLVED_FROM",   # Topic|Endpoint -> ConfigValue      (audit trail for SpEL/YAML resolution)
})

# Wire-coupling confidence tiers written to `match_confidence` on every
# PRODUCES_TO / CONSUMES_FROM / SERVES / INVOKES / ALIAS_OF edge.
# Order is priority: earlier entries win when two tiers apply to the same pair.
# Consumers filter with `WHERE r.match_confidence IN ['DECLARED','EXTRACTED']`
# for high-trust traversals.
WIRE_CONFIDENCE_TIERS = (
    "DECLARED",     # 0 — Human-asserted via .cgc/wire.yml, CLI --wire, or CGC_WIRE env
    "EXTRACTED",    # 1 — Both ends resolved to the same literal string
    "INFERRED",     # 2 — One end resolved via YAML / @Value / final-constant tracing
    "NORMALIZED",   # 3 — Matched after env-suffix strip / path templating
    "SYMBOLIC",     # 4 — Both ends unresolved SpEL/${...}, same symbolic key
    "AMBIGUOUS",    # 5 — Multiple candidates or fuzzy identity match
    "SUPERSEDED",   # 6 — Auto-emitted but overridden by a DECLARED edge
)

# Identity properties used in MERGE for code entities (path = absolute file path).
# occurrence_index disambiguates distinct symbols that share a name and a line in
# one file -- grouped CSS selectors, minified JS bundles -- which the previous
# three-property key silently merged into a single node (#1393). It is 0 for the
# first record of each (name, line_number) key, so identity is unchanged for the
# overwhelming majority of symbols, which never collide.
FUNCTION_MERGE_KEYS = ("name", "path", "line_number", "occurrence_index")
CLASS_MERGE_KEYS = ("name", "path", "line_number", "occurrence_index")
FILE_MERGE_KEYS = ("path",)
REPOSITORY_MERGE_KEYS = ("path",)
DIRECTORY_MERGE_KEYS = ("path",)

# Merge keys for wire-coupling nodes (MULTI_REPO_LINKS, PR #1).
# Every key is a string identity of the *wire address*, never a path — this is
# what lets producer-in-repo-A and consumer-in-repo-B land on the same node
# without any cross-repo coordination during indexing.
TOPIC_MERGE_KEYS = ("system", "name")                       # e.g. ("kafka", "group-chat-notifications")
ENDPOINT_MERGE_KEYS = ("protocol", "method", "path")        # e.g. ("http", "POST", "/v1/players/{id}/invitations")
CONFIG_VALUE_MERGE_KEYS = ("repo_root", "key")              # per-repo scoped; alias linkage is on Topic/Endpoint, not here
HINT_FILE_MERGE_KEYS = ("path",)                            # absolute path of the loaded hint file
INDEX_WARNING_MERGE_KEYS = ("run_id", "category", "message")
