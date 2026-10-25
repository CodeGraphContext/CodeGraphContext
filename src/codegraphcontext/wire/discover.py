"""Cross-repo wire-coupling discovery (MULTI_REPO_LINKS).

Aggregate the output of :mod:`kafka_scanner`, :mod:`http_scanner`,
:mod:`grpc_scanner`, and :mod:`language_scanner` over one or more repos and
report matching / orphaned wire pairs on Topic and Endpoint identities.

The command is read-only and does not touch the graph. When paired with
``MULTI_REPO_LINKS=true`` in a later PR, the same aggregation will drive
edge materialization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from codegraphcontext.wire.config_scanner import scan_repo_config
from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.grpc_scanner import scan_repo_grpc
from codegraphcontext.wire.http_scanner import scan_repo_http
from codegraphcontext.wire.kafka_scanner import scan_repo_kafka
from codegraphcontext.wire.language_scanner import (
    scan_repo_go_http,
    scan_repo_python_http,
)


# ── Canonical identities & records ─────────────────────────────────────────

@dataclass(frozen=True)
class TopicIdentity:
    system: str        # "kafka" (only kafka in this PR series)
    name: str


@dataclass(frozen=True)
class EndpointIdentity:
    protocol: str      # "http" | "grpc"
    method: str        # "GET" / "POST" / "*" / RPC name
    path: str          # "/api/x" or "OrdersService/CreateOrder"


@dataclass
class WireEndpointGroup:
    identity: EndpointIdentity
    servers: List[dict] = field(default_factory=list)   # {fqn, source_file, line, confidence, provenance, framework, repo}
    clients: List[dict] = field(default_factory=list)

    def is_matched(self) -> bool:
        return bool(self.servers) and bool(self.clients)

    def is_orphan_server(self) -> bool:
        return bool(self.servers) and not self.clients

    def is_orphan_client(self) -> bool:
        return bool(self.clients) and not self.servers


@dataclass
class WireTopicGroup:
    identity: TopicIdentity
    producers: List[dict] = field(default_factory=list)
    consumers: List[dict] = field(default_factory=list)

    def is_matched(self) -> bool:
        return bool(self.producers) and bool(self.consumers)

    def is_orphan_producer(self) -> bool:
        return bool(self.producers) and not self.consumers

    def is_orphan_consumer(self) -> bool:
        return bool(self.consumers) and not self.producers


@dataclass
class DiscoveryResult:
    topics: Dict[Tuple[str, str], WireTopicGroup] = field(default_factory=dict)
    endpoints: Dict[Tuple[str, str, str], WireEndpointGroup] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    per_repo_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def matched_topics(self) -> List[WireTopicGroup]:
        return [t for t in self.topics.values() if t.is_matched()]

    def matched_endpoints(self) -> List[WireEndpointGroup]:
        return [e for e in self.endpoints.values() if e.is_matched()]

    def orphan_producers(self) -> List[WireTopicGroup]:
        return [t for t in self.topics.values() if t.is_orphan_producer()]

    def orphan_consumers(self) -> List[WireTopicGroup]:
        return [t for t in self.topics.values() if t.is_orphan_consumer()]

    def orphan_servers(self) -> List[WireEndpointGroup]:
        return [e for e in self.endpoints.values() if e.is_orphan_server()]

    def orphan_clients(self) -> List[WireEndpointGroup]:
        return [e for e in self.endpoints.values() if e.is_orphan_client()]


# ── Aggregation ─────────────────────────────────────────────────────────────

def _topic_group(result: DiscoveryResult, ident: TopicIdentity) -> WireTopicGroup:
    key = (ident.system, ident.name)
    if key not in result.topics:
        result.topics[key] = WireTopicGroup(identity=ident)
    return result.topics[key]


def _endpoint_group(result: DiscoveryResult, ident: EndpointIdentity) -> WireEndpointGroup:
    key = (ident.protocol, ident.method, ident.path)
    if key not in result.endpoints:
        result.endpoints[key] = WireEndpointGroup(identity=ident)
    return result.endpoints[key]


def discover(
    repos: List[Path],
    *,
    active_profile: str = BASE_PROFILE,
    per_repo_stores: Optional[Dict[str, ConfigValueStore]] = None,
) -> DiscoveryResult:
    """Run every extractor over ``repos`` and cross-reference the results.

    ``per_repo_stores`` lets callers pre-supply a :class:`ConfigValueStore` per
    repo (keyed by ``str(repo.resolve())``); otherwise the discovery step
    reads config values from each repo itself.
    """
    result = DiscoveryResult()
    for repo in repos:
        rp = Path(repo).resolve()
        rp_str = str(rp)
        store = (per_repo_stores or {}).get(rp_str) or scan_repo_config(rp)

        # Kafka
        k = scan_repo_kafka(rp, store=store, active_profile=active_profile)
        for p in k.producers:
            grp = _topic_group(result, TopicIdentity("kafka", p.topic_resolved))
            grp.producers.append({
                "fqn": p.fqn, "source_file": p.source_file, "line": p.line,
                "confidence": p.confidence, "provenance": p.provenance,
                "call_shape": p.call_shape, "repo": rp_str, "language": "java",
            })
        for c in k.consumers:
            grp = _topic_group(result, TopicIdentity("kafka", c.topic_resolved))
            grp.consumers.append({
                "fqn": c.fqn, "source_file": c.source_file, "line": c.line,
                "confidence": c.confidence, "provenance": c.provenance,
                "is_pattern": c.is_pattern, "repo": rp_str, "language": "java",
            })
        result.warnings.extend(k.warnings)

        # HTTP (Java)
        h = scan_repo_http(rp, store=store, active_profile=active_profile)
        for s in h.servers:
            grp = _endpoint_group(result, EndpointIdentity("http", s.method, s.path))
            grp.servers.append({
                "fqn": s.fqn, "source_file": s.source_file, "line": s.line,
                "confidence": s.confidence, "provenance": s.provenance,
                "framework": s.framework, "repo": rp_str, "language": "java",
            })
        for c in h.clients:
            grp = _endpoint_group(result, EndpointIdentity("http", c.method, c.path))
            grp.clients.append({
                "fqn": c.fqn, "source_file": c.source_file, "line": c.line,
                "confidence": c.confidence, "provenance": c.provenance,
                "framework": c.framework, "repo": rp_str, "language": "java",
            })
        result.warnings.extend(h.warnings)

        # gRPC
        g = scan_repo_grpc(rp, store=store, active_profile=active_profile)
        for s in g.servers:
            grp = _endpoint_group(result, EndpointIdentity("grpc", s.rpc, s.path))
            grp.servers.append({
                "fqn": s.fqn, "source_file": s.source_file, "line": s.line,
                "confidence": s.confidence, "provenance": s.provenance,
                "framework": "grpc-java", "repo": rp_str, "language": "java",
            })
        for c in g.clients:
            grp = _endpoint_group(result, EndpointIdentity("grpc", c.rpc, c.path))
            grp.clients.append({
                "fqn": c.fqn, "source_file": c.source_file, "line": c.line,
                "confidence": c.confidence, "provenance": c.provenance,
                "framework": f"grpc-java:{c.stub_kind}", "repo": rp_str, "language": "java",
            })
        result.warnings.extend(g.warnings)

        # Python + Go HTTP servers
        py = scan_repo_python_http(rp, store=store, active_profile=active_profile)
        for s in py.servers:
            grp = _endpoint_group(result, EndpointIdentity("http", s.method, s.path))
            grp.servers.append({
                "fqn": s.fqn, "source_file": s.source_file, "line": s.line,
                "confidence": s.confidence, "provenance": s.provenance,
                "framework": s.framework, "repo": rp_str, "language": "python",
            })
        result.warnings.extend(py.warnings)

        go = scan_repo_go_http(rp, store=store, active_profile=active_profile)
        for s in go.servers:
            grp = _endpoint_group(result, EndpointIdentity("http", s.method, s.path))
            grp.servers.append({
                "fqn": s.fqn, "source_file": s.source_file, "line": s.line,
                "confidence": s.confidence, "provenance": s.provenance,
                "framework": s.framework, "repo": rp_str, "language": "go",
            })
        result.warnings.extend(go.warnings)

        result.per_repo_stats[rp_str] = {
            "kafka_producers": len(k.producers),
            "kafka_consumers": len(k.consumers),
            "http_servers_java": len(h.servers),
            "http_clients_java": len(h.clients),
            "grpc_servers": len(g.servers),
            "grpc_clients": len(g.clients),
            "http_servers_python": len(py.servers),
            "http_servers_go": len(go.servers),
        }
    return result


__all__ = [
    "DiscoveryResult",
    "EndpointIdentity",
    "TopicIdentity",
    "WireEndpointGroup",
    "WireTopicGroup",
    "discover",
]
