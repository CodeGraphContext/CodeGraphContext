# src/codegraphcontext/api/auth.py
"""Optional API-key authentication for the CodeGraphContext HTTP API.

Backward-compatible and opt-in:

* When **no** key is configured, the API behaves exactly as it did before
  (every endpoint is unauthenticated) but a prominent security warning is
  logged at startup so operators know the gateway is wide open.
* When a key **is** configured (via the ``CGC_API_KEY`` environment variable
  or the standard config mechanism), every protected router endpoint requires
  it, supplied as either ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``.
  Missing/incorrect keys receive an HTTP ``401``.

The comparison uses :func:`secrets.compare_digest` to avoid timing side
channels.
"""

import logging
import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# Config/env key that holds the API key. Reused as the config_manager key so
# ``cgc config set CGC_API_KEY <value>`` works as well.
API_KEY_ENV = "CGC_API_KEY"


def get_configured_api_key() -> Optional[str]:
    """Return the configured API key, or ``None`` when auth is disabled.

    Resolution order (highest priority first):

    1. The ``CGC_API_KEY`` environment variable (read directly so auth works
       even when no config file is present).
    2. The value stored via the existing config mechanism
       (:func:`codegraphcontext.cli.config_manager.get_config_value`).

    Empty / whitespace-only values are treated as "not configured".
    """
    env_val = os.getenv(API_KEY_ENV)
    if env_val and env_val.strip():
        return env_val.strip()

    # Fall back to the existing config mechanism (global/local .env, defaults).
    try:
        from codegraphcontext.cli.config_manager import get_config_value

        cfg_val = get_config_value(API_KEY_ENV)
        if cfg_val and cfg_val.strip():
            return cfg_val.strip()
    except Exception:  # pragma: no cover - config lookup is best-effort here
        pass

    return None


def _extract_provided_key(
    authorization: Optional[str], x_api_key: Optional[str]
) -> Optional[str]:
    """Pull the caller-supplied key from the Authorization or X-API-Key header."""
    if authorization:
        value = authorization.strip()
        if value.lower().startswith("bearer "):
            return value[len("bearer ") :].strip()
        # Accept a bare token in the Authorization header as a convenience.
        return value or None
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    return None


def _keys_match(provided: str, configured: str) -> bool:
    """Constant-time comparison that never raises on non-ASCII input."""
    try:
        return secrets.compare_digest(
            provided.encode("utf-8"), configured.encode("utf-8")
        )
    except (TypeError, AttributeError):
        return False


async def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that enforces the API key when one is configured.

    No-op (backward compatible) when no key is set; otherwise requires a valid
    key via ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``, returning
    HTTP ``401`` on a missing or incorrect key.
    """
    configured = get_configured_api_key()
    if not configured:
        # Auth disabled -> preserve the pre-existing unauthenticated behavior.
        return

    provided = _extract_provided_key(authorization, x_api_key)
    if not provided or not _keys_match(provided, configured):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


def log_auth_status() -> None:
    """Log the authentication status at app startup.

    Emits a prominent WARNING when the API is unauthenticated so the insecure
    default is impossible to miss in logs.
    """
    if get_configured_api_key():
        logger.info("API key authentication is ENABLED (CGC_API_KEY is set).")
    else:
        logger.warning(
            "⚠️  CodeGraphContext API is running WITHOUT authentication. "
            "Anyone who can reach this server can index code, run Cypher queries "
            "and call tools. Set CGC_API_KEY to require a key."
        )
