"""Cross-repo wire-coupling hints (MULTI_REPO_LINKS).

See docs/multi-repo-links.md (added in a later PR) for the full model.
"""

from codegraphcontext.wire.config_scanner import (
    DEFAULT_CONFIG_DIRS,
    parse_properties,
    parse_yaml_kv,
    scan_repo_config,
)
from codegraphcontext.wire.config_values import (
    BASE_PROFILE,
    ConfigValue,
    ConfigValueStore,
    PlaceholderResolution,
    flatten_yaml,
)
from codegraphcontext.wire.hints import (
    LoadedHintSet,
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
from codegraphcontext.wire.loader import (
    ENV_VAR_NAME,
    LoaderInputs,
    REPO_HINT_SUBDIR,
    WIRE_HINT_FILENAME,
    WireHintLoader,
)

__all__ = [
    "BASE_PROFILE",
    "ConfigValue",
    "ConfigValueStore",
    "DEFAULT_CONFIG_DIRS",
    "ENV_VAR_NAME",
    "LoadedHintSet",
    "LoaderInputs",
    "PlaceholderResolution",
    "REPO_HINT_SUBDIR",
    "SUPPORTED_ALIAS_KINDS",
    "SUPPORTED_ENDPOINT_PROTOCOLS",
    "SUPPORTED_HINT_VERSION",
    "SUPPORTED_TOPIC_SYSTEMS",
    "WIRE_HINT_FILENAME",
    "WireAlias",
    "WireEndpointHint",
    "WireHintFile",
    "WireHintLoader",
    "WireHintSource",
    "WireHintValidationError",
    "WireProvenance",
    "WireTopicHint",
    "flatten_yaml",
    "parse_properties",
    "parse_yaml_kv",
    "scan_repo_config",
]
