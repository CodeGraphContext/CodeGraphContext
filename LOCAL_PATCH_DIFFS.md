# Unified Diffs (Installed Package -> Fork Source)

--- src/codegraphcontext/server.py
+++ /workspace/.venv-mcp/lib/python3.12/site-packages/codegraphcontext/server.py
@@ -12,7 +12,7 @@
 from pathlib import Path
 from dataclasses import asdict
 
-from typing import Any, Dict, Coroutine, Optional, List
+from typing import Any, Dict, Coroutine, Optional, List, Tuple
 
 from .prompts import LLM_SYSTEM_PROMPT
 from .core import get_database_manager
@@ -247,6 +247,49 @@
         else:
             return {"error": f"Unknown tool: {tool_name}"}
 
+    def _read_request_blocking(self) -> Tuple[Optional[dict], Optional[str]]:
+        """Read one request from stdin supporting MCP framing and legacy line JSON-RPC."""
+        stdin_buffer = sys.stdin.buffer
+        first = stdin_buffer.readline()
+        if not first:
+            return None, None
+
+        first_str = first.decode("utf-8", errors="replace")
+        if first_str.lower().startswith("content-length:"):
+            try:
+                content_length = int(first_str.split(":", 1)[1].strip())
+            except Exception as exc:
+                raise ValueError(f"Invalid Content-Length header: {first_str.strip()}") from exc
+
+            # Consume all remaining headers up to the blank line.
+            while True:
+                header_line = stdin_buffer.readline()
+                if not header_line:
+                    return None, None
+                if header_line in (b"\r\n", b"\n", b""):
+                    break
+
+            body = stdin_buffer.read(content_length)
+            if len(body) < content_length:
+                return None, None
+            return json.loads(body.decode("utf-8")), "mcp"
+
+        # Fallback: line-delimited JSON-RPC.
+        line = first_str.strip()
+        if not line:
+            return None, "line"
+        return json.loads(line), "line"
+
+    def _write_response(self, response: dict, framing: Optional[str]) -> None:
+        """Write response using the same framing as the request."""
+        if framing == "mcp":
+            payload = json.dumps(response).encode("utf-8")
+            sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
+            sys.stdout.buffer.write(payload)
+            sys.stdout.buffer.flush()
+        else:
+            print(json.dumps(response), flush=True)
+
     async def run(self):
         """
         Runs the main server loop, listening for JSON-RPC requests from stdin.
@@ -258,13 +301,12 @@
         loop = asyncio.get_event_loop()
         while True:
             try:
-                # Read a request from the standard input.
-                line = await loop.run_in_executor(None, sys.stdin.readline)
-                if not line:
+                # Read a request from standard input.
+                request, framing = await loop.run_in_executor(None, self._read_request_blocking)
+                if request is None:
                     debug_logger("Client disconnected (EOF received). Shutting down.")
                     break
-                
-                request = json.loads(line.strip())
+
                 method = request.get('method')
                 params = request.get('params', {})
                 request_id = request.get('id')
@@ -319,7 +361,7 @@
                 
                 # Send the response to standard output if it's not a notification.
                 if request_id is not None and response:
-                    print(json.dumps(response), flush=True)
+                    self._write_response(response, framing)
 
             except Exception as e:
                 error_logger(f"Error processing request: {e}\n{traceback.format_exc()}")
@@ -331,7 +373,7 @@
                     "jsonrpc": "2.0", "id": request_id,
                     "error": {"code": -32603, "message": f"Internal error: {str(e)}", "data": traceback.format_exc()}
                 }
-                print(json.dumps(error_response), flush=True)
+                self._write_response(error_response, locals().get("framing"))
 
     def shutdown(self):
         """Gracefully shuts down the server and its components."""

--- src/codegraphcontext/tools/graph_builder.py
+++ /workspace/.venv-mcp/lib/python3.12/site-packages/codegraphcontext/tools/graph_builder.py
@@ -182,6 +182,30 @@
         # When adding a new node type with a unique key, add its constraint here.
         with self.driver.session() as session:
             try:
+                backend_type = getattr(self.db_manager, 'get_backend_type', lambda: 'neo4j')()
+
+                # KuzuDB has its own schema/index lifecycle in database_kuzu.py.
+                # Here we only ensure FTS indexes used by find_code are present.
+                if backend_type == 'kuzudb':
+                    kuzu_fts_indexes = [
+                        ("Function", "function_code_search_fts", "['name', 'source', 'docstring']"),
+                        ("Class", "class_code_search_fts", "['name', 'source', 'docstring']"),
+                        ("Variable", "variable_code_search_fts", "['name', 'source', 'docstring']"),
+                    ]
+                    for table_name, index_name, fields in kuzu_fts_indexes:
+                        try:
+                            session.run(
+                                f"CALL CREATE_FTS_INDEX('{table_name}', '{index_name}', {fields})"
+                            )
+                        except Exception as e:
+                            # Idempotent behavior: ignore "already exists", report everything else.
+                            if "already exists" not in str(e).lower():
+                                warning_logger(
+                                    f"Kuzu FTS index creation warning for {table_name}.{index_name}: {e}"
+                                )
+                    info_logger("KuzuDB FTS indexes verified/created successfully")
+                    return
+
                 session.run("CREATE CONSTRAINT repository_path IF NOT EXISTS FOR (r:Repository) REQUIRE r.path IS UNIQUE")
                 session.run("CREATE CONSTRAINT path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
                 session.run("CREATE CONSTRAINT directory_path IF NOT EXISTS FOR (d:Directory) REQUIRE d.path IS UNIQUE")
@@ -204,7 +228,7 @@
                 session.run("CREATE INDEX class_lang IF NOT EXISTS FOR (c:Class) ON (c.lang)")
                 session.run("CREATE INDEX annotation_lang IF NOT EXISTS FOR (a:Annotation) ON (a.lang)")
                 
-                is_falkordb = getattr(self.db_manager, 'get_backend_type', lambda: 'neo4j')() != 'neo4j'
+                is_falkordb = backend_type in ('falkordb', 'falkordb-remote')
                 if is_falkordb:
                     # FalkorDB uses db.idx.fulltext.createNodeIndex per label
                     for label in ['Function', 'Class']:

--- src/codegraphcontext/tools/code_finder.py
+++ /workspace/.venv-mcp/lib/python3.12/site-packages/codegraphcontext/tools/code_finder.py
@@ -15,12 +15,121 @@
     def __init__(self, db_manager: DatabaseManager):
         self.db_manager = db_manager
         self.driver = self.db_manager.get_driver()
-        self._is_falkordb = getattr(db_manager, 'get_backend_type', lambda: 'neo4j')() != 'neo4j'
+        self._backend_type = getattr(db_manager, 'get_backend_type', lambda: 'neo4j')()
+        self._is_neo4j = self._backend_type == 'neo4j'
+        self._is_kuzu = self._backend_type == 'kuzudb'
+        self._is_falkordb = self._backend_type in ('falkordb', 'falkordb-remote')
+        self._kuzu_fts_index_by_label = {
+            "Function": "function_code_search_fts",
+            "Class": "class_code_search_fts",
+            "Variable": "variable_code_search_fts",
+        }
+        if self._is_kuzu:
+            self._ensure_kuzu_fts_indexes()
+
+    def _ensure_kuzu_fts_indexes(self) -> None:
+        """Best-effort Kuzu FTS index bootstrap for code search."""
+        with self.driver.session() as session:
+            existing: set[tuple[str, str]] = set()
+            try:
+                for row in session.run("CALL SHOW_INDEXES() RETURN *").data():
+                    table_name = row.get("table_name")
+                    index_name = row.get("index_name")
+                    if table_name and index_name:
+                        existing.add((str(table_name), str(index_name)))
+            except Exception:
+                logger.debug("Failed to inspect existing Kuzu indexes", exc_info=True)
+
+            for label, index_name in self._kuzu_fts_index_by_label.items():
+                if (label, index_name) in existing:
+                    continue
+                try:
+                    session.run(
+                        f"CALL CREATE_FTS_INDEX('{label}', '{index_name}', ['name', 'source', 'docstring'])"
+                    )
+                except Exception as e:
+                    if "already exists" not in str(e).lower():
+                        logger.warning(
+                            "Kuzu FTS bootstrap failed for %s.%s: %s",
+                            label,
+                            index_name,
+                            e,
+                        )
+
+    @staticmethod
+    def _extract_node_path(node: Any) -> Optional[str]:
+        if isinstance(node, dict):
+            return node.get("path")
+        return None
+
+    def _query_kuzu_fts(self, label: str, search_term: str, repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
+        """Run QUERY_FTS_INDEX for a given label, with graceful fallback if index is missing."""
+        index_name = self._kuzu_fts_index_by_label.get(label)
+        if not index_name:
+            return []
+
+        with self.driver.session() as session:
+            try:
+                rows = session.run(
+                    f"CALL QUERY_FTS_INDEX('{label}', '{index_name}', $search_term) RETURN node, score LIMIT 200",
+                    search_term=search_term,
+                ).data()
+                if repo_path:
+                    rows = [
+                        row for row in rows
+                        if (self._extract_node_path(row.get("node")) or "").startswith(repo_path)
+                    ]
+                return rows
+            except Exception as e:
+                # Index might not exist yet (fresh DB) or extension might be unavailable.
+                logger.debug("Kuzu FTS query failed for %s: %s", label, e, exc_info=True)
+                return []
+
+    def _kuzu_name_search_fallback(self, label: str, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
+        """Fallback CONTAINS search for Kuzu when FTS is unavailable."""
+        repo_filter = "AND node.path STARTS WITH $repo_path" if repo_path else ""
+        with self.driver.session() as session:
+            result = session.run(
+                f"""
+                    MATCH (node:{label})
+                    WHERE toLower(node.name) CONTAINS toLower($search_term) {repo_filter}
+                    RETURN node.name as name, node.path as path, node.line_number as line_number,
+                        node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
+                    ORDER BY node.is_dependency ASC, node.name
+                    LIMIT 20
+                """,
+                search_term=search_term,
+                repo_path=repo_path,
+            )
+            return result.data()
+
+    def _kuzu_find_by_label_name(self, label: str, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
+        """Kuzu-native name search using FTS results projected to CodeFinder shape."""
+        rows = self._query_kuzu_fts(label, search_term, repo_path=repo_path)
+        if not rows:
+            return self._kuzu_name_search_fallback(label, search_term, repo_path)
+
+        projected: List[Dict[str, Any]] = []
+        for row in rows:
+            node = row.get("node")
+            if not isinstance(node, dict):
+                continue
+            projected.append({
+                "name": node.get("name"),
+                "path": node.get("path"),
+                "line_number": node.get("line_number"),
+                "source": node.get("source"),
+                "docstring": node.get("docstring"),
+                "is_dependency": node.get("is_dependency"),
+            })
+            if len(projected) >= 20:
+                break
+        return projected
 
     def format_query(self, find_by: Literal["Class", "Function"], fuzzy_search:bool, repo_path: Optional[str] = None) -> str:
         """Format the search query based on the search type and fuzzy search settings."""
         repo_filter = "AND node.path STARTS WITH $repo_path" if repo_path else ""
-        if self._is_falkordb:
+        if self._is_falkordb or self._is_kuzu:
             # FalkorDB does not support CALL db.idx.fulltext.queryNodes.
             # Fall back to a pure Cypher CONTAINS/toLower match on node name.
             name_filter = "toLower(node.name) CONTAINS toLower($search_term)"
@@ -54,8 +163,15 @@
                            node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                     LIMIT 20
                 """, name=search_term, repo_path=repo_path)
-                return result.data()
-            
+                exact = result.data()
+                if exact or not self._is_kuzu:
+                    return exact
+                # For Kuzu, fall back to FTS when exact match misses.
+                return self._kuzu_find_by_label_name("Function", search_term, repo_path)
+            
+            if self._is_kuzu:
+                return self._kuzu_find_by_label_name("Function", search_term, repo_path)
+
             # Fuzzy search using fulltext index (Neo4j) or CONTAINS fallback (FalkorDB)
             # On FalkorDB, format_query uses CONTAINS so we pass the raw term; on Neo4j
             # we need the Lucene field-selector prefix.
@@ -75,7 +191,14 @@
                            node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                     LIMIT 20
                 """, name=search_term, repo_path=repo_path)
-                return result.data()
+                exact = result.data()
+                if exact or not self._is_kuzu:
+                    return exact
+                # For Kuzu, fall back to FTS when exact match misses.
+                return self._kuzu_find_by_label_name("Class", search_term, repo_path)
+
+            if self._is_kuzu:
+                return self._kuzu_find_by_label_name("Class", search_term, repo_path)
 
             # Fuzzy search using fulltext index (Neo4j) or CONTAINS fallback (FalkorDB)
             # On FalkorDB, format_query uses CONTAINS so we pass the raw term; on Neo4j
@@ -100,6 +223,8 @@
 
     def find_by_content(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
         """Find code by content matching in source or docstrings using the full-text index."""
+        if self._is_kuzu:
+            return self._find_by_content_kuzu(search_term, repo_path)
         if self._is_falkordb:
             return self._find_by_content_falkordb(search_term, repo_path)
         with self.driver.session() as session:
@@ -121,6 +246,35 @@
                 LIMIT 20
             """, search_term=search_term, repo_path=repo_path)
             return result.data()
+
+    def _find_by_content_kuzu(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
+        """Kuzu-native content search backed by FTS indexes across Function/Class/Variable."""
+        all_rows: List[Dict[str, Any]] = []
+        for label, type_name in [("Function", "function"), ("Class", "class"), ("Variable", "variable")]:
+            rows = self._query_kuzu_fts(label, search_term, repo_path=repo_path)
+            for row in rows:
+                node = row.get("node")
+                if not isinstance(node, dict):
+                    continue
+                all_rows.append({
+                    "type": type_name,
+                    "name": node.get("name"),
+                    "path": node.get("path"),
+                    "line_number": node.get("line_number"),
+                    "source": node.get("source"),
+                    "docstring": node.get("docstring"),
+                    "is_dependency": node.get("is_dependency"),
+                    "_score": row.get("score", 0.0),
+                })
+
+        if not all_rows:
+            return self._find_by_content_falkordb(search_term, repo_path)
+
+        all_rows.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
+        trimmed = all_rows[:20]
+        for row in trimmed:
+            row.pop("_score", None)
+        return trimmed
 
     def _find_by_content_falkordb(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
         """FalkorDB-compatible content search using pure Cypher CONTAINS matching.
@@ -183,8 +337,8 @@
         """Find code related to a query using multiple search strategies"""
         # FalkorDB does not support Lucene-style fuzzy edit-distance syntax (e.g. term~2).
         # On FalkorDB, always use the plain query so that the CONTAINS-based fallbacks work.
-        if fuzzy_search and self._is_falkordb:
-            logger.debug("FalkorDB backend: ignoring fuzzy edit-distance normalisation; using plain CONTAINS search.")
+        if fuzzy_search and (self._is_falkordb or self._is_kuzu):
+            logger.debug("%s backend: ignoring Lucene fuzzy normalisation; using backend-native search.", self._backend_type)
             fuzzy_search = False
 
         if fuzzy_search:

