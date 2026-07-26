# src/codegraphcontext/core/graph_query.py
"""
ROADMAP M4 — GraphQueryInterface protocol for database backends.

CodeFinder and indexing pipelines should depend on this interface rather than
backend-specific Cypher dialects. Implementations: Neo4j, FalkorDB, embedded
Kùzu-dialect (KùzuDB / LadybugDB), Nornic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple


class GraphQueryInterface(ABC):
    """Minimal contract shared by all CGC graph database managers."""

    name: str

    @abstractmethod
    def get_driver(self) -> Any:
        """Return a driver wrapper exposing ``session()`` compatible with Neo4j."""

    @abstractmethod
    def close_driver(self) -> None:
        """Release connections and embedded database resources."""

    @abstractmethod
    def is_connected(self) -> bool:
        """True when the backend is reachable and can execute a trivial query."""

    @abstractmethod
    def get_backend_type(self) -> str:
        """Stable backend identifier (e.g. ``neo4j``, ``kuzudb``, ``falkordb``)."""

    @classmethod
    @abstractmethod
    def validate_config(cls, *args, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate backend-specific configuration before connecting."""

    @classmethod
    @abstractmethod
    def test_connection(cls, *args, **kwargs) -> Tuple[bool, Optional[str]]:
        """Check whether the backend driver is installed and usable."""
