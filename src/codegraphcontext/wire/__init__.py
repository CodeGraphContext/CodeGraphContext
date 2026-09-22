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
from codegraphcontext.wire.discover import (
    DiscoveryResult,
    EndpointIdentity,
    TopicIdentity,
    WireEndpointGroup,
    WireTopicGroup,
    discover,
)
from codegraphcontext.wire.go_extractor import (
    GoExtractionResult,
    extract_from_source as extract_go_from_source,
    looks_like_go_http_source,
)
from codegraphcontext.wire.grpc_extractor import (
    GrpcClientRecord,
    GrpcExtractionResult,
    GrpcServerRecord,
    extract_from_source as extract_grpc_from_source,
    looks_like_grpc_source,
)
from codegraphcontext.wire.grpc_scanner import (
    GrpcScanResult,
    scan_repo_grpc,
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
from codegraphcontext.wire.http_extractor import (
    HTTP_METHODS,
    HttpClientRecord,
    HttpExtractionResult,
    HttpServerRecord,
    extract_from_source as extract_http_from_source,
    looks_like_http_source,
)
from codegraphcontext.wire.http_scanner import (
    HttpScanResult,
    scan_repo_http,
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
from codegraphcontext.wire.language_scanner import (
    DEFAULT_GO_DIRS,
    DEFAULT_PYTHON_DIRS,
    LanguageScanResult,
    scan_repo_go_http,
    scan_repo_python_http,
)
from codegraphcontext.wire.loader import (
    ENV_VAR_NAME,
    LoaderInputs,
    REPO_HINT_SUBDIR,
    WIRE_HINT_FILENAME,
    WireHintLoader,
)

from codegraphcontext.wire.python_extractor import (
    PythonExtractionResult,
    extract_from_source as extract_python_from_source,
    looks_like_python_http_source,
)

from codegraphcontext.wire.writer import (
    WireWriteStats,
    write_wire_edges,
)

__all__ = [
    "BASE_PROFILE",
    "ConfigValue",
    "ConfigValueStore",
    "DEFAULT_CONFIG_DIRS",
    "DEFAULT_GO_DIRS",
    "DEFAULT_JAVA_SOURCE_DIRS",
    "DEFAULT_PYTHON_DIRS",
    "DiscoveryResult",
    "ENV_VAR_NAME",
    "EndpointIdentity",
    "GoExtractionResult",
    "GrpcClientRecord",
    "GrpcExtractionResult",
    "GrpcScanResult",
    "GrpcServerRecord",
    "HTTP_METHODS",
    "HttpClientRecord",
    "HttpExtractionResult",
    "HttpScanResult",
    "HttpServerRecord",
    "KafkaConsumerRecord",
    "KafkaExtractionResult",
    "KafkaProducerRecord",
    "KafkaScanResult",
    "LanguageScanResult",
    "LoadedHintSet",
    "LoaderInputs",
    "PlaceholderResolution",
    "PythonExtractionResult",
    "REPO_HINT_SUBDIR",
    "SUPPORTED_ALIAS_KINDS",
    "SUPPORTED_ENDPOINT_PROTOCOLS",
    "SUPPORTED_HINT_VERSION",
    "SUPPORTED_TOPIC_SYSTEMS",
    "TopicIdentity",
    "WIRE_HINT_FILENAME",
    "WireAlias",
    "WireEndpointGroup",
    "WireEndpointHint",
    "WireHintFile",
    "WireHintLoader",
    "WireHintSource",
    "WireHintValidationError",
    "WireProvenance",
    "WireTopicGroup",
    "WireTopicHint",
    "WireWriteStats",
    "discover",
    "extract_go_from_source",
    "extract_grpc_from_source",
    "extract_http_from_source",
    "extract_kafka_from_source",
    "extract_python_from_source",
    "flatten_yaml",
    "looks_like_go_http_source",
    "looks_like_grpc_source",
    "looks_like_http_source",
    "looks_like_kafka_source",
    "looks_like_python_http_source",
    "parse_properties",
    "parse_yaml_kv",
    "scan_repo_config",
    "scan_repo_go_http",
    "scan_repo_grpc",
    "scan_repo_http",
    "scan_repo_kafka",
    "scan_repo_python_http",
    "write_wire_edges",
]
