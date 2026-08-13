# src/codegraphcontext/core/database_ladybug.py
"""
Thread-safe singleton manager for the LadybugDB embedded graph database.

Implementation is delegated to ``database_embedded_kuzu`` (shared with KùzuDB).
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

LADYBUG_SPEC = EmbeddedBackendSpec(
    backend_id="ladybugdb",
    python_module="ladybug",
    display_name="LadybugDB",
    path_env_var="LADYBUGDB_PATH",
    config_key="LADYBUGDB_PATH",
    default_dir="ladybugdb",
    install_hint="Run 'pip install ladybug'",
)


class LadybugDBManager(EmbeddedGraphManager):
    """Manages the LadybugDB database connection as a singleton."""

    BACKEND_SPEC = LADYBUG_SPEC
    _compat_state = EmbeddedCompatState()


# Backward-compatible public names.
LadybugDriverWrapper = EmbeddedDriverWrapper
LadybugSessionWrapper = EmbeddedSessionWrapper
LadybugRecord = EmbeddedRecord
LadybugResultWrapper = EmbeddedResultWrapper
_LadybugCompatState = EmbeddedCompatState
