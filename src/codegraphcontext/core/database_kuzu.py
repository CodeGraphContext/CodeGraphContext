# src/codegraphcontext/core/database_kuzu.py
"""
Thread-safe singleton manager for the KùzuDB embedded graph database.

Implementation is delegated to ``database_embedded_kuzu`` (shared with LadybugDB).
"""

from .database_embedded_kuzu import (
    EmbeddedBackendSpec,
    EmbeddedCompatState,
    EmbeddedDriverWrapper,
    EmbeddedGraphManager,
    EmbeddedRecord,
    EmbeddedResultWrapper,
    EmbeddedSessionWrapper,
)

KUZU_SPEC = EmbeddedBackendSpec(
    backend_id="kuzudb",
    python_module="kuzu",
    display_name="KùzuDB",
    path_env_var="KUZUDB_PATH",
    config_key="KUZUDB_PATH",
    default_dir="kuzudb",
    install_hint="Run 'pip install kuzu'",
)


class KuzuDBManager(EmbeddedGraphManager):
    """Manages the KùzuDB database connection as a singleton."""

    BACKEND_SPEC = KUZU_SPEC
    _compat_state = EmbeddedCompatState()


# Backward-compatible public names used across tests and CLI helpers.
KuzuDriverWrapper = EmbeddedDriverWrapper
KuzuSessionWrapper = EmbeddedSessionWrapper
KuzuRecord = EmbeddedRecord
KuzuResultWrapper = EmbeddedResultWrapper
_KuzuCompatState = EmbeddedCompatState
