# src/codegraphcontext/tools/indexing/embeddings.py
"""Batch embedding generation for Function nodes across graph backends.

Usage (after indexing is complete):
    from codegraphcontext.tools.indexing.embeddings import EmbeddingPipeline
    pipeline = EmbeddingPipeline(driver)
    pipeline.run(repo_path="/opt/repos/myapp")

Embeddings are stored on each Function node as ``embedding`` (list[float]).
Neo4j additionally creates a vector index named ``function_embeddings``.
Embedded backends (KùzuDB, LadybugDB) and FalkorDB store embeddings as node
properties; similarity search uses in-process cosine scoring (see
``vector_resolver``).

Model selection (via env var CGC_EMBEDDING_MODEL):
  - "openai"         → text-embedding-3-small via OpenAI API  (requires OPENAI_API_KEY)
  - "local"          → sentence-transformers/all-MiniLM-L6-v2 if available, else fastembed
  - "fastembed"      → fastembed BAAI/bge-small-en-v1.5 (ONNX, no torch required)
  - any HF model ID  → loaded via sentence-transformers
"""

from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from ...utils.debug_log import info_logger, warning_logger, error_logger

_DIM_OPENAI = 1536
_DIM_MINILM = 384
_DIM_BGE_SMALL = 384

_VECTOR_INDEX_NAME = "function_embeddings"


def detect_graph_backend(driver: Any) -> str:
    """Return a stable backend id for the active graph driver wrapper."""
    if hasattr(driver, "get_backend_type"):
        return driver.get_backend_type()
    cls = type(driver).__name__
    if cls == "Neo4jDriverWrapper":
        return "neo4j"
    if cls in ("FalkorDBDriverWrapper", "FalkorDBRemoteDriverWrapper"):
        return "falkordb"
    if cls in ("KuzuDriverWrapper", "LadybugDriverWrapper", "EmbeddedDriverWrapper"):
        backend_id = getattr(driver, "_backend_id", None)
        if backend_id:
            return backend_id
        return "kuzudb"
    return "unknown"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_text(fn: Dict[str, Any]) -> str:
    """Construct the text to embed for a Function node."""
    parts: List[str] = []
    qname = fn.get("qualified_name") or fn.get("name") or ""
    if qname:
        parts.append(qname)
    if fn.get("docstring"):
        parts.append(fn["docstring"])
    params = fn.get("parameters") or fn.get("args") or []
    if params:
        parts.append("params: " + ", ".join(str(p) for p in params))
    return " | ".join(parts) or "(anonymous)"


class _OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-small"):
        try:
            import openai
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        self.client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model
        self.dim = _DIM_OPENAI

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]


class _LocalEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("sentence-transformers package required: pip install sentence-transformers")
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, show_progress_bar=False).tolist()


class _FastEmbedder:
    """ONNX-based embedder via fastembed — no torch required, works on Python 3.13."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError("fastembed package required: pip install fastembed")
        self._model = TextEmbedding(model_name=model_name)
        self.dim = _DIM_BGE_SMALL

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]


def _get_embedder(model_spec: Optional[str] = None):
    """Return the appropriate embedder based on CGC_EMBEDDING_MODEL env var."""
    spec = model_spec or os.environ.get("CGC_EMBEDDING_MODEL", "local")
    if spec == "openai":
        return _OpenAIEmbedder()
    if spec == "fastembed":
        return _FastEmbedder()
    if spec == "local":
        try:
            return _LocalEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        except ImportError:
            info_logger("sentence-transformers not available; falling back to fastembed (ONNX)")
            return _FastEmbedder()
    return _LocalEmbedder(spec)


class EmbeddingPipeline:
    """Reads Function nodes, generates embeddings, and writes them back."""

    def __init__(self, driver: Any, batch_size: int = 256):
        self.driver = driver
        self.batch_size = batch_size
        self._backend = detect_graph_backend(driver)

    def _ensure_vector_index(self, dim: int) -> None:
        """Create a native vector index when the backend supports one."""
        if self._backend != "neo4j":
            info_logger(
                f"[EMBED] Backend '{self._backend}' uses property storage "
                "(cosine search in-process during vector resolve)"
            )
            return
        with self.driver.session() as session:
            try:
                session.run(
                    f"""
                    CREATE VECTOR INDEX {_VECTOR_INDEX_NAME} IF NOT EXISTS
                    FOR (f:Function) ON (f.embedding)
                    OPTIONS {{indexConfig: {{
                        `vector.dimensions`: {dim},
                        `vector.similarity_function`: 'cosine'
                    }}}}
                    """
                )
                info_logger(f"[EMBED] Vector index '{_VECTOR_INDEX_NAME}' ready (dim={dim})")
            except Exception as e:
                warning_logger(f"[EMBED] Could not create vector index: {e}")

    def _unembedded_predicate(self) -> str:
        if self._backend in ("kuzudb", "ladybugdb"):
            return "(f.embedding IS NULL OR size(f.embedding) = 0)"
        return "f.embedding IS NULL"

    def _fetch_unembedded(self, repo_path: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Return (path, name, props) for Function nodes without an embedding."""
        repo_path_prefix = repo_path.rstrip("/") + "/"
        predicate = self._unembedded_predicate()
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (f:Function)
                WHERE f.path STARTS WITH $repo_path_prefix
                  AND {predicate}
                RETURN f.path AS path, f.name AS name, f.line_number AS line_number,
                       f.qualified_name AS qualified_name,
                       f.docstring AS docstring,
                       f.parameters AS parameters
                """,
                repo_path_prefix=repo_path_prefix,
            )
            return [
                (
                    row["path"],
                    row["name"],
                    {
                        "line_number": row["line_number"],
                        "qualified_name": row.get("qualified_name"),
                        "docstring": row.get("docstring"),
                        "parameters": row.get("parameters") or [],
                    },
                )
                for row in result
            ]

    def _write_embeddings(self, rows: List[Dict[str, Any]]) -> None:
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (f:Function {name: row.name, path: row.path})
                WHERE row.line_number IS NULL OR f.line_number = row.line_number
                SET f.embedding = row.embedding
                """,
                rows=rows,
            )

    def invalidate_for_file(self, file_path: str) -> int:
        """Clear embeddings for all Function nodes in the given file."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function {path: $path})
                WHERE f.embedding IS NOT NULL
                REMOVE f.embedding
                RETURN count(f) AS cleared
                """,
                path=file_path,
            )
            row = result.single()
            cleared = row["cleared"] if row else 0
            info_logger(f"[EMBED] Invalidated {cleared} embeddings for {file_path}")
            return cleared

    def run(self, repo_path: str, model_spec: Optional[str] = None) -> None:
        """Generate and persist embeddings for all un-embedded Function nodes in repo."""
        embedder = _get_embedder(model_spec)
        self._ensure_vector_index(embedder.dim)

        info_logger(f"[EMBED] Fetching un-embedded functions for {repo_path} ...")
        nodes = self._fetch_unembedded(repo_path)
        info_logger(f"[EMBED] Found {len(nodes)} functions to embed")

        if not nodes:
            return

        total = 0
        batch_num = 0
        t0 = time.time()
        n_batches = (len(nodes) + self.batch_size - 1) // self.batch_size
        for i in range(0, len(nodes), self.batch_size):
            batch = nodes[i : i + self.batch_size]
            texts = [_build_text({"name": name, **props}) for _path, name, props in batch]
            try:
                vectors = embedder.embed_batch(texts)
            except Exception as e:
                error_logger(f"[EMBED] Batch {batch_num + 1}/{n_batches} failed: {e}")
                batch_num += 1
                continue

            write_rows = [
                {
                    "path": path,
                    "name": name,
                    "line_number": props.get("line_number"),
                    "embedding": vec,
                }
                for (path, name, props), vec in zip(batch, vectors)
            ]
            self._write_embeddings(write_rows)
            total += len(write_rows)
            batch_num += 1

            if batch_num % 10 == 0 or batch_num == n_batches:
                elapsed = time.time() - t0
                pct = int(100 * total / len(nodes))
                info_logger(f"[EMBED] batch {batch_num}/{n_batches} — {total}/{len(nodes)} ({pct}%) in {elapsed:.1f}s")

        info_logger(f"[EMBED] Done: {total} embeddings written in {time.time() - t0:.1f}s")
