"""Per-repo ConfigValue store and placeholder resolver (MULTI_REPO_LINKS).

Extractors added in PR #4-#6 need to resolve Spring-style placeholders like
`${kafka.topic.orders}` and `@Value("${grpc.host}")` to concrete literal
strings before they can build a wire address. This module holds the parsed
values from a repo's application.properties / application.yml family and
performs best-effort placeholder substitution.

The store is per-repo scoped (repo_root + key) so cross-repo linkage
happens at the wire-address level (Topic/Endpoint merge keys), never at the
config-key level — two repos may legitimately define the same key with
different values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# Spring placeholder: ${key}   or  ${key:default}
# The default may contain colons (URLs, "localhost:9092"), so we allow any
# non-`}` character run.
_PLACEHOLDER_RE = re.compile(r"\$\{([^:{}]+)(?::([^{}]*))?\}")

# Empty profile string means "base configuration" (application.properties,
# application.yml with no -profile suffix).
BASE_PROFILE = ""


@dataclass(frozen=True)
class ConfigValue:
    """A single resolved config entry from a properties/YAML file."""
    repo_root: str        # absolute path to the repo root
    key: str              # dotted key, e.g. "kafka.topic.orders"
    value: str            # literal string value as it appears in the file
    source_file: str      # absolute path to the file where the value was defined
    source_kind: str      # "properties" | "yaml"
    profile: str = BASE_PROFILE   # "" for base, e.g. "prod" for application-prod.yml

    def merge_key(self) -> Tuple[str, str]:
        # Mirrors schema_contract.CONFIG_VALUE_MERGE_KEYS.
        return (self.repo_root, self.key)


@dataclass
class ConfigValueStore:
    """All config values discovered for a single repo, grouped by profile."""
    repo_root: str
    # profile -> key -> ConfigValue
    _by_profile: Dict[str, Dict[str, ConfigValue]] = field(default_factory=dict)

    def add(self, entry: ConfigValue) -> None:
        if entry.repo_root != self.repo_root:
            raise ValueError(
                f"ConfigValue repo_root {entry.repo_root!r} does not match "
                f"store repo_root {self.repo_root!r}"
            )
        self._by_profile.setdefault(entry.profile, {})[entry.key] = entry

    def get(self, key: str, active_profile: str = BASE_PROFILE) -> Optional[ConfigValue]:
        """Return the effective value for `key` — profile-specific if present, else base."""
        if active_profile and active_profile in self._by_profile:
            hit = self._by_profile[active_profile].get(key)
            if hit is not None:
                return hit
        return self._by_profile.get(BASE_PROFILE, {}).get(key)

    def get_value(self, key: str, active_profile: str = BASE_PROFILE) -> Optional[str]:
        e = self.get(key, active_profile)
        return None if e is None else e.value

    def all_entries(self) -> Iterable[ConfigValue]:
        for profile_map in self._by_profile.values():
            yield from profile_map.values()

    def known_profiles(self) -> List[str]:
        return sorted(self._by_profile.keys())

    def resolve_placeholders(
        self, text: str, active_profile: str = BASE_PROFILE
    ) -> "PlaceholderResolution":
        """Best-effort placeholder substitution.

        Leaves unresolved `${...}` in place so callers can still emit the
        original literal as a SYMBOLIC-tier edge and let cross-repo linkage
        happen on the raw placeholder key.
        """
        resolved_text_parts: List[str] = []
        cursor = 0
        used: List[Tuple[str, str]] = []   # (key, resolution_source)  base|profile|default
        unresolved: List[str] = []

        for m in _PLACEHOLDER_RE.finditer(text):
            resolved_text_parts.append(text[cursor:m.start()])
            key = m.group(1)
            default = m.group(2)

            # Profile match wins over base.
            entry = None
            source_label = ""
            if active_profile:
                profile_entry = self._by_profile.get(active_profile, {}).get(key)
                if profile_entry is not None:
                    entry = profile_entry
                    source_label = f"profile:{active_profile}"
            if entry is None:
                base_entry = self._by_profile.get(BASE_PROFILE, {}).get(key)
                if base_entry is not None:
                    entry = base_entry
                    source_label = "base"

            if entry is not None:
                resolved_text_parts.append(entry.value)
                used.append((key, source_label))
            elif default is not None:
                resolved_text_parts.append(default)
                used.append((key, "default"))
            else:
                resolved_text_parts.append(m.group(0))
                unresolved.append(key)

            cursor = m.end()
        resolved_text_parts.append(text[cursor:])

        return PlaceholderResolution(
            input=text,
            output="".join(resolved_text_parts),
            used=used,
            unresolved=unresolved,
        )


@dataclass(frozen=True)
class PlaceholderResolution:
    """Structured result of ConfigValueStore.resolve_placeholders."""
    input: str
    output: str
    used: List[Tuple[str, str]]     # (key, source_label)
    unresolved: List[str]

    def fully_resolved(self) -> bool:
        return not self.unresolved

    def is_pure_placeholder(self) -> bool:
        """True when the input was exactly one `${...}` with no surrounding text."""
        return bool(_PLACEHOLDER_RE.fullmatch(self.input))


def flatten_yaml(doc: object, prefix: str = "") -> Iterable[Tuple[str, str]]:
    """Walk a parsed YAML tree and yield (dotted_key, string_value) pairs.

    Non-string leaves (int, float, bool, None) are stringified so the store
    behaves consistently — a Kafka topic name might legitimately be `"1234"`
    and we don't want a YAML type inference to drop it.
    """
    if isinstance(doc, dict):
        for k, v in doc.items():
            key_str = str(k)
            child_prefix = f"{prefix}.{key_str}" if prefix else key_str
            yield from flatten_yaml(v, child_prefix)
    elif isinstance(doc, list):
        # Lists are stored as `key[i]` so array elements can be looked up.
        for i, item in enumerate(doc):
            yield from flatten_yaml(item, f"{prefix}[{i}]")
    elif doc is None:
        yield prefix, ""
    else:
        yield prefix, str(doc)
