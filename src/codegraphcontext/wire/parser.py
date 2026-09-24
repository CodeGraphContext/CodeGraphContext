"""Parsers for wire hint sources (YAML files, CLI shorthand, env var)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import yaml

from codegraphcontext.wire.hints import (
    SUPPORTED_ALIAS_KINDS,
    SUPPORTED_ENDPOINT_PROTOCOLS,
    SUPPORTED_HINT_VERSION,
    SUPPORTED_TOPIC_SYSTEMS,
    WireAlias,
    WireEndpointHint,
    WireHintFile,
    WireHintSource,
    WireHintValidationError,
    WireProvenance,
    WireTopicHint,
)


# ── YAML file parser ─────────────────────────────────────────────────────────

def parse_wire_yaml(
    text: str,
    *,
    source: WireHintSource = WireHintSource.REPO,
    source_path: Optional[str] = None,
) -> WireHintFile:
    """Parse a wire.yml document. Raises WireHintValidationError on hard errors."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise WireHintValidationError(f"YAML parse error: {e}") from e

    if doc is None:
        # Empty file is legal — treat as version 1 with no entries.
        doc = {"version": SUPPORTED_HINT_VERSION}
    if not isinstance(doc, dict):
        raise WireHintValidationError(
            f"top-level document must be a mapping, got {type(doc).__name__}"
        )

    version = doc.get("version", SUPPORTED_HINT_VERSION)
    if version != SUPPORTED_HINT_VERSION:
        raise WireHintValidationError(
            f"unsupported wire.yml version: {version!r} (this cgc supports v{SUPPORTED_HINT_VERSION})"
        )

    file_prov = WireProvenance(source=source, path=source_path)
    warnings: List[str] = []

    topics = _parse_topics(doc.get("topics") or [], file_prov, warnings)
    endpoints = _parse_endpoints(doc.get("endpoints") or [], file_prov, warnings)
    aliases = _parse_aliases(doc.get("aliases") or {}, file_prov, warnings)

    unknown_keys = set(doc.keys()) - {"version", "topics", "endpoints", "aliases"}
    if unknown_keys:
        warnings.append(
            f"unknown top-level keys ignored: {sorted(unknown_keys)}"
        )

    return WireHintFile(
        version=version,
        topics=topics,
        endpoints=endpoints,
        aliases=aliases,
        source=file_prov,
        warnings=warnings,
    )


def parse_wire_file(path: Path, *, source: WireHintSource = WireHintSource.REPO) -> WireHintFile:
    """Parse a wire.yml on disk. Missing file raises FileNotFoundError."""
    text = path.read_text(encoding="utf-8")
    return parse_wire_yaml(text, source=source, source_path=str(path.resolve()))


def _parse_topics(raw: object, file_prov: WireProvenance, warnings: List[str]) -> List[WireTopicHint]:
    if not isinstance(raw, list):
        raise WireHintValidationError(f"`topics` must be a list, got {type(raw).__name__}")
    result: List[WireTopicHint] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise WireHintValidationError(
                f"`topics[{i}]` must be a mapping, got {type(entry).__name__}"
            )
        system = _require_str(entry, "system", f"topics[{i}]")
        name = _require_str(entry, "name", f"topics[{i}]")
        if system not in SUPPORTED_TOPIC_SYSTEMS:
            warnings.append(
                f"topics[{i}]: unknown system {system!r} (supported: {list(SUPPORTED_TOPIC_SYSTEMS)}); "
                "hint kept, extractors may not resolve it"
            )
        result.append(
            WireTopicHint(
                system=system,
                name=name,
                produced_by=_string_list(entry.get("produced_by"), f"topics[{i}].produced_by"),
                consumed_by=_string_list(entry.get("consumed_by"), f"topics[{i}].consumed_by"),
                provenance=[file_prov],
            )
        )
    return result


def _parse_endpoints(raw: object, file_prov: WireProvenance, warnings: List[str]) -> List[WireEndpointHint]:
    if not isinstance(raw, list):
        raise WireHintValidationError(f"`endpoints` must be a list, got {type(raw).__name__}")
    result: List[WireEndpointHint] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise WireHintValidationError(
                f"`endpoints[{i}]` must be a mapping, got {type(entry).__name__}"
            )
        protocol = _require_str(entry, "protocol", f"endpoints[{i}]")
        method = _require_str(entry, "method", f"endpoints[{i}]")
        path = _require_str(entry, "path", f"endpoints[{i}]")
        if protocol not in SUPPORTED_ENDPOINT_PROTOCOLS:
            warnings.append(
                f"endpoints[{i}]: unknown protocol {protocol!r} "
                f"(supported: {list(SUPPORTED_ENDPOINT_PROTOCOLS)}); hint kept"
            )
        result.append(
            WireEndpointHint(
                protocol=protocol,
                method=method,
                path=path,
                served_by=_string_list(entry.get("served_by"), f"endpoints[{i}].served_by"),
                invoked_by=_string_list(entry.get("invoked_by"), f"endpoints[{i}].invoked_by"),
                provenance=[file_prov],
            )
        )
    return result


def _parse_aliases(raw: object, file_prov: WireProvenance, warnings: List[str]) -> List[WireAlias]:
    if not isinstance(raw, dict):
        raise WireHintValidationError(f"`aliases` must be a mapping, got {type(raw).__name__}")
    result: List[WireAlias] = []
    for kind in SUPPORTED_ALIAS_KINDS:
        for i, entry in enumerate(raw.get(kind) or []):
            if not isinstance(entry, dict):
                raise WireHintValidationError(
                    f"`aliases.{kind}[{i}]` must be a mapping"
                )
            canonical = _require_str(entry, "canonical", f"aliases.{kind}[{i}]")
            names = entry.get("names") or []
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise WireHintValidationError(
                    f"`aliases.{kind}[{i}].names` must be a list of strings"
                )
            result.append(
                WireAlias(kind=kind, canonical=canonical, aliases=names, provenance=[file_prov])
            )
    unknown_kinds = set(raw.keys()) - set(SUPPORTED_ALIAS_KINDS)
    if unknown_kinds:
        warnings.append(f"aliases: unknown kinds ignored: {sorted(unknown_kinds)}")
    return result


def _require_str(entry: dict, key: str, ctx: str) -> str:
    v = entry.get(key)
    if not isinstance(v, str) or not v.strip():
        raise WireHintValidationError(f"`{ctx}.{key}` is required and must be a non-empty string")
    return v.strip()


def _string_list(v: object, ctx: str) -> List[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
        raise WireHintValidationError(f"`{ctx}` must be a list of non-empty strings")
    return [s.strip() for s in v]


# ── CLI shorthand parser ─────────────────────────────────────────────────────
# Shape:   <scheme>:<identity>=<role>:<fqn>
# Kafka:   kafka:order-events=produced_by:orders.KafkaPublisherImpl.publish
# HTTP:    http:POST:/v1/users/{id}/orders=served_by:pkg.Controller.create
# gRPC:    grpc:GetStatus:com.example.status.v1.StatusService/GetStatus=served_by:pkg.Impl.getStatus

_TOPIC_ROLES = {"produced_by", "consumed_by"}
_ENDPOINT_ROLES = {"served_by", "invoked_by"}


def parse_cli_shorthand(hint: str, *, source: WireHintSource = WireHintSource.CLI) -> WireHintFile:
    """Parse a single `--wire` argument into a one-entry WireHintFile."""
    if "=" not in hint:
        raise WireHintValidationError(
            f"--wire {hint!r}: expected `<scheme>:<identity>=<role>:<fqn>`"
        )
    left, right = hint.split("=", 1)
    if ":" not in left or ":" not in right:
        raise WireHintValidationError(
            f"--wire {hint!r}: both sides of `=` must contain a `:`"
        )
    scheme, identity = left.split(":", 1)
    role, fqn = right.split(":", 1)
    scheme = scheme.strip().lower()
    role = role.strip()
    fqn = fqn.strip()
    if not (scheme and identity and role and fqn):
        raise WireHintValidationError(f"--wire {hint!r}: empty component")

    prov = WireProvenance(source=source)

    if scheme in SUPPORTED_TOPIC_SYSTEMS:
        if role not in _TOPIC_ROLES:
            raise WireHintValidationError(
                f"--wire {hint!r}: role {role!r} invalid for topic; use one of {sorted(_TOPIC_ROLES)}"
            )
        topic = WireTopicHint(system=scheme, name=identity.strip(), provenance=[prov])
        if role == "produced_by":
            topic.produced_by = [fqn]
        else:
            topic.consumed_by = [fqn]
        return WireHintFile(version=SUPPORTED_HINT_VERSION, topics=[topic], source=prov)

    if scheme in SUPPORTED_ENDPOINT_PROTOCOLS:
        # identity is `<method>:<path>` for endpoints.
        if ":" not in identity:
            raise WireHintValidationError(
                f"--wire {hint!r}: endpoint identity must be `<method>:<path>`"
            )
        method, ep_path = identity.split(":", 1)
        method = method.strip()
        ep_path = ep_path.strip()
        if role not in _ENDPOINT_ROLES:
            raise WireHintValidationError(
                f"--wire {hint!r}: role {role!r} invalid for endpoint; use one of {sorted(_ENDPOINT_ROLES)}"
            )
        ep = WireEndpointHint(protocol=scheme, method=method, path=ep_path, provenance=[prov])
        if role == "served_by":
            ep.served_by = [fqn]
        else:
            ep.invoked_by = [fqn]
        return WireHintFile(version=SUPPORTED_HINT_VERSION, endpoints=[ep], source=prov)

    raise WireHintValidationError(
        f"--wire {hint!r}: unknown scheme {scheme!r} "
        f"(topic systems: {list(SUPPORTED_TOPIC_SYSTEMS)}, "
        f"endpoint protocols: {list(SUPPORTED_ENDPOINT_PROTOCOLS)})"
    )


def parse_env_hints(text: Optional[str]) -> List[WireHintFile]:
    """Split CGC_WIRE env var into individual shorthand hints (one per line)."""
    if not text:
        return []
    out: List[WireHintFile] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(parse_cli_shorthand(line, source=WireHintSource.ENV))
    return out


def parse_cli_hints(hints: Iterable[str]) -> List[WireHintFile]:
    """Parse a batch of --wire values from the CLI."""
    return [parse_cli_shorthand(h, source=WireHintSource.CLI) for h in hints]
