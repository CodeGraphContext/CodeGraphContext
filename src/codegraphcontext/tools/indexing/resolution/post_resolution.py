# src/codegraphcontext/tools/indexing/resolution/post_resolution.py
"""Post-resolution pass: tighten low-confidence CALLS edges using INHERITS graph.

This module is called AFTER the initial CALLS graph is written.  It looks for
edges with confidence < 0.5 (tiers 8 and 9) where the call target has a
unique implementor that can be determined from the INHERITS graph.

Algorithm for each low-confidence CALLS edge (caller → called_name → same_file):
  1. Find all Function nodes with name = called_name across the codebase
  2. Find which of those are in classes that INHERIT from a common base
  3. If the caller file imports exactly one of those base types, resolve to
     the matching implementor
  4. Update the CALLS edge: set called_file_path, confidence, resolution_tier=10

Tier 10 = inheritance-graph resolved (confidence: 0.78)

This pass requires an active Neo4j driver.  It is called from pipeline.py
after `writer.write_function_call_groups()`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from ....utils.debug_log import info_logger, warning_logger
from ..persistence.utils import get_backend_type, execute_read_operation, execute_write_operation

# Tier 10: resolved via inheritance graph (better than tier 8 first-match bias)
_TIER_INHERIT_CONFIDENCE = 0.78
_TIER_INHERIT = 10

# Tier 11: inheritance + embedding similarity
_TIER_EMBED_CONFIDENCE = 0.82
_TIER_EMBED = 11


def run_inheritance_reresolve(
    driver: Any,
    repo_path: str,
    vector_resolver: Optional[Any] = None,
) -> int:
    """Re-resolve low-confidence CALLS edges using INHERITS graph + optional embeddings.

    Returns the number of edges that were improved.
    """
    t0 = time.time()
    improved = 0

    # Normalise repo_path to a directory prefix so STARTS WITH is safe:
    # "/opt/repos/myapp" must not accidentally match "/opt/repos/myapp_extra".
    repo_path_prefix = repo_path.rstrip("/") + "/"

    # Step 1: find all low-confidence same-file CALLS edges (tier 8 or 9)
    # These are edges where the resolver gave up and pointed to the caller's file.
    backend = get_backend_type(driver)
    def _read_work_1(session):
        return list(session.run(
            """
            MATCH (caller)-[c:CALLS]->(called)
            WHERE (caller.path STARTS WITH $repo_path_prefix
                   OR called.path STARTS WITH $repo_path_prefix)
              AND c.resolution_tier IN [8, 9]
            RETURN
                caller.name AS caller_name,
                caller.path AS caller_path,
                caller.line_number AS caller_line,
                called.name AS called_name,
                c.line_number AS call_line,
                c.full_call_name AS full_call_name,
                c.args AS args
            """,
            repo_path_prefix=repo_path_prefix,
        ))
    low_confidence = execute_read_operation(driver, backend, _read_work_1)

    info_logger(f"[INHERIT-RESOLVE] Found {len(low_confidence)} low-confidence edges to re-examine")
    if not low_confidence:
        return 0

    # Step 2: batch-fetch all candidate implementations in a single query.
    # Using UNWIND + IN instead of N separate round-trips prevents session
    # timeouts on large repos and is orders-of-magnitude faster.
    name_to_impls: Dict[str, List[Dict[str, Any]]] = {}

    # Guard: skip edges whose called_name is null/empty (e.g. calls to external Modules)
    unique_names: Set[str] = {
        row["called_name"] for row in low_confidence if row["called_name"]
    }

    _NAMES_BATCH = 500  # stay well under Cypher parameter-list limits
    unique_names_list = list(unique_names)
    backend = get_backend_type(driver)
    def _read_work_2(session):
        local_impls = {}
        for _i in range(0, len(unique_names_list), _NAMES_BATCH):
            chunk = unique_names_list[_i : _i + _NAMES_BATCH]
            result = session.run(
                """
                UNWIND $names AS name
                MATCH (cls:Class)-[:CONTAINS]->(fn:Function {name: name})
                WHERE fn.path STARTS WITH $repo_path_prefix
                OPTIONAL MATCH (cls)-[:INHERITS]->(parent:Class)
                RETURN fn.name AS queried_name, fn.path AS path,
                       fn.line_number AS line_number,
                       cls.name AS class_name, cls.qualified_name AS class_qname,
                       parent.name AS parent_name, parent.qualified_name AS parent_qname
                """,
                names=chunk,
                repo_path_prefix=repo_path_prefix,
            )
            for row in result:
                local_impls.setdefault(row["queried_name"], []).append(dict(row))
        return local_impls
    
    name_to_impls.update(execute_read_operation(driver, backend, _read_work_2))

    # Step 3: for each low-confidence edge, check if INHERITS narrows candidates
    # Strategy:
    #   a) If only 1 candidate exists across the entire repo → use it (tier 10)
    #   b) If multiple exist → filter to those in a class that INHERITS from something
    #      (prefer polymorphic implementations over utility helpers)
    #   c) If vector_resolver available → use embedding similarity to pick the best
    improvements: List[Dict[str, Any]] = []

    for row in low_confidence:
        called_name = row["called_name"]
        if not called_name:  # skip null/empty call targets (external module refs etc.)
            continue
        caller_path = row["caller_path"]
        impls = name_to_impls.get(called_name, [])

        # Skip if no candidates or all candidates are the caller itself
        candidates = [impl for impl in impls if impl["path"] != caller_path]
        if not candidates:
            continue

        best_path = None
        best_line = None
        confidence = _TIER_INHERIT_CONFIDENCE
        tier = _TIER_INHERIT

        if len(candidates) == 1:
            # Unambiguous: single implementation outside the caller file
            best_path = candidates[0]["path"]
            best_line = candidates[0].get("line_number")
        else:
            # Multiple candidates — prefer those that are part of an INHERITS hierarchy
            inheriting = [c for c in candidates if c.get("parent_name")]
            pool = inheriting if inheriting else candidates

            if len(pool) == 1:
                best_path = pool[0]["path"]
                best_line = pool[0].get("line_number")
            elif vector_resolver is not None:
                # Use embedding similarity to disambiguate
                vec_path = vector_resolver.resolve(
                    called_name=called_name,
                    caller_qualified_name=None,
                    candidate_paths=[c["path"] for c in pool],
                    repo_path=repo_path,
                )
                if vec_path:
                    best_path = vec_path
                    best_line = next((c.get("line_number") for c in pool if c["path"] == vec_path), None)
                    confidence = _TIER_EMBED_CONFIDENCE
                    tier = _TIER_EMBED
            # else: too ambiguous without vector — skip

        if best_path is None:
            continue

        improvements.append({
            "caller_path": caller_path,
            "caller_name": row["caller_name"],
            "caller_line": row["caller_line"],
            "called_name": called_name,
            "call_line": row["call_line"],
            "new_called_path": best_path,
            "new_called_line": best_line,
            "confidence": confidence,
            "resolution_tier": tier,
        })

    if not improvements:
        info_logger(f"[INHERIT-RESOLVE] No improvable edges found in {time.time()-t0:.1f}s")
        return 0

    info_logger(f"[INHERIT-RESOLVE] Re-resolving {len(improvements)} edges...")

    batch_size = 500
    backend = get_backend_type(driver)

    def _make_write_query(caller_has_line: bool, called_has_line: bool) -> str:
        caller_match = (
            "MATCH (caller:Function {name: row.caller_name, path: row.caller_path, line_number: row.caller_line})"
            if caller_has_line
            else "MATCH (caller {name: row.caller_name, path: row.caller_path})"
        )
        called_match = (
            "MATCH (new_called:Function {name: row.called_name, path: row.new_called_path, line_number: row.new_called_line})"
            if called_has_line
            else "MATCH (new_called:Function {name: row.called_name, path: row.new_called_path})"
        )
        return f"""
                UNWIND $batch AS row
                {caller_match}
                {called_match}
                OPTIONAL MATCH (caller)-[old_edge:CALLS]->(old_called {{name: row.called_name}})
                  WHERE old_edge.resolution_tier IN [8, 9]
                DELETE old_edge
                WITH caller, new_called, row
                MERGE (caller)-[c:CALLS {{called_name: row.called_name}}]->(new_called)
                SET c.line_number = coalesce(row.call_line, c.line_number),
                    c.confidence = row.confidence,
                    c.resolution_tier = row.resolution_tier,
                    c.resolution_method = 'inheritance'
                """

    def _write_work(session):
        local_improved = 0
        for i in range(0, len(improvements), batch_size):
            batch = improvements[i : i + batch_size]
            # Partition into 4 groups based on what line numbers are available
            buckets = {(True, True): [], (True, False): [], (False, True): [], (False, False): []}
            for row in batch:
                key = (
                    row.get("caller_line") is not None and isinstance(row.get("caller_line"), int),
                    row.get("new_called_line") is not None and isinstance(row.get("new_called_line"), int),
                )
                buckets[key].append(row)
            for (caller_has_line, called_has_line), sub_batch in buckets.items():
                if not sub_batch:
                    continue
                session.run(_make_write_query(caller_has_line, called_has_line), batch=sub_batch)
            local_improved += len(batch)
        return local_improved
    improved += execute_write_operation(driver, backend, _write_work)

    info_logger(
        f"[INHERIT-RESOLVE] Improved {improved} CALLS edges in {time.time()-t0:.1f}s"
    )
    return improved
