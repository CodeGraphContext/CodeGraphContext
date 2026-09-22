"""Cross-repo wire-coupling hints (MULTI_REPO_LINKS).

See docs/multi-repo-links.md (added in a later PR) for the full model.
"""

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
    "ENV_VAR_NAME",
    "LoadedHintSet",
    "LoaderInputs",
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
]
