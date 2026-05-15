# src/codegraphcontext/tools/indexing/vector_resolver.py
"""Vector-similarity-based call resolution using pre-computed Function embeddings.

This module is used as the final tiebreaker in `resolve_function_call` when
heuristic tiers 1–8 cannot produce a high-confidence answer.  It queries the
Neo4j vector index to find the Function node whose embedding is most similar
to a query constructed from the call context.

Architecture:
  - VectorResolver wraps a live Neo4j driver session
  - `resolve(call, caller_context, candidates)` returns the best candidate path
    or None if no candidate clears the similarity threshold
  - The resolver is instantiated once per indexing run and passed into
    `build_function_call_groups` as an optional argument (Phase 4 wiring)

Requires:
  - Function nodes must have been embedded via embeddings.EmbeddingPipeline
  - Neo4j vector index "function_embeddings" must exist
  - An embedder compatible with the one used during embedding generation
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ...utils.debug_log import info_logger, warning_logger

_VECTOR_INDEX_NAME = "function_embeddings"
_DEFAULT_THRESHOLD = 0.75  # cosine similarity floor
_DEFAULT_TOP_K = 5


class VectorResolver:
    """Use Neo4j ANN vector search to pick the best Function among candidates."""

    def __init__(
        self,
        driver: Any,
        threshold: float = _DEFAULT_THRESHOLD,
        top_k: int = _DEFAULT_TOP_K,
    ):
        self.driver = driver
        self.threshold = threshold
        self.top_k = top_k
        self._embedder = None  # lazy-loaded

    def _get_embedder(self):
        if self._embedder is None:
            # Import here to avoid circular deps and to keep the embedder lazy
            from codegraphcontext.tools.indexing.embeddings import _get_embedder
            self._embedder = _get_embedder()
        return self._embedder

    def _embed_query(self, text: str) -> List[float]:
        return self._get_embedder().embed_batch([text])[0]

    def resolve(
        self,
        called_name: str,
        caller_qualified_name: Optional[str],
        candidate_paths: List[str],
        repo_path: str,
    ) -> Optional[str]:
        """Return the file path of the best-matching Function among candidates.

        Args:
            called_name: The short method name being called (e.g. "execute").
            caller_qualified_name: FQN of the calling function for context.
            candidate_paths: File paths that define `called_name`; we restrict
                the ANN search to these paths.
            repo_path: Path prefix to scope the index query.

        Returns:
            The file path of the best candidate, or None if below threshold.
        """
        if not candidate_paths:
            return None

        query_text = f"{caller_qualified_name or ''} calls {called_name}"
        try:
            query_vec = self._embed_query(query_text)
        except Exception as e:
            warning_logger(f"[VECTOR] Embed query failed: {e}")
            return None

        with self.driver.session() as session:
            try:
                # Expand top_k to cover all candidates so we never miss the right one.
                # A fixed top_k=5 would silently drop candidates when len(paths) > 5.
                effective_top_k = max(self.top_k, len(candidate_paths))
                result = session.run(
                    f"""
                    CALL db.index.vector.queryNodes(
                        '{_VECTOR_INDEX_NAME}', $top_k, $vec
                    ) YIELD node AS fn, score
                    WHERE fn.name = $name
                      AND fn.path IN $paths
                    RETURN fn.path AS path, score
                    ORDER BY score DESC
                    LIMIT 1
                    """,
                    top_k=effective_top_k,
                    vec=query_vec,
                    name=called_name,
                    paths=candidate_paths,
                )
                row = result.single()
                if row and row["score"] >= self.threshold:
                    return row["path"]
            except Exception as e:
                warning_logger(f"[VECTOR] ANN query failed: {e}")

        return None

    def resolve_bulk(
        self,
        calls: List[Dict[str, Any]],
        repo_path: str,
    ) -> Dict[int, str]:
        """Resolve a list of calls in one pass; returns {call_index: resolved_path}.

        Each call dict must have:
          - "called_name": str
          - "candidate_paths": List[str]
          - "caller_qualified_name": Optional[str]
        """
        results: Dict[int, str] = {}
        for idx, call in enumerate(calls):
            resolved = self.resolve(
                called_name=call["called_name"],
                caller_qualified_name=call.get("caller_qualified_name"),
                candidate_paths=call["candidate_paths"],
                repo_path=repo_path,
            )
            if resolved:
                results[idx] = resolved
        return results
