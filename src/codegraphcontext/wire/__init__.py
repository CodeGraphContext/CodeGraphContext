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
from codegraphcontext.wire.kafka_extractor import (
    KafkaConsumerRecord,
    KafkaExtractionResult,
    KafkaProducerRecord,
    extract_from_source as extract_kafka_from_source,
    looks_like_kafka_source,
)
from codegraphcontext.wire.kafka_scanner import (
    DEFAULT_JAVA_SOURCE_DIRS,
    KafkaScanResult,
    scan_repo_kafka,
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
    "DEFAULT_JAVA_SOURCE_DIRS",
    "ENV_VAR_NAME",
    "KafkaConsumerRecord",
    "KafkaExtractionResult",
    "KafkaProducerRecord",
    "KafkaScanResult",
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
    "extract_kafka_from_source",
    "flatten_yaml",
    "looks_like_kafka_source",
    "parse_properties",
    "parse_yaml_kv",
    "scan_repo_config",
    "scan_repo_kafka",
]
