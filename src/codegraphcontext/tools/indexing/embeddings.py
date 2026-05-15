# src/codegraphcontext/tools/indexing/embeddings.py
"""Batch embedding generation for Function nodes stored in Neo4j.

Usage (after indexing is complete):
    from codegraphcontext.tools.indexing.embeddings import EmbeddingPipeline
    pipeline = EmbeddingPipeline(driver)
    pipeline.run(repo_path="/opt/repos/myapp")

Embeddings are stored on each Function node as `embedding` (list[float]).
A Neo4j vector index named "function_embeddings" is created on first run.

Model selection (via env var CGC_EMBEDDING_MODEL):
  - "openai"         → text-embedding-3-small via OpenAI API  (requires OPENAI_API_KEY)
  - "local"          → sentence-transformers/all-MiniLM-L6-v2 if available, else fastembed BAAI/bge-small-en-v1.5
  - "fastembed"      → fastembed BAAI/bge-small-en-v1.5 (ONNX, no torch required)
  - any HF model ID  → loaded via sentence-transformers

The embedding dimension is stored on the vector index (1536 for OpenAI, 384 for MiniLM).
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from ...utils.debug_log import info_logger, warning_logger, error_logger

# Embedding dimension constants
_DIM_OPENAI = 1536
_DIM_MINILM = 384
_DIM_BGE_SMALL = 384

_VECTOR_INDEX_NAME = "function_embeddings"


def _build_text(fn: Dict[str, Any]) -> str:
    """Construct the text to embed for a Function node.

    We combine name, qualified_name, docstring, and parameter names
    so that semantically similar functions are close in embedding space.
    Never returns an empty string — falls back to "(anonymous)" so embedders
    don't receive blank input.
    """
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
            raise ImportError(
                "sentence-transformers package required: pip install sentence-transformers"
            )
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
            raise ImportError(
                "fastembed package required: pip install fastembed"
            )
        self._model = TextEmbedding(model_name=model_name)
        self.dim = _DIM_BGE_SMALL

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [vec.tolist() for vec in self._model.embed(texts)]


def _get_embedder(model_spec: Optional[str] = None):
    """Return the appropriate embedder based on CGC_EMBEDDING_MODEL env var.

    Falls back automatically: sentence-transformers → fastembed → error.
    """
    spec = model_spec or os.environ.get("CGC_EMBEDDING_MODEL", "local")
    if spec == "openai":
        return _OpenAIEmbedder()
    if spec == "fastembed":
        return _FastEmbedder()
    # "local" or a specific HF model ID — try sentence-transformers, fall back to fastembed
    if spec == "local":
        try:
            return _LocalEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        except ImportError:
            info_logger(
                "sentence-transformers not available; falling back to fastembed (ONNX)"
            )
            return _FastEmbedder()
    # Explicit HF model ID — must use sentence-transformers
    return _LocalEmbedder(spec)


class EmbeddingPipeline:
    """Reads Function nodes from Neo4j, generates embeddings, and writes them back."""

    def __init__(self, driver: Any, batch_size: int = 256):
        self.driver = driver
        self.batch_size = batch_size

    def _ensure_vector_index(self, dim: int) -> None:
        """Create the Neo4j vector index if it doesn't already exist."""
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

    def _fetch_unembedded(self, repo_path: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Return (path, name, props) for Function nodes without an embedding.

        Uses STARTS WITH (not CONTAINS) so a repo at /opt/repos/myapp never
        accidentally matches /opt/repos/myapp_extra.
        """
        repo_path_prefix = repo_path.rstrip("/") + "/"
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function)
                WHERE f.path STARTS WITH $repo_path_prefix
                  AND f.embedding IS NULL
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
        """Clear embeddings for all Function nodes in the given file.

        Called by the watcher after a file is modified so stale embeddings
        are re-generated on the next EmbeddingPipeline.run() call.
        Returns the number of functions cleared.
        """
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
                error_logger(f"[EMBED] Batch {batch_num+1}/{n_batches} failed: {e}")
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

            # Log every 10 batches so output is readable without being noisy
            if batch_num % 10 == 0 or batch_num == n_batches:
                elapsed = time.time() - t0
                pct = int(100 * total / len(nodes))
                info_logger(
                    f"[EMBED] batch {batch_num}/{n_batches} — {total}/{len(nodes)} ({pct}%) in {elapsed:.1f}s"
                )

        info_logger(f"[EMBED] Done: {total} embeddings written in {time.time() - t0:.1f}s")
