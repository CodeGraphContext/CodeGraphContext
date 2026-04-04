# src/codegraphcontext/tools/code_finder.py
import logging

from typing import Any, Dict, List, Literal, Optional
from pathlib import Path

from ..core.database import DatabaseManager
from ..utils.path_ignore import cypher_path_not_under_ignore_dirs

logger = logging.getLogger(__name__)

class CodeFinder:
    """Module for finding relevant code snippets and analyzing relationships."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.driver = self.db_manager.get_driver()
        self._is_falkordb = getattr(db_manager, 'get_backend_type', lambda: 'neo4j')() != 'neo4j'

    def format_query(self, find_by: Literal["Class", "Function"], fuzzy_search:bool, repo_path: Optional[str] = None) -> str:
        """Format the search query based on the search type and fuzzy search settings."""
        repo_filter = "AND node.path STARTS WITH $repo_path" if repo_path else ""
        if self._is_falkordb:
            # FalkorDB does not support CALL db.idx.fulltext.queryNodes.
            # Fall back to a pure Cypher CONTAINS/toLower match on node name.
            name_filter = "toLower(node.name) CONTAINS toLower($search_term)"
            return f"""
                MATCH (node:{find_by})
                WHERE {name_filter} {repo_filter}
                RETURN node.name as name, node.path as path, node.line_number as line_number,
                    node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                ORDER BY node.is_dependency ASC, node.name
                LIMIT 20
            """
        return f"""
            CALL db.index.fulltext.queryNodes("code_search_index", $search_term) YIELD node, score
                WITH node, score
                WHERE node:{find_by} {'AND node.name CONTAINS $search_term' if not fuzzy_search else ''} {repo_filter}
                RETURN node.name as name, node.path as path, node.line_number as line_number,
                    node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                ORDER BY score DESC
                LIMIT 20
            """

    def find_by_function_name(self, search_term: str, fuzzy_search: bool, repo_path: Optional[str] = None) -> List[Dict]:
        """Find functions by name matching."""
        with self.driver.session() as session:
            if not fuzzy_search:
                # Use simple match for exact search to avoid fulltext index dependency
                result = session.run(f"""
                    MATCH (node:Function {{name: $name}})
                    {"WHERE node.path STARTS WITH $repo_path" if repo_path else ""}
                    RETURN node.name as name, node.path as path, node.line_number as line_number,
                           node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                    LIMIT 20
                """, name=search_term, repo_path=repo_path)
                return result.data()
            
            # Fuzzy search using fulltext index (Neo4j) or CONTAINS fallback (FalkorDB)
            # On FalkorDB, format_query uses CONTAINS so we pass the raw term; on Neo4j
            # we need the Lucene field-selector prefix.
            formatted_search_term = search_term if self._is_falkordb else f"name:{search_term}"
            result = session.run(self.format_query("Function", fuzzy_search, repo_path), search_term=formatted_search_term, repo_path=repo_path)
            return result.data()

    def find_by_class_name(self, search_term: str, fuzzy_search: bool, repo_path: Optional[str] = None) -> List[Dict]:
        """Find classes by name matching."""
        with self.driver.session() as session:
            if not fuzzy_search:
                # Use simple match for exact search to avoid fulltext index dependency
                result = session.run(f"""
                    MATCH (node:Class {{name: $name}})
                    {"WHERE node.path STARTS WITH $repo_path" if repo_path else ""}
                    RETURN node.name as name, node.path as path, node.line_number as line_number,
                           node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                    LIMIT 20
                """, name=search_term, repo_path=repo_path)
                return result.data()

            # Fuzzy search using fulltext index (Neo4j) or CONTAINS fallback (FalkorDB)
            # On FalkorDB, format_query uses CONTAINS so we pass the raw term; on Neo4j
            # we need the Lucene field-selector prefix.
            formatted_search_term = search_term if self._is_falkordb else f"name:{search_term}"
            result = session.run(self.format_query("Class", fuzzy_search, repo_path), search_term=formatted_search_term, repo_path=repo_path)
            return result.data()

    def find_by_variable_name(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
        """Find variables by name matching"""
        with self.driver.session() as session:
            result = session.run(f"""
                MATCH (v:Variable)
                WHERE v.name CONTAINS $search_term {"AND v.path STARTS WITH $repo_path" if repo_path else ""}
                RETURN v.name as name, v.path as path, v.line_number as line_number,
                       v.value as value, v.context as context, v.is_dependency as is_dependency
                ORDER BY v.is_dependency ASC, v.name
                LIMIT 20
            """, search_term=search_term, repo_path=repo_path)
            
            return result.data()

    def find_by_content(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
        """Find code by content matching in source or docstrings using the full-text index."""
        if self._is_falkordb:
            return self._find_by_content_falkordb(search_term, repo_path)
        with self.driver.session() as session:
            result = session.run(f"""
                CALL db.index.fulltext.queryNodes("code_search_index", $search_term) YIELD node, score
                WITH node, score
                WHERE (node:Function OR node:Class OR node:Variable) {"AND node.path STARTS WITH $repo_path" if repo_path else ""}
                MATCH (node)<-[:CONTAINS]-(f:File)
                RETURN
                    CASE
                        WHEN node:Function THEN 'function'
                        WHEN node:Class THEN 'class'
                        ELSE 'variable'
                    END as type,
                    node.name as name, f.path as path,
                    node.line_number as line_number, node.source as source,
                    node.docstring as docstring, node.is_dependency as is_dependency
                ORDER BY score DESC
                LIMIT 20
            """, search_term=search_term, repo_path=repo_path)
            return result.data()

    def _find_by_content_falkordb(self, search_term: str, repo_path: Optional[str] = None) -> List[Dict]:
        """FalkorDB-compatible content search using pure Cypher CONTAINS matching.
        FalkorDB does not support CALL db.idx.fulltext.queryNodes, so we fall back
        to substring matching on name, source, and docstring fields."""
        all_results = []
        with self.driver.session() as session:
            repo_filter = "AND node.path STARTS WITH $repo_path" if repo_path else ""
            for label, type_name in [('Function', 'function'), ('Class', 'class')]:
                try:
                    result = session.run(f"""
                        MATCH (node:{label})
                        WHERE (toLower(node.name) CONTAINS toLower($search_term)
                            OR (node.source IS NOT NULL AND toLower(node.source) CONTAINS toLower($search_term))
                            OR (node.docstring IS NOT NULL AND toLower(node.docstring) CONTAINS toLower($search_term)))
                            {repo_filter}
                        RETURN
                            '{type_name}' as type,
                            node.name as name, node.path as path,
                            node.line_number as line_number, node.source as source,
                            node.docstring as docstring, node.is_dependency as is_dependency
                        ORDER BY node.is_dependency ASC, node.name
                        LIMIT 20
                    """, search_term=search_term, repo_path=repo_path)
                    all_results.extend(result.data())
                except Exception:
                    logger.debug(f"FalkorDB content query failed for label {label}", exc_info=True)
        return all_results[:20]
    
    def find_by_module_name(self, search_term: str) -> List[Dict]:
        """Find modules by name matching"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Module)
                WHERE m.name CONTAINS $search_term
                RETURN m.name as name, m.lang as lang
                ORDER BY m.name
                LIMIT 20
            """, search_term=search_term)
            return result.data()

    def find_imports(self, search_term: str) -> List[Dict]:
        """Find imported symbols (aliases or original names)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:File)-[r:IMPORTS]->(m:Module)
                WHERE r.alias = $search_term OR r.imported_name = $search_term
                RETURN 
                    r.alias as alias, 
                    r.imported_name as imported_name, 
                    m.name as module_name, 
                    f.path as path, 
                    r.line_number as line_number
                ORDER BY f.path
                LIMIT 20
            """, search_term=search_term)
            return result.data()

    def find_related_code(self, user_query: str, fuzzy_search: bool, edit_distance: int, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Find code related to a query using multiple search strategies"""
        # FalkorDB does not support Lucene-style fuzzy edit-distance syntax (e.g. term~2).
        # On FalkorDB, always use the plain query so that the CONTAINS-based fallbacks work.
        if fuzzy_search and self._is_falkordb:
            logger.debug("FalkorDB backend: ignoring fuzzy edit-distance normalisation; using plain CONTAINS search.")
            fuzzy_search = False

        if fuzzy_search:
            user_query_normalized = " ".join(map(lambda x: f"{x}~{edit_distance}", user_query.split(" ")))
        else:
            user_query_normalized = user_query

        results: Dict[str, Any] = {
            "query": user_query_normalized,
            "functions_by_name": self.find_by_function_name(user_query_normalized, fuzzy_search, repo_path),
            "classes_by_name": self.find_by_class_name(user_query_normalized, fuzzy_search, repo_path),
            "variables_by_name": self.find_by_variable_name(user_query, repo_path),  # no fuzzy for variables as they are not using full-text index
            "content_matches": self.find_by_content(user_query_normalized, repo_path)
        }
        
        all_results: List[Dict[str, Any]] = []
        
        for func in results["functions_by_name"]:
            func["search_type"] = "function_name"
            func["relevance_score"] = 0.9 if not func["is_dependency"] else 0.7
            all_results.append(func)
        
        for cls in results["classes_by_name"]:
            cls["search_type"] = "class_name"
            cls["relevance_score"] = 0.8 if not cls["is_dependency"] else 0.6
            all_results.append(cls)

        for var in results["variables_by_name"]:
            var["search_type"] = "variable_name"
            var["relevance_score"] = 0.7 if not var["is_dependency"] else 0.5
            all_results.append(var)
        
        for content in results["content_matches"]:
            content["search_type"] = "content"
            content["relevance_score"] = 0.6 if not content["is_dependency"] else 0.4
            all_results.append(content)
        
        all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        results["ranked_results"] = all_results[:15]
        results["total_matches"] = len(all_results)
        
        return results
    
    def find_functions_by_argument(self, argument_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find functions that take a specific argument name."""
        with self.driver.session() as session:
            repo_filter = "AND f.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                query = f"""
                    MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)
                    WHERE p.name = $argument_name AND f.path = $path {repo_filter}
                    RETURN f.name AS function_name, f.path AS path, f.line_number AS line_number,
                           f.docstring AS docstring, f.is_dependency AS is_dependency
                    ORDER BY f.is_dependency ASC, f.path, f.line_number
                    LIMIT 20
                """
                result = session.run(query, argument_name=argument_name, path=path, repo_path=repo_path)
            else:
                query = f"""
                    MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)
                    WHERE p.name = $argument_name {repo_filter}
                    RETURN f.name AS function_name, f.path AS path, f.line_number AS line_number,
                           f.docstring AS docstring, f.is_dependency AS is_dependency
                    ORDER BY f.is_dependency ASC, f.path, f.line_number
                    LIMIT 20
                """
                result = session.run(query, argument_name=argument_name, repo_path=repo_path)
            return result.data()

    def find_functions_by_decorator(self, decorator_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find functions that have a specific decorator applied to them."""
        with self.driver.session() as session:
            repo_filter = "AND f.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                query = f"""
                    MATCH (f:Function)
                    WHERE f.path = $path AND $decorator_name IN f.decorators {repo_filter}
                    RETURN f.name AS function_name, f.path AS path, f.line_number AS line_number,
                           f.docstring AS docstring, f.is_dependency AS is_dependency, f.decorators AS decorators
                    ORDER BY f.is_dependency ASC, f.path, f.line_number
                    LIMIT 20
                """
                result = session.run(query, decorator_name=decorator_name, path=path, repo_path=repo_path)
            else:
                query = f"""
                    MATCH (f:Function)
                    WHERE $decorator_name IN f.decorators {repo_filter}
                    RETURN f.name AS function_name, f.path AS path, f.line_number AS line_number,
                           f.docstring AS docstring, f.is_dependency AS is_dependency, f.decorators AS decorators
                    ORDER BY f.is_dependency ASC, f.path, f.line_number
                    LIMIT 20
                """
                result = session.run(query, decorator_name=decorator_name, repo_path=repo_path)
            return result.data()
    
    def who_calls_function(self, function_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find what functions call a specific function using CALLS relationships with improved matching"""
        with self.driver.session() as session:
            repo_filter = "AND caller.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                result = session.run(f"""
                    MATCH (caller)-[call:CALLS]->(target:Function {{name: $function_name, path: $path}})
                    WHERE (caller:Function OR caller:Class OR caller:File) {repo_filter}
                    OPTIONAL MATCH (caller_file:File)-[:CONTAINS]->(caller)
                    RETURN DISTINCT
                        caller.name as caller_function,
                        COALESCE(caller.path, caller_file.path) as caller_file_path,
                        caller.line_number as caller_line_number,
                        caller.docstring as caller_docstring,
                        caller.is_dependency as caller_is_dependency,
                        call.line_number as call_line_number,
                        call.args as call_args,
                        call.full_call_name as full_call_name,
                        target.path as target_file_path
                ORDER BY caller_is_dependency ASC, caller_file_path, caller_line_number
                    LIMIT 20
                """, function_name=function_name, path=path, repo_path=repo_path)
                
                results = result.data()
                if not results:
                    result = session.run(f"""
                        MATCH (caller)-[call:CALLS]->(target:Function {{name: $function_name}})
                        WHERE (caller:Function OR caller:Class OR caller:File) {repo_filter}
                        OPTIONAL MATCH (caller_file:File)-[:CONTAINS]->(caller)
                        RETURN DISTINCT
                            caller.name as caller_function,
                            COALESCE(caller.path, caller_file.path) as caller_file_path,
                            caller.line_number as caller_line_number,
                            caller.docstring as caller_docstring,
                            caller.is_dependency as caller_is_dependency,
                            call.line_number as call_line_number,
                            call.args as call_args,
                            call.full_call_name as full_call_name,
                            target.path as target_file_path
                    ORDER BY caller_is_dependency ASC, caller_file_path, caller_line_number
                        LIMIT 20
                    """, function_name=function_name, repo_path=repo_path)
                    results = result.data()
            else:
                result = session.run(f"""
                    MATCH (caller:Function)-[call:CALLS]->(target:Function {{name: $function_name}})
                    WHERE 1=1 {repo_filter}
                    OPTIONAL MATCH (caller_file:File)-[:CONTAINS]->(caller)
                    RETURN DISTINCT
                        caller.name as caller_function,
                        caller.path as caller_file_path,
                        caller.line_number as caller_line_number,
                        caller.docstring as caller_docstring,
                        caller.is_dependency as caller_is_dependency,
                        call.line_number as call_line_number,
                        call.args as call_args,
                        call.full_call_name as full_call_name,
                        target.path as target_file_path
                ORDER BY caller_is_dependency ASC, caller_file_path, caller_line_number
                    LIMIT 20
                """, function_name=function_name, repo_path=repo_path)
                results = result.data()
            
            return results
    
    def what_does_function_call(self, function_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find what functions a specific function calls using CALLS relationships"""
        with self.driver.session() as session:
            if path:
                # Convert path to absolute path
                absolute_file_path = str(Path(path).resolve())
                result = session.run(f"""
                    MATCH (caller:Function {{name: $function_name, path: $absolute_file_path}})
                    MATCH (caller)-[call:CALLS]->(called:Function)
                    WHERE called.path STARTS WITH $repo_path OR $repo_path IS NULL
                    OPTIONAL MATCH (called_file:File)-[:CONTAINS]->(called)
                    RETURN DISTINCT
                        called.name as called_function,
                        called.path as called_file_path,
                        called.line_number as called_line_number,
                        called.docstring as called_docstring,
                        called.is_dependency as called_is_dependency,
                        call.line_number as call_line_number,
                        call.args as call_args,
                        call.full_call_name as full_call_name
                    ORDER BY called_is_dependency ASC, called_function
                    LIMIT 20
                """, function_name=function_name, absolute_file_path=absolute_file_path, repo_path=repo_path)
            else:
                result = session.run(f"""
                    MATCH (caller:Function {{name: $function_name}})-[call:CALLS]->(called:Function)
                    WHERE called.path STARTS WITH $repo_path OR $repo_path IS NULL
                    OPTIONAL MATCH (called_file:File)-[:CONTAINS]->(called)
                    RETURN DISTINCT
                        called.name as called_function,
                        called.path as called_file_path,
                        called.line_number as called_line_number,
                        called.docstring as called_docstring,
                        called.is_dependency as called_is_dependency,
                        call.line_number as call_line_number,
                        call.args as call_args,
                        call.full_call_name as full_call_name
                    ORDER BY called_is_dependency ASC, called_function
                    LIMIT 20
                """, function_name=function_name, repo_path=repo_path)
            
            return result.data()
    
    def who_imports_module(self, module_name: str, repo_path: Optional[str] = None) -> List[Dict]:
        """Find what files import a specific module using IMPORTS relationships"""
        with self.driver.session() as session:
            repo_filter = "AND file.path STARTS WITH $repo_path" if repo_path else ""
            result = session.run(f"""
                MATCH (file:File)-[imp:IMPORTS]->(module:Module)
                WHERE (module.name = $module_name OR module.full_import_name CONTAINS $module_name) {repo_filter}
                OPTIONAL MATCH (repo:Repository)-[:CONTAINS]->(file)
                WITH file, repo, COLLECT({{
                    imported_module: module.name,
                    import_alias: module.alias,
                    full_import_name: module.full_import_name
                }}) AS imports
                RETURN
                    file.name AS file_name,
                    file.path AS path,
                    file.relative_path AS file_relative_path,
                    file.is_dependency AS file_is_dependency,
                    repo.name AS repository_name,
                    imports
                ORDER BY file.is_dependency ASC, file.path
                LIMIT 20
            """, module_name=module_name, repo_path=repo_path)
            
            return result.data()
    
    def who_modifies_variable(self, variable_name: str, repo_path: Optional[str] = None) -> List[Dict]:
        """Find what functions contain or modify a specific variable"""
        with self.driver.session() as session:
            repo_filter = "AND container.path STARTS WITH $repo_path" if repo_path else ""
            result = session.run(f"""
                MATCH (var:Variable {{name: $variable_name}})
                MATCH (container)-[:CONTAINS]->(var)
                WHERE (container:Function OR container:Class OR container:File) {repo_filter}
                OPTIONAL MATCH (file:File)-[:CONTAINS]->(container)
                RETURN DISTINCT
                    CASE 
                        WHEN container:Function THEN container.name
                        WHEN container:Class THEN container.name
                        ELSE 'file_level'
                    END as container_name,
                    CASE 
                        WHEN container:Function THEN 'function'
                        WHEN container:Class THEN 'class'
                        ELSE 'file'
                    END as container_type,
                    COALESCE(container.path, file.path) as path,
                    container.line_number as container_line_number,
                    var.line_number as variable_line_number,
                    var.value as variable_value,
                    var.context as variable_context,
                    COALESCE(container.is_dependency, file.is_dependency, false) as is_dependency
                ORDER BY is_dependency ASC, path, variable_line_number
                LIMIT 20
            """, variable_name=variable_name, repo_path=repo_path)
            
            return result.data()
    
    def find_class_hierarchy(self, class_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Find class inheritance relationships using INHERITS relationships"""
        with self.driver.session() as session:
            repo_filter = "AND parent.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                match_clause = "MATCH (child:Class {name: $class_name, path: $path})"
            else:
                match_clause = "MATCH (child:Class {name: $class_name})"

            parents_query = f"""
                {match_clause}
                MATCH (child)-[:INHERITS]->(parent:Class)
                WHERE 1=1 {repo_filter}
                OPTIONAL MATCH (parent_file:File)-[:CONTAINS]->(parent)
                RETURN DISTINCT
                    parent.name as parent_class,
                    parent.path as parent_file_path,
                    parent.line_number as parent_line_number,
                    parent.docstring as parent_docstring,
                    parent.is_dependency as parent_is_dependency
                ORDER BY parent_is_dependency ASC, parent_class
            """
            parents_result = session.run(parents_query, class_name=class_name, path=path, repo_path=repo_path)
            
            repo_filter_child = "AND grandchild.path STARTS WITH $repo_path" if repo_path else ""
            children_query = f"""
                {match_clause}
                MATCH (grandchild:Class)-[:INHERITS]->(child)
                WHERE 1=1 {repo_filter_child}
                OPTIONAL MATCH (child_file:File)-[:CONTAINS]->(grandchild)
                RETURN DISTINCT
                    grandchild.name as child_class,
                    grandchild.path as child_file_path,
                    grandchild.line_number as child_line_number,
                    grandchild.docstring as child_docstring,
                    grandchild.is_dependency as child_is_dependency
                ORDER BY child_is_dependency ASC, child_class
            """
            children_result = session.run(children_query, class_name=class_name, path=path, repo_path=repo_path)
            
            repo_filter_method = "WHERE method.path STARTS WITH $repo_path" if repo_path else ""
            methods_query = f"""
                {match_clause}
                MATCH (child)-[:CONTAINS]->(method:Function)
                {repo_filter_method}
                RETURN DISTINCT
                    method.name as method_name,
                    method.path as method_file_path,
                    method.line_number as method_line_number,
                    method.args as method_args,
                    method.docstring as method_docstring,
                    method.is_dependency as method_is_dependency
                ORDER BY method_is_dependency ASC, method_line_number
            """
            methods_result = session.run(methods_query, class_name=class_name, path=path, repo_path=repo_path)
            
            return {
                "class_name": class_name,
                "parent_classes": parents_result.data(),
                "child_classes": children_result.data(),
                "methods": methods_result.data()
            }
    
    def find_function_overrides(self, function_name: str, repo_path: Optional[str] = None) -> List[Dict]:
        """Find all implementations of a function across different classes"""
        with self.driver.session() as session:
            repo_filter = "AND class.path STARTS WITH $repo_path" if repo_path else ""
            result = session.run(f"""
                MATCH (class:Class)-[:CONTAINS]->(func:Function {{name: $function_name}})
                WHERE 1=1 {repo_filter}
                OPTIONAL MATCH (file:File)-[:CONTAINS]->(class)
                RETURN DISTINCT
                    class.name as class_name,
                    class.path as class_file_path,
                    func.name as function_name,
                    func.line_number as function_line_number,
                    func.args as function_args,
                    func.docstring as function_docstring,
                    func.is_dependency as is_dependency,
                    file.name as file_name
                ORDER BY is_dependency ASC, class_name
                LIMIT 20
            """, function_name=function_name, repo_path=repo_path)
            
            return result.data()
    
    def find_dead_code(self, exclude_decorated_with: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Find potentially unused functions (not called by other functions in the project), optionally excluding those with specific decorators."""
        if exclude_decorated_with is None:
            exclude_decorated_with = []

        with self.driver.session() as session:
            repo_filter = "AND func.path STARTS WITH $repo_path" if repo_path else ""
            decorator_filter = "AND ALL(decorator_name IN $exclude_decorated_with WHERE NOT decorator_name IN func.decorators)" if exclude_decorated_with else ""
            func_ignore = cypher_path_not_under_ignore_dirs("func.path")
            caller_ignore = cypher_path_not_under_ignore_dirs("caller.path")
            
            query = f"""
                MATCH (func:Function)
                WHERE func.is_dependency = false {repo_filter} {func_ignore}
                  AND NOT func.name IN ['main', 'setup', 'run']
                  AND NOT (func.name STARTS WITH '__' AND func.name ENDS WITH '__')
                  AND NOT func.name STARTS WITH '_test'
                  AND NOT func.name STARTS WITH 'test_'
                  AND NOT func.name CONTAINS 'main'
                  AND NOT toLower(func.name) CONTAINS 'application'
                  AND NOT toLower(func.name) CONTAINS 'entry'
                  AND NOT toLower(func.name) CONTAINS 'entrypoint'
                  {decorator_filter}
                WITH func
                OPTIONAL MATCH (caller:Function)-[:CALLS]->(func)
                WHERE caller.is_dependency = false {caller_ignore}
                WITH func, count(caller) as caller_count
                WHERE caller_count = 0
                OPTIONAL MATCH (file:File)-[:CONTAINS]->(func)
                RETURN
                    func.name as function_name,
                    func.path as path,
                    func.line_number as line_number,
                    func.docstring as docstring,
                    func.context as context,
                    file.name as file_name
                ORDER BY func.path, func.line_number
                LIMIT 50
            """
            
            params = {}
            if repo_path:
                params["repo_path"] = repo_path
            if exclude_decorated_with:
                params["exclude_decorated_with"] = exclude_decorated_with
                
            result = session.run(query, **params)
            
            return {
                "potentially_unused_functions": result.data(),
                "note": "These functions might be unused, but could be entry points, callbacks, or called dynamically"
            }
    
    def find_all_callers(self, function_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find all direct and indirect callers of a specific function."""
        with self.driver.session() as session:
            repo_filter = "AND f.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                # KùzuDB-compatible: Use anonymous end node and filter with WHERE
                query = f"""
                    MATCH p = (f:Function)-[:CALLS*]->()
                    WITH f as f, p as p, nodes(p) as path_nodes
                    WITH f as f, path_nodes as path_nodes, path_nodes[size(path_nodes)] as target
                    WHERE target.name = $function_name AND target.path = $path {repo_filter}
                    RETURN DISTINCT f.name AS caller_name, f.path AS caller_file_path, f.line_number AS caller_line_number, f.is_dependency AS caller_is_dependency
                    ORDER BY caller_is_dependency ASC, caller_file_path, caller_line_number
                    LIMIT 50
                """
                result = session.run(query, function_name=function_name, path=path, repo_path=repo_path)
            else:
                # KùzuDB-compatible: Use anonymous end node and filter with WHERE
                query = f"""
                    MATCH p = (f:Function)-[:CALLS*]->()
                    WITH f as f, p as p, nodes(p) as path_nodes
                    WITH f as f, path_nodes as path_nodes, path_nodes[size(path_nodes)] as target
                    WHERE target.name = $function_name {repo_filter}
                    RETURN DISTINCT f.name AS caller_name, f.path AS caller_file_path, f.line_number AS caller_line_number, f.is_dependency AS caller_is_dependency
                    ORDER BY caller_is_dependency ASC, caller_file_path, caller_line_number
                    LIMIT 50
                """
                result = session.run(query, function_name=function_name, repo_path=repo_path)
            return result.data()

    def find_all_callees(self, function_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find all direct and indirect callees of a specific function."""
        with self.driver.session() as session:
            repo_filter = "WHERE f.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                # KùzuDB-compatible: Use anonymous end node and extract from path
                query = f"""
                    MATCH (caller:Function {{name: $function_name, path: $path}})
                    MATCH p = (caller)-[:CALLS*]->()
                    WITH p as p, nodes(p) as path_nodes
                    WITH path_nodes[size(path_nodes)] as f
                    {repo_filter}
                    RETURN DISTINCT f.name AS callee_name, f.path AS callee_file_path, f.line_number AS callee_line_number, f.is_dependency AS callee_is_dependency
                    ORDER BY callee_is_dependency ASC, callee_file_path, callee_line_number
                    LIMIT 50
                """
                result = session.run(query, function_name=function_name, path=path, repo_path=repo_path)
            else:
                # KùzuDB-compatible: Use anonymous end node and extract from path
                query = f"""
                    MATCH (caller:Function {{name: $function_name}})
                    MATCH p = (caller)-[:CALLS*]->()
                    WITH p as p, nodes(p) as path_nodes
                    WITH path_nodes[size(path_nodes)] as f
                    {repo_filter}
                    RETURN DISTINCT f.name AS callee_name, f.path AS callee_file_path, f.line_number AS callee_line_number, f.is_dependency AS callee_is_dependency
                    ORDER BY callee_is_dependency ASC, callee_file_path, callee_line_number
                    LIMIT 50
                """
                result = session.run(query, function_name=function_name, repo_path=repo_path)
            return result.data()

    def find_function_call_chain(self, start_function: str, end_function: str, max_depth: int = 5, start_file: Optional[str] = None, end_file: Optional[str] = None, repo_path: Optional[str] = None) -> List[Dict]:
        """Find call chains between two functions"""
        with self.driver.session() as session:
            # Build match clauses based on whether files are specified
            start_props = "{name: $start_function" + (", path: $start_file}" if start_file else "}")
            end_props = "{name: $end_function" + (", path: $end_file}" if end_file else "}")

            # KùzuDB-compatible: Use anonymous end node and filter
            repo_filter = "WHERE 1=1 AND (start.path IS NULL OR start.path STARTS WITH $repo_path) AND (end_target.path IS NULL OR end_target.path STARTS WITH $repo_path)" if repo_path else ""
            query = f"""
                MATCH (start:Function {start_props}), (end_target:Function {end_props})
                {repo_filter}
                WITH start as start, end_target as end_target
                MATCH path = (start)-[:CALLS*1..{max_depth}]->()
                WITH path as path, end_target as end_target, nodes(path) as func_nodes, relationships(path) as call_rels
                WITH path as path, func_nodes as func_nodes, call_rels as call_rels, end_target as end_target, func_nodes[size(func_nodes)] as path_end
                WHERE path_end.name = end_target.name AND (end_target.path IS NULL OR path_end.path = end_target.path)
                RETURN func_nodes as function_nodes, call_rels as call_nodes, size(call_rels) as chain_length
                ORDER BY chain_length ASC
                LIMIT 20
            """
            
            # Prepare parameters
            params = {
                "start_function": start_function,
                "end_function": end_function,
                "start_file": start_file,
                "end_file": end_file,
                "repo_path": repo_path
            }
            
            result = session.run(query, **params)

            # Post-process Node/Rel objects into plain dicts so CLI output stays stable
            rows = result.data()
            transformed: List[Dict[str, Any]] = []
            for row in rows:
                func_nodes = row.get("function_nodes") or []
                rel_nodes = row.get("call_nodes") or []
                chain_len = row.get("chain_length", 0)

                function_chain = []
                for n in func_nodes:
                    # Depending on KùzuDB + driver wrapping, list elements can arrive
                    # either as Node/Rel objects or already-materialized dicts.
                    if isinstance(n, dict):
                        props = n
                    else:
                        props = None
                        try:
                            props = n.get_properties()
                        except Exception:
                            props = getattr(n, "properties", None)
                        if props is None:
                            props = {}
                    function_chain.append(
                        {
                            "name": props.get("name"),
                            "path": props.get("path"),
                            "line_number": props.get("line_number"),
                            "is_dependency": props.get("is_dependency"),
                        }
                    )

                call_details = []
                for r in rel_nodes:
                    if isinstance(r, dict):
                        props = r
                    else:
                        props = None
                        try:
                            props = r.get_properties()
                        except Exception:
                            props = getattr(r, "properties", None)
                        if props is None:
                            props = {}
                    call_details.append(
                        {
                            "call_line": props.get("line_number"),
                            "args": props.get("args"),
                            "full_call_name": props.get("full_call_name"),
                        }
                    )

                transformed.append(
                    {
                        "function_chain": function_chain,
                        "call_details": call_details,
                        "chain_length": chain_len,
                    }
                )

            return transformed

    def find_by_type(self, element_type: str, limit: int = 50) -> List[Dict]:
        """Find all elements of a specific type (Function, Class, File, Module)."""
        # Map input type to node label
        type_map = {
            "function": "Function",
            "class": "Class",
            "file": "File",
            "module": "Module"
        }
        label = type_map.get(element_type.lower())
        
        if not label:
            return []
            
        with self.driver.session() as session:
            if label == "File":
                query = f"""
                    MATCH (n:File)
                    RETURN n.name as name, n.path as path, n.is_dependency as is_dependency
                    ORDER BY n.path
                    LIMIT $limit
                """
            elif label == "Module":
                query = f"""
                    MATCH (n:Module)
                    RETURN n.name as name, n.name as path, false as is_dependency
                    ORDER BY n.name
                    LIMIT $limit
                """
            else:
                query = f"""
                    MATCH (n:{label})
                    RETURN n.name as name, n.path as path, n.line_number as line_number, n.is_dependency as is_dependency
                    ORDER BY is_dependency ASC, name
                    LIMIT $limit
                """
            
            result = session.run(query, limit=limit)
            return result.data()
    
    def find_module_dependencies(self, module_name: str, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Find all dependencies and dependents of a module"""
        with self.driver.session() as session:
            repo_filter = "AND file.path STARTS WITH $repo_path" if repo_path else ""
            # Find files that import this module (who imports this module)
            importers_result = session.run(f"""
                MATCH (file:File)-[imp:IMPORTS]->(module:Module {{name: $module_name}})
                WHERE 1=1 {repo_filter}
                OPTIONAL MATCH (repo:Repository)-[:CONTAINS]->(file)
                RETURN DISTINCT
                    file.path as importer_file_path,
                    imp.line_number as import_line_number,
                    file.is_dependency as file_is_dependency,
                    repo.name as repository_name
                ORDER BY file.is_dependency ASC, file.path
                LIMIT 50
            """, module_name=module_name, repo_path=repo_path)
            
            # Find modules that are imported by files that also import the target module
            # This helps understand what this module is typically used with
            imports_result = session.run(f"""
                MATCH (file:File)-[:IMPORTS]->(target_module:Module {{name: $module_name}})
                MATCH (file)-[imp:IMPORTS]->(other_module:Module)
                WHERE other_module <> target_module {repo_filter}
                RETURN DISTINCT
                    other_module.name as imported_module,
                    imp.alias as import_alias
                ORDER BY other_module.name
                LIMIT 50
            """, module_name=module_name, repo_path=repo_path)
            
            return {
                "module_name": module_name,
                "importers": importers_result.data(),
                "imports": imports_result.data()
            }
    
    def find_variable_usage_scope(self, variable_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Find the scope and usage patterns of a variable, optional file path filtering"""
        with self.driver.session() as session:
            repo_filter = "AND var.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                variable_instances = session.run(f"""
                    MATCH (var:Variable {{name: $variable_name}})
                    WHERE (var.path ENDS WITH $path OR var.path = $path) {repo_filter}
                    OPTIONAL MATCH (container)-[:CONTAINS]->(var)
                    WHERE container:Function OR container:Class OR container:File
                    OPTIONAL MATCH (file:File)-[:CONTAINS]->(var)
                    RETURN DISTINCT
                        var.name as variable_name,
                        var.value as variable_value,
                        var.line_number as line_number,
                        var.context as context,
                        COALESCE(var.path, file.path) as path,
                        CASE 
                        WHEN container:Function THEN 'function'
                        WHEN container:Class THEN 'class'
                        ELSE 'module'
                    END as scope_type,
                    CASE 
                        WHEN container:Function THEN container.name
                        WHEN container:Class THEN container.name
                        ELSE 'module_level'
                    END as scope_name,
                    var.is_dependency as is_dependency
                ORDER BY var.is_dependency ASC, path, line_number
            """, variable_name=variable_name, path=path, repo_path=repo_path)
            else:
                variable_instances = session.run(f"""
                    MATCH (var:Variable {{name: $variable_name}})
                    WHERE 1=1 {repo_filter}
                    OPTIONAL MATCH (container)-[:CONTAINS]->(var)
                    WHERE container:Function OR container:Class OR container:File
                    OPTIONAL MATCH (file:File)-[:CONTAINS]->(var)
                    RETURN DISTINCT
                        var.name as variable_name,
                        var.value as variable_value,
                        var.line_number as line_number,
                        var.context as context,
                        COALESCE(var.path, file.path) as path,
                        CASE 
                            WHEN container:Function THEN 'function'
                            WHEN container:Class THEN 'class'
                            ELSE 'module'
                        END as scope_type,
                        CASE 
                            WHEN container:Function THEN container.name
                            WHEN container:Class THEN container.name
                            ELSE 'module_level'
                        END as scope_name,
                        var.is_dependency as is_dependency
                    ORDER BY var.is_dependency ASC, path, line_number
                """, variable_name=variable_name, repo_path=repo_path)
            
            return {
                "variable_name": variable_name,
                "instances": variable_instances.data()
            }
    
    def analyze_code_relationships(self, query_type: str, target: str, context: Optional[str] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Main method to analyze different types of code relationships with fixed return types"""
        query_type = query_type.lower().strip()
        
        try:
            if query_type == "find_callers":
                results = self.who_calls_function(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_callers", "target": target, "context": context, "results": results,
                    "summary": f"Found {len(results)} functions that call '{target}'"
                }
            
            elif query_type == "find_callees":
                results = self.what_does_function_call(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_callees", "target": target, "context": context, "results": results,
                    "summary": f"Function '{target}' calls {len(results)} other functions"
                }
                
            elif query_type == "find_importers":
                results = self.who_imports_module(target, repo_path=repo_path)
                return {
                    "query_type": "find_importers", "target": target, "results": results,
                    "summary": f"Found {len(results)} files that import '{target}'"
                }
                
            elif query_type == "find_functions_by_argument":
                results = self.find_functions_by_argument(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_functions_by_argument", "target": target, "context": context, "results": results,
                    "summary": f"Found {len(results)} functions that take '{target}' as an argument"
                }
            
            elif query_type == "find_functions_by_decorator":
                results = self.find_functions_by_decorator(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_functions_by_decorator", "target": target, "context": context, "results": results,
                    "summary": f"Found {len(results)} functions decorated with '{target}'"
                }
                
            elif query_type in ["who_modifies", "modifies", "mutations", "changes", "variable_usage"]:
                results = self.who_modifies_variable(target, repo_path=repo_path)
                return {
                    "query_type": "who_modifies", "target": target, "results": results,
                    "summary": f"Found {len(results)} containers that hold variable '{target}'"
                }
            
            elif query_type in ["class_hierarchy", "inheritance", "extends"]:
                results = self.find_class_hierarchy(target, context, repo_path=repo_path)
                return {
                    "query_type": "class_hierarchy", "target": target, "results": results,
                    "summary": f"Class '{target}' has {len(results['parent_classes'])} parents, {len(results['child_classes'])} children, and {len(results['methods'])} methods"
                }
            
            elif query_type in ["overrides", "implementations", "polymorphism"]:
                results = self.find_function_overrides(target, repo_path=repo_path)
                return {
                    "query_type": "overrides", "target": target, "results": results,
                    "summary": f"Found {len(results)} implementations of function '{target}'"
                }
            
            elif query_type in ["dead_code", "unused", "unreachable"]:
                results = self.find_dead_code(repo_path=repo_path)
                return {
                    "query_type": "dead_code", "results": results,
                    "summary": f"Found {len(results['potentially_unused_functions'])} potentially unused functions"
                }
            
            elif query_type == "find_complexity":
                limit = int(context) if context and context.isdigit() else 10
                results = self.find_most_complex_functions(limit, repo_path=repo_path)
                return {
                    "query_type": "find_complexity", "limit": limit, "results": results,
                    "summary": f"Found the top {len(results)} most complex functions"
                }
            
            elif query_type == "find_all_callers":
                results = self.find_all_callers(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_all_callers", "target": target, "context": context, "results": results,
                    "summary": f"Found {len(results)} direct and indirect callers of '{target}'"
                }

            elif query_type == "find_all_callees":
                results = self.find_all_callees(target, context, repo_path=repo_path)
                return {
                    "query_type": "find_all_callees", "target": target, "context": context, "results": results,
                    "summary": f"Found {len(results)} direct and indirect callees of '{target}'"
                }
                
            elif query_type in ["call_chain", "path", "chain"]:
                if '->' in target:
                    start_func, end_func = target.split('->', 1)
                    # max_depth can be passed as context, default to 5 if not provided or invalid
                    max_depth = int(context) if context and context.isdigit() else 5
                    results = self.find_function_call_chain(start_func.strip(), end_func.strip(), max_depth, repo_path=repo_path)
                    return {
                        "query_type": "call_chain", "target": target, "results": results,
                        "summary": f"Found {len(results)} call chains from '{start_func.strip()}' to '{end_func.strip()}' (max depth: {max_depth})"
                    }
                else:
                    return {
                        "error": "For call_chain queries, use format 'start_function->end_function'",
                        "example": "main->process_data"
                    }
            
            elif query_type in ["module_deps", "module_dependencies", "module_usage"]:
                results = self.find_module_dependencies(target, repo_path=repo_path)
                return {
                    "query_type": "module_dependencies", "target": target, "results": results,
                    "summary": f"Module '{target}' is imported by {len(results['imported_by_files'])} files"
                }
            
            elif query_type in ["variable_scope", "var_scope", "variable_usage_scope"]:
                results = self.find_variable_usage_scope(target, repo_path=repo_path)
                return {
                    "query_type": "variable_scope", "target": target, "results": results,
                    "summary": f"Variable '{target}' has {len(results['instances'])} instances across different scopes"
                }
            
            else:
                return {
                    "error": f"Unknown query type: {query_type}",
                    "supported_types": [
                        "find_callers", "find_callees", "find_importers", "who_modifies",
                        "class_hierarchy", "overrides", "dead_code", "call_chain",
                        "module_deps", "variable_scope", "find_complexity"
                    ]
                }
        
        except Exception as e:
            return {
                "error": f"Error executing relationship query: {str(e)}",
                "query_type": query_type,
                "target": target
            }

    def get_cyclomatic_complexity(self, function_name: str, path: Optional[str] = None, repo_path: Optional[str] = None) -> Optional[Dict]:
        """Get the cyclomatic complexity of a function."""
        with self.driver.session() as session:
            repo_filter = "AND f.path STARTS WITH $repo_path" if repo_path else ""
            if path:
                # Use ENDS WITH for flexible path matching, or exact match
                query = f"""
                    MATCH (f:Function {{name: $function_name}})
                    WHERE (f.path ENDS WITH $path OR f.path = $path) {repo_filter}
                    RETURN f.name as function_name, f.cyclomatic_complexity as complexity,
                           f.path as path, f.line_number as line_number
                """
                result = session.run(query, function_name=function_name, path=path, repo_path=repo_path)
            else:
                query = f"""
                    MATCH (f:Function {{name: $function_name}})
                    WHERE 1=1 {repo_filter}
                    RETURN f.name as function_name, f.cyclomatic_complexity as complexity,
                           f.path as path, f.line_number as line_number
                """
                result = session.run(query, function_name=function_name, repo_path=repo_path)
            
            result_data = result.data()
            if result_data:
                return result_data[0]
            return None

    def find_most_complex_functions(self, limit: int = 10, repo_path: Optional[str] = None) -> List[Dict]:
        """Find the most complex functions based on cyclomatic complexity."""
        with self.driver.session() as session:
            repo_filter = "AND f.path STARTS WITH $repo_path" if repo_path else ""
            path_ignore = cypher_path_not_under_ignore_dirs("f.path")
            query = f"""
                MATCH (f:Function)
                WHERE f.cyclomatic_complexity IS NOT NULL AND f.is_dependency = false {repo_filter} {path_ignore}
                RETURN f.name as function_name, f.path as path, f.cyclomatic_complexity as complexity, f.line_number as line_number
                ORDER BY f.cyclomatic_complexity DESC
                LIMIT $limit
            """
            result = session.run(query, limit=limit, repo_path=repo_path)
            return result.data()

    def list_indexed_repositories(self) -> List[Dict]:
        """List all indexed repositories."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Repository)
                RETURN r.name as name, r.path as path, r.is_dependency as is_dependency
                ORDER BY r.name
            """)
            return result.data()
