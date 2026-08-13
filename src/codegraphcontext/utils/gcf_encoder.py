"""
Optional GCF (Graph Compact Format) encoding for tool responses.

When enabled via CGC_OUTPUT_FORMAT=gcf, tool results are encoded using GCF
instead of JSON, reducing token consumption by ~62% on typical code graph data.

GCF encodes structured data with positional fields: keys declared once in a
header, values pipe-delimited per row. LLMs read it natively with 100%
comprehension accuracy across all frontier models tested.

Requires: pip install gcf-python
Falls back to JSON silently if the package is not installed.

See https://gcformat.com for the full specification.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_gcf_encode = None
_gcf_checked = False


def _load_gcf():
    """Lazily load GCF encoder. Check once, cache the result."""
    global _gcf_encode, _gcf_checked
    if _gcf_checked:
        return _gcf_encode
    _gcf_checked = True
    try:
        from gcf import encode_generic
        _gcf_encode = encode_generic
    except ImportError:
        _gcf_encode = None
    return _gcf_encode


def is_gcf_enabled() -> bool:
    """Check if GCF output format is enabled via environment variable."""
    return os.environ.get("CGC_OUTPUT_FORMAT", "").lower() == "gcf"


def encode_response(result: Any) -> str:
    """Encode a tool result as GCF (if enabled and available) or JSON.

    Args:
        result: The tool result dictionary to encode.

    Returns:
        Encoded string (GCF or JSON with indent=2).
    """
    if is_gcf_enabled():
        encoder = _load_gcf()
        if encoder is not None:
            try:
                return encoder(result)
            except Exception:
                logger.debug("GCF encoding failed; falling back to JSON", exc_info=True)

    return json.dumps(result, indent=2)
