"""Wire-coupling hint model (MULTI_REPO_LINKS).

Hints are human- or tool-provided DECLARED-tier statements that link a wire
node (Topic or Endpoint) to specific producers, consumers, servers, or
invokers by their fully-qualified symbol name. The indexing pipeline reads
loaded hints and emits PRODUCES_TO / CONSUMES_FROM / SERVES / INVOKES edges
with `match_confidence = 'DECLARED'` — the highest tier in the
WIRE_CONFIDENCE_TIERS priority list from schema_contract.

PR #2 ships the data model, YAML parser, and 4-source loader. Pipeline
consumption arrives per-extractor in later PRs and is gated on the
MULTI_REPO_LINKS config flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class WireHintSource(str, Enum):
    """Precedence order runs top-down: CLI > ENV > CONTEXT > REPO."""
    CLI = "cli"
    ENV = "env"
    CONTEXT = "context"
    REPO = "repo"


@dataclass(frozen=True)
class WireProvenance:
    """Where a single hint came from — used for `cgc wire list` and IndexWarning."""
    source: WireHintSource
    # Absolute path when source is CONTEXT or REPO; None for CLI/ENV.
    path: Optional[str] = None
    # 1-based line number in the source YAML, when known.
    line: Optional[int] = None


@dataclass
class WireTopicHint:
    """One asynchronous channel identity and the symbols wired to it."""
    system: str            # e.g. "kafka", "sqs", "rabbit", "pubsub"
    name: str              # e.g. "order-events"
    produced_by: List[str] = field(default_factory=list)   # FQNs, e.g. "orders.KafkaPublisherImpl.publish"
    consumed_by: List[str] = field(default_factory=list)
    provenance: List[WireProvenance] = field(default_factory=list)

    def merge_key(self) -> tuple:
        # Mirrors schema_contract.TOPIC_MERGE_KEYS.
        return (self.system, self.name)


@dataclass
class WireEndpointHint:
    """One synchronous wire address and the symbols wired to it."""
    protocol: str          # "http" | "grpc"
    method: str            # HTTP verb, or gRPC method name
    path: str              # URI template or gRPC "service/method"
    served_by: List[str] = field(default_factory=list)     # handler FQNs
    invoked_by: List[str] = field(default_factory=list)    # caller FQNs
    provenance: List[WireProvenance] = field(default_factory=list)

    def merge_key(self) -> tuple:
        # Mirrors schema_contract.ENDPOINT_MERGE_KEYS.
        return (self.protocol, self.method, self.path)


@dataclass
class WireAlias:
    """Declares that several wire identities are the same logical channel/endpoint.

    Emitted as ALIAS_OF edges at index time. Common uses: env-suffixed topic
    names ("orders-prod" -> "orders"), path templates that vary by version.
    """
    kind: str              # "topic" | "endpoint"
    canonical: str         # canonical identity string
    aliases: List[str] = field(default_factory=list)
    provenance: List[WireProvenance] = field(default_factory=list)


@dataclass
class WireHintFile:
    """Parsed representation of one wire.yml plus any warnings raised during parse."""
    version: int
    topics: List[WireTopicHint] = field(default_factory=list)
    endpoints: List[WireEndpointHint] = field(default_factory=list)
    aliases: List[WireAlias] = field(default_factory=list)
    source: WireProvenance = field(
        default_factory=lambda: WireProvenance(source=WireHintSource.REPO)
    )
    warnings: List[str] = field(default_factory=list)


@dataclass
class LoadedHintSet:
    """Result of WireHintLoader.load — hints merged across all four sources."""
    topics: List[WireTopicHint] = field(default_factory=list)
    endpoints: List[WireEndpointHint] = field(default_factory=list)
    aliases: List[WireAlias] = field(default_factory=list)
    # Per-source counts for `cgc wire list` UX.
    counts_by_source: dict = field(default_factory=dict)
    # Non-fatal problems surfaced from parsing (missing keys, unknown protocol, ...).
    warnings: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.topics or self.endpoints or self.aliases)


class WireHintValidationError(ValueError):
    """Raised on structural violations that make a hint unusable."""


SUPPORTED_HINT_VERSION = 1
SUPPORTED_TOPIC_SYSTEMS = ("kafka", "sqs", "rabbit", "pubsub", "nats", "kinesis")
SUPPORTED_ENDPOINT_PROTOCOLS = ("http", "grpc")
# YAML uses the plural form (`aliases.topics`, `aliases.endpoints`) to match
# the top-level `topics:` / `endpoints:` sections, so listeners can read a
# hint file without switching between singular and plural forms.
SUPPORTED_ALIAS_KINDS = ("topics", "endpoints")
