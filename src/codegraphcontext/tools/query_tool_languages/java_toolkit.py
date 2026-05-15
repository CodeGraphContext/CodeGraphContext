# src/codegraphcontext/tools/query_tool_languages/java_toolkit.py
"""Java-specific analysis toolkit (#889).

Provides Spring-aware query methods used by the ``advanced_language_query_tool``
and directly accessible via MCP tools ``find_java_spring_endpoints`` /
``find_java_spring_beans``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class JavaToolkit:
    """Spring-aware Java analysis methods backed by CodeFinder / raw Cypher."""

    def __init__(self, code_finder: Any):
        """
        Args:
            code_finder: A ``CodeFinder`` instance (or compatible duck-type).
        """
        self._cf = code_finder
        self._driver = code_finder.driver

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run(self, query: str, **params) -> List[Dict]:
        try:
            with self._driver.session() as session:
                result = session.run(query, **params)
                return [dict(r) for r in result]
        except Exception as exc:
            return [{"_error": str(exc)}]

    # ── Public API ────────────────────────────────────────────────────────────

    def find_spring_endpoints(
        self,
        http_method: Optional[str] = None,
        path_pattern: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> List[Dict]:
        """Return Spring HTTP endpoint functions.

        Args:
            http_method:  Optional filter, e.g. 'GET', 'POST'.
            path_pattern: Optional URL path substring, e.g. '/api/users'.
            repo_path:    Optional repo root to restrict results.

        Returns:
            List of dicts with keys: method, path, handler, file, line_number.
        """
        conditions = ["fn.http_method IS NOT NULL"]
        params: Dict[str, Any] = {}
        if http_method:
            conditions.append("fn.http_method = $http_method")
            params["http_method"] = http_method.upper()
        if path_pattern:
            conditions.append("fn.http_path CONTAINS $path_pattern")
            params["path_pattern"] = path_pattern
        if repo_path:
            conditions.append("fn.path STARTS WITH $repo_path")
            params["repo_path"] = repo_path

        where = " AND ".join(conditions)
        return self._run(
            f"""
            MATCH (fn:Function)
            WHERE {where}
            RETURN fn.http_method AS method, fn.http_path AS path,
                   fn.name AS handler, fn.path AS file,
                   fn.line_number AS line_number
            ORDER BY fn.http_path, fn.http_method
            LIMIT 100
            """,
            **params,
        )

    def find_beans_by_stereotype(
        self,
        stereotype: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> List[Dict]:
        """Return Spring bean classes, optionally filtered by stereotype.

        Args:
            stereotype: One of CONTROLLER, REST_CONTROLLER, SERVICE,
                        REPOSITORY, COMPONENT, CONFIGURATION.
            repo_path:  Optional repo root to restrict results.

        Returns:
            List of dicts with keys: name, stereotype, file, line_number,
            injection_count.
        """
        conditions = ["c.spring_stereotype IS NOT NULL"]
        params: Dict[str, Any] = {}
        if stereotype:
            conditions.append("c.spring_stereotype = $stereotype")
            params["stereotype"] = stereotype.upper()
        if repo_path:
            conditions.append("c.path STARTS WITH $repo_path")
            params["repo_path"] = repo_path

        where = " AND ".join(conditions)
        return self._run(
            f"""
            MATCH (c:Class)
            WHERE {where}
            OPTIONAL MATCH ()-[:INJECTS]->(c)
            WITH c, count(*) AS injection_count
            RETURN c.name AS name, c.spring_stereotype AS stereotype,
                   c.path AS file, c.line_number AS line_number,
                   injection_count
            ORDER BY stereotype, name
            LIMIT 200
            """,
            **params,
        )

    def find_spring_injection_targets(
        self,
        class_name: str,
        repo_path: Optional[str] = None,
    ) -> List[Dict]:
        """Return all classes that inject *class_name* via @Autowired / @Inject.

        Args:
            class_name: The injected class to look up.
            repo_path:  Optional repo root to restrict results.

        Returns:
            List of dicts with keys: injector, file, field_name, inject_line.
        """
        conditions = ["injected.name = $class_name"]
        params: Dict[str, Any] = {"class_name": class_name}
        if repo_path:
            conditions.append("injector.path STARTS WITH $repo_path")
            params["repo_path"] = repo_path

        where = " AND ".join(conditions)
        return self._run(
            f"""
            MATCH (injector:Class)-[r:INJECTS]->(injected:Class)
            WHERE {where}
            RETURN injector.name AS injector, injector.path AS file,
                   r.field_name AS field_name, r.inject_line AS inject_line
            ORDER BY injector.name
            LIMIT 100
            """,
            **params,
        )

    def find_transactional_methods(
        self,
        repo_path: Optional[str] = None,
    ) -> List[Dict]:
        """Return all @Transactional-annotated functions.

        Args:
            repo_path: Optional repo root to restrict results.

        Returns:
            List of dicts with keys: name, file, line_number.
        """
        conditions = ["fn.transactional = true"]
        params: Dict[str, Any] = {}
        if repo_path:
            conditions.append("fn.path STARTS WITH $repo_path")
            params["repo_path"] = repo_path

        where = " AND ".join(conditions)
        return self._run(
            f"""
            MATCH (fn:Function)
            WHERE {where}
            RETURN fn.name AS name, fn.path AS file,
                   fn.line_number AS line_number
            ORDER BY fn.path, fn.line_number
            LIMIT 200
            """,
            **params,
        )

    def find_maven_module_deps(
        self,
        artifact_id: str,
    ) -> Dict[str, Any]:
        """Return internal and external dependencies of a Maven module.

        Args:
            artifact_id: The Maven artifactId to look up.

        Returns:
            Dict with keys: internal_deps, external_libs.
        """
        internal = self._run(
            """
            MATCH (src:MavenModule {artifact_id: $artifact_id})-[r:MODULE_DEPENDS_ON]->(tgt:MavenModule)
            RETURN tgt.artifact_id AS artifact_id, tgt.group_id AS group_id,
                   tgt.version AS version, r.scope AS scope
            ORDER BY tgt.artifact_id
            """,
            artifact_id=artifact_id,
        )
        external = self._run(
            """
            MATCH (src:MavenModule {artifact_id: $artifact_id})-[r:USES_LIBRARY]->(lib:ExternalLibrary)
            RETURN lib.group_id AS group_id, lib.artifact_id AS artifact_id,
                   lib.version AS version, r.scope AS scope
            ORDER BY lib.artifact_id
            """,
            artifact_id=artifact_id,
        )
        return {"internal_deps": internal, "external_libs": external}

    def find_ambiguous_calls(
        self,
        repo_path: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Return CALLS edges with AMBIGUOUS confidence — potential mis-resolutions.

        Args:
            repo_path: Optional repo root to restrict results.
            limit:     Max rows to return.

        Returns:
            List of dicts with keys: caller, callee, resolution_tier, file.
        """
        conditions = ["c.confidence_label = 'AMBIGUOUS'"]
        params: Dict[str, Any] = {"limit": limit}
        if repo_path:
            conditions.append("caller.path STARTS WITH $repo_path")
            params["repo_path"] = repo_path

        where = " AND ".join(conditions)
        return self._run(
            f"""
            MATCH (caller)-[c:CALLS]->(callee)
            WHERE {where}
            RETURN caller.name AS caller, callee.name AS callee,
                   c.resolution_tier AS resolution_tier, caller.path AS file
            ORDER BY c.resolution_tier DESC
            LIMIT $limit
            """,
            **params,
        )

    # Legacy shim — keeps existing callers working
    def get_cypher_query(self, query: str) -> str:
        raise NotImplementedError(
            "Use find_spring_endpoints(), find_beans_by_stereotype(), etc. instead."
        )
