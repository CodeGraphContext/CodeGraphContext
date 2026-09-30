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

# Comma-separated allowlists for the MCP transport's DNS-rebinding protection.
#
# Origin is validated by default (browsers send it; a CLI/desktop MCP client
# doesn't, and an absent Origin is always allowed) — this is the actual
# DNS-rebinding vector, a malicious page in the user's browser making
# same-origin-looking requests to a locally-bound server. The default
# allowlist covers localhost; add remote origins via CGC_MCP_ALLOWED_ORIGINS.
#
# Host is NOT checked by default: this gateway commonly sits behind a proxy
# or is reached over a non-loopback hostname (default bind is 0.0.0.0), so
# there's no single default that wouldn't reject legitimate deployments. Set
# CGC_MCP_ALLOWED_HOSTS to opt in once the deployment's real hostname(s) are
# known.
MCP_ALLOWED_HOSTS_ENV = "CGC_MCP_ALLOWED_HOSTS"
MCP_ALLOWED_ORIGINS_ENV = "CGC_MCP_ALLOWED_ORIGINS"
DEFAULT_MCP_ALLOWED_ORIGINS = [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
    # Portless forms (no ":*" suffix to match): a browser omits the port for
    # the default http port, so "http://localhost:*" alone won't match
    # "http://localhost".
    "http://127.0.0.1",
    "http://localhost",
    "http://[::1]",
]


def _get_list_env(name: str) -> list[str]:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_mcp_transport_security_config() -> tuple[list[str], list[str]]:
    """Return the configured (allowed_hosts, allowed_origins) allowlists.

    ``allowed_hosts`` is empty unless CGC_MCP_ALLOWED_HOSTS is set (Host
    checking is opt-in). ``allowed_origins`` defaults to localhost when
    CGC_MCP_ALLOWED_ORIGINS is unset (Origin checking is on by default).
    """
    configured_origins = _get_list_env(MCP_ALLOWED_ORIGINS_ENV)
    return (
        _get_list_env(MCP_ALLOWED_HOSTS_ENV),
        configured_origins or list(DEFAULT_MCP_ALLOWED_ORIGINS),
    )


def _host_matches(host: Optional[str], allowed: list[str]) -> bool:
    if not host:
        return False
    if host in allowed:
        return True
    return any(pattern.endswith(":*") and host.startswith(pattern[:-2] + ":") for pattern in allowed)


def _origin_matches(origin: Optional[str], allowed: list[str]) -> bool:
    # Origin can legitimately be absent (same-origin / non-browser clients).
    if not origin:
        return True
    if origin in allowed:
        return True
    return any(pattern.endswith(":*") and origin.startswith(pattern[:-2] + ":") for pattern in allowed)


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


async def require_mcp_transport_security(
    host: Optional[str] = Header(default=None),
    origin: Optional[str] = Header(default=None),
) -> None:
    """FastAPI dependency enforcing the same DNS-rebinding checks as the
    Streamable HTTP mount's ASGI middleware, for the legacy MCP-over-SSE
    routes (which don't go through that middleware).

    Origin is checked by default (localhost allowlist); Host only when
    CGC_MCP_ALLOWED_HOSTS is set. See get_mcp_transport_security_config().
    """
    allowed_hosts, allowed_origins = get_mcp_transport_security_config()

    if allowed_hosts and not _host_matches(host, allowed_hosts):
        logger.warning("Rejected MCP request with Host %r; add it to CGC_MCP_ALLOWED_HOSTS if legitimate.", host)
        raise HTTPException(status_code=421, detail="Invalid Host header")

    if not _origin_matches(origin, allowed_origins):
        logger.warning("Rejected MCP request with Origin %r; add it to CGC_MCP_ALLOWED_ORIGINS if legitimate.", origin)
        raise HTTPException(status_code=403, detail="Invalid Origin header")


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

    allowed_hosts, allowed_origins = get_mcp_transport_security_config()
    logger.info(
        "MCP transport Origin validation is ENABLED (allowed_origins=%s). "
        "Set CGC_MCP_ALLOWED_ORIGINS (comma-separated) to extend it.",
        allowed_origins,
    )
    if allowed_hosts:
        logger.info("MCP transport Host validation is ENABLED (allowed_hosts=%s).", allowed_hosts)
    else:
        logger.warning(
            "⚠️  MCP transport is running WITHOUT Host header validation. "
            "Set CGC_MCP_ALLOWED_HOSTS (comma-separated) to enable it."
        )
