# src/codegraphcontext/core/cgc_bundle.py
"""
This module handles the creation and loading of .cgc (CodeGraphContext Bundle) files.

A .cgc file is a portable, pre-indexed graph snapshot that can be distributed and loaded
instantly without re-indexing. This enables:
- Pre-indexing famous repositories once
- Distributing graph knowledge as artifacts
- Instant context loading for LLMs
- Version-controlled code knowledge

Bundle Structure:
    .cgc (ZIP archive)
    ├── metadata.json       # Repository and indexing metadata
    ├── schema.json         # Graph schema definition
    ├── nodes.jsonl         # All nodes (one JSON object per line)
    ├── edges.jsonl         # All relationships (one JSON object per line)
    ├── stats.json          # Graph statistics
    └── README.md           # Human-readable description
"""

import json
import os
import re
import zipfile
import tempfile
import hashlib
import hmac
import base64
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
import subprocess

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.git_utils import get_repo_commit_hash, get_repo_branch_name


class _BundleEncoder(json.JSONEncoder):
    """Handles Neo4j DateTime and other non-standard types for bundle serialization."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, 'iso_format'):
            return obj.iso_format()
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        return super().default(obj)


#: Cypher identifiers accepted from a bundle. Labels and relationship types
#: cannot be passed as query parameters — they are interpolated into the query
#: text — so a bundle is an untrusted source of executable Cypher unless every
#: identifier is validated first. A bundle carrying the label
#:     Evil) WITH n MATCH (v:Victim) DETACH DELETE v //
#: previously produced, and executed:
#:     CREATE (n:Evil) WITH n MATCH (v:Victim) DETACH DELETE v //) SET n = $props ...
_CYPHER_IDENTIFIER_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")


class BundleValidationError(ValueError):
    """Raised when a bundle contains content that is unsafe to import."""


def _validate_cypher_identifier(value: Any, kind: str) -> str:
    """Return *value* if it is a bare Cypher identifier, else raise."""
    if not isinstance(value, str) or not _CYPHER_IDENTIFIER_RE.match(value):
        raise BundleValidationError(
            f"Refusing to import bundle: invalid {kind} {value!r}. "
            f"{kind.capitalize()}s must match [A-Za-z_][A-Za-z0-9_]* — a value "
            "outside that set can inject arbitrary Cypher."
        )
    return value


class CGCBundle:
    """Handles creation and loading of .cgc bundle files."""

    VERSION = "0.1.0"  # CGC bundle format version
    
    def __init__(self, db_manager):
        """
        Initialize the CGC Bundle handler.

        Args:
            db_manager: DatabaseManager instance for graph queries
        """
        self.db_manager = db_manager
        self._active_graph = None
    
    def _get_id_function(self) -> str:
        """
        Get the appropriate ID function based on the database backend.
        
        Returns:
            str: 'elementId' for Neo4j, 'id' for FalkorDB
        """
        backend = self.db_manager.get_backend_type()
        if backend == 'neo4j':
            return 'elementId'
        return 'id'

    def _uses_pk_edge_matching(self) -> bool:
        """Kùzu/Ladybug internal IDs are not comparable via id() in MATCH."""
        return self.db_manager.get_backend_type() in {'kuzudb', 'ladybugdb'}

    def _node_lookup_key(self, labels, properties: Dict) -> Optional[tuple]:
        if not labels:
            return None
        if isinstance(labels, str):
            labels = [labels]
        primary_label = labels[0]
        pk_field = self._PK_MAP.get(primary_label)
        if pk_field and pk_field in properties:
            return (primary_label, pk_field, properties[pk_field])
        return None

    
    def export_to_bundle(
        self,
        output_path: Path,
        repo_path: Optional[Path] = None,
        include_stats: bool = True,
        sign_key: Optional[str] = None,
        encrypt_password: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Export the current graph (or a specific repository) to a .cgc bundle.
        
        Args:
            output_path: Path where the .cgc file should be saved
            repo_path: Optional specific repository path to export (None = export all)
            include_stats: Whether to include detailed statistics
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            info_logger(f"Starting export to {output_path}")
            
            # Ensure output path has .cgc extension
            if not str(output_path).endswith('.cgc'):
                output_path = Path(str(output_path) + '.cgc')
            
            # Create temporary directory for bundle contents
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Extract metadata base
                info_logger("Extracting metadata...")
                metadata = self._extract_metadata(repo_path)
                
                # Step 2: Extract schema
                info_logger("Extracting schema...")
                schema = self._extract_schema()
                with open(temp_path / "schema.json", 'w') as f:
                    json.dump(schema, f, indent=2, cls=_BundleEncoder)
                
                # Step 3: Extract nodes
                info_logger("Extracting nodes...")
                node_count = self._extract_nodes(temp_path / "nodes.jsonl", repo_path)
                if node_count == 0:
                    return False, (
                        "No nodes to export. Index the repository first or verify "
                        "that --repo exists in the graph."
                    )

                # Step 4: Extract edges
                info_logger("Extracting edges...")
                edge_count = self._extract_edges(temp_path / "edges.jsonl", repo_path)
                
                # Step 5: Generate statistics and assemble standardized metadata
                if include_stats:
                    info_logger("Generating statistics...")
                    stats = self._generate_stats(repo_path, node_count, edge_count)
                    with open(temp_path / "stats.json", 'w') as f:
                        json.dump(stats, f, indent=2, cls=_BundleEncoder)
                else:
                    stats = None

                # Compile dynamic standardized metadata
                try:
                    from importlib.metadata import version as get_version
                    py_version = get_version("codegraphcontext")
                except Exception:
                    py_version = "0.5.1"

                metadata["format_version"] = "1.0.0"
                metadata["generator"] = f"PYv{py_version}"
                
                # Timestamp format: YYYY-MM-DDTHH:MM:SSZ (UTC ISO String format)
                # datetime.utcnow() was deprecated, using timezone-aware or simple UTC strftime
                from datetime import timezone
                metadata["exported_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                # Build name
                if metadata.get("repo") and "/" in metadata["repo"]:
                    owner, repo_name = metadata["repo"].split("/", 1)
                    branch = metadata.get("branch", "main")
                    commit = metadata.get("commit", "latest")
                    metadata["name"] = f"{owner}__{repo_name}__{branch}__{commit}.cgc"
                else:
                    foldername = metadata.get("repo", "unknown")
                    metadata["name"] = f"{foldername}.cgc"

                metadata["graph_metrics"] = {
                    "total_nodes": node_count,
                    "total_edges": edge_count
                }

                # Save final metadata.json
                with open(temp_path / "metadata.json", 'w') as f:
                    json.dump(metadata, f, indent=2, cls=_BundleEncoder)
                
                # Step 6: Create README
                self._create_readme(temp_path / "README.md", metadata, stats if include_stats else None)
                
                # Step 7: Add integrity manifest and optional signature
                self._create_manifest(temp_path)
                if sign_key:
                    self._create_signature(temp_path, sign_key)

                # Step 8: Create ZIP archive
                info_logger("Creating bundle archive...")
                if encrypt_password:
                    self._create_encrypted_zip(temp_path, output_path, encrypt_password)
                else:
                    self._create_zip(temp_path, output_path)
            
            success_msg = f"✅ Successfully exported to {output_path}\n"
            success_msg += f"   Nodes: {node_count:,} | Edges: {edge_count:,}"
            if sign_key:
                success_msg += "\n   Signature: HMAC-SHA256"
            if encrypt_password:
                success_msg += "\n   Encryption: AES-256-GCM"
            info_logger(success_msg)
            return True, success_msg
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to export bundle: {str(e)}"
            error_logger(error_msg)
            # Print full traceback for debugging
            traceback.print_exc()
            return False, error_msg
    
    def import_from_bundle(
        self,
        bundle_path: Path,
        clear_existing: bool = False,
        readonly: bool = False,
        password: Optional[str] = None,
        verify_key: Optional[str] = None,
        graph_name: str = None,
    ) -> Tuple[bool, str]:
        self._active_graph = graph_name
        """
        Import a .cgc bundle into the current database.
        
        Args:
            bundle_path: Path to the .cgc file
            clear_existing: Whether to clear existing graph data first
            readonly: If True, mount as read-only (future feature)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            info_logger(f"Starting import from {bundle_path}")
            
            if not bundle_path.exists():
                return False, f"Bundle file not found: {bundle_path}"
            
            # Extract bundle to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Extract ZIP (with Zip Slip protection)
                info_logger("Extracting bundle...")
                # _extract_bundle_archive delegates to _extract_zip_safely, which
                # rejects Zip Slip via relative_to() on resolved paths — the same
                # component-wise comparison main used inline, applied to both the
                # outer archive and the decrypted inner payload.
                payload_path, extract_msg = self._extract_bundle_archive(bundle_path, temp_path, password)
                if payload_path is None:
                    return False, extract_msg
                
                # Step 2: Validate bundle
                info_logger("Validating bundle...")
                is_valid, validation_msg = self._validate_bundle(payload_path, verify_key=verify_key)
                if not is_valid:
                    return False, f"Invalid bundle: {validation_msg}"
                
                # Step 3: Load metadata
                with open(payload_path / "metadata.json", 'r') as f:
                    metadata = json.load(f)
                
                info_logger(f"Loading bundle: {metadata.get('repo', 'unknown')}")
                info_logger(f"Bundle version: {metadata.get('cgc_version', 'unknown')}")
                
                # Step 4: Handle existing data
                repo_name = metadata.get('repo', 'unknown')
                repo_path = metadata.get('repo_path')
                
                if clear_existing:
                    # User explicitly wants to clear - remove everything
                    info_logger("Clearing all existing graph data...")
                    self._clear_graph()
                else:
                    # Check if this repository already exists (only when NOT clearing)
                    existing_repo = self._check_existing_repository(repo_name, repo_path)
                    
                    if existing_repo:
                        return False, (
                            f"Repository '{repo_name}' already exists in the database. "
                            "Re-run with --clear (CLI) or clear_existing=True (MCP) to replace it."
                        )
                
                
                # Step 5: Create schema
                info_logger("Creating schema...")
                self._import_schema(payload_path / "schema.json")
                
                # Step 6: Import nodes
                info_logger("Importing nodes...")
                node_count = self._import_nodes(payload_path / "nodes.jsonl")
                
                # Step 7: Import edges
                info_logger("Importing edges...")
                edge_count = self._import_edges(payload_path / "edges.jsonl")
            
            success_msg = f"✅ Successfully imported {bundle_path.name}\n"
            success_msg += f"   Repository: {metadata.get('repo', 'unknown')}\n"
            success_msg += f"   Nodes: {node_count:,} | Edges: {edge_count:,}"
            info_logger(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Failed to import bundle: {str(e)}"
            error_logger(error_msg)
            return False, error_msg
    
    # ========================================================================
    # EXPORT HELPERS
    # ========================================================================
    
    def _extract_metadata(self, repo_path: Optional[Path]) -> Dict[str, Any]:
        """Extract metadata about the repository and indexing process."""
        metadata = {
            "cgc_version": self.VERSION,
            "exported_at": datetime.now().isoformat(),
            "format_version": "1.0"
        }
        
        # Get repository information
        with self.db_manager.get_driver(self._active_graph).session() as session:
            if repo_path:
                # Specific repository
                result = session.run(
                    "MATCH (r:Repository {path: $path}) RETURN r",
                    path=repo_path.resolve().as_posix()
                )
                repo_node = result.single()
                if repo_node:
                    node = repo_node['r']
                    # Convert Node to dict (handle both Neo4j and FalkorDB)
                    try:
                        repo = dict(node)
                    except TypeError:
                        # FalkorDB nodes - access properties directly
                        repo = {}
                        if hasattr(node, '_properties'):
                            repo = dict(node._properties)
                        elif hasattr(node, 'properties'):
                            repo = dict(node.properties)
                        else:
                            # Fallback: try to get individual properties
                            for attr in ['name', 'path', 'is_dependency']:
                                if hasattr(node, attr):
                                    repo[attr] = getattr(node, attr)
                    
                    metadata["repo"] = repo.get('name', str(repo_path.name if repo_path else 'unknown'))
                    # Clean up absolute path prefix to keep it relative
                    meta_path = repo.get('path', '')
                    if repo_path and meta_path.startswith(repo_path.resolve().as_posix()):
                        repo_str = repo_path.resolve().as_posix()
                        rel = meta_path[len(repo_str):].lstrip('/')
                        metadata["repo_path"] = "./" + rel if rel else "."
                    else:
                        metadata["repo_path"] = meta_path
                    metadata["is_dependency"] = repo.get('is_dependency', False)
            else:
                # All repositories
                result = session.run(
                    "MATCH (r:Repository) RETURN r.name as name, r.path as path"
                )
                repos = [{"name": record["name"], "path": record["path"]} for record in result]
                metadata["repositories"] = repos
                metadata["repo"] = "multiple" if len(repos) > 1 else repos[0]["name"] if repos else "unknown"
            
            # Try to get git information if available
            if repo_path and repo_path.exists():
                commit = get_repo_commit_hash(repo_path)
                if commit:
                    metadata["commit"] = commit[:8]
                branch = get_repo_branch_name(repo_path)
                if branch:
                    metadata["branch"] = branch

                try:
                    repo_str = repo_path.resolve().as_posix()
                    result = session.run("""
                        MATCH (f:File)
                        WHERE f.path = $repo_path OR f.path STARTS WITH $repo_prefix
                        RETURN f.language as language, count(*) as count
                        ORDER BY count DESC
                    """, repo_path=repo_str, repo_prefix=repo_str + "/")
                    languages = {record["language"]: record["count"] for record in result if record["language"]}
                    metadata["languages"] = list(languages.keys())
                except Exception:
                    pass
        
        return metadata
    
    def _extract_schema(self) -> Dict[str, Any]:
        """Extract the graph schema (node labels, relationship types, constraints)."""
        from codegraphcontext.tools.indexing.schema_contract import RELATIONSHIP_TYPES

        schema = {
            "node_labels": [],
            "relationship_types": [],
            "constraints": [],
            "indexes": []
        }

        backend = getattr(self.db_manager, "get_backend_type", lambda: "neo4j")()

        with self.db_manager.get_driver(self._active_graph).session() as session:
            try:
                if backend in ("kuzudb", "ladybugdb"):
                    result = session.run("MATCH (n) RETURN DISTINCT label(n) AS lbl")
                    labels = sorted({record[0] for record in result if record[0] is not None})
                elif backend == "neo4j":
                    result = session.run("CALL db.labels()")
                    labels = []
                    for record in result:
                        try:
                            labels.append(record[0])
                        except (KeyError, TypeError):
                            if hasattr(record, "values"):
                                vals = list(record.values())
                                if vals:
                                    labels.append(vals[0])
                else:
                    result = session.run("CALL db.labels()")
                    labels = [record[0] for record in result if record[0] is not None]
                schema["node_labels"] = labels
            except Exception:
                schema["node_labels"] = []

            try:
                if backend in ("kuzudb", "ladybugdb"):
                    result = session.run("MATCH ()-[r]->() RETURN DISTINCT label(r) AS rel")
                    rel_types = sorted({record[0] for record in result if record[0] is not None})
                elif backend == "neo4j":
                    result = session.run("CALL db.relationshipTypes()")
                    rel_types = [record[0] for record in result if record[0] is not None]
                else:
                    result = session.run("CALL db.relationshipTypes()")
                    rel_types = [record[0] for record in result if record[0] is not None]
                schema["relationship_types"] = rel_types or sorted(RELATIONSHIP_TYPES)
            except Exception:
                schema["relationship_types"] = sorted(RELATIONSHIP_TYPES)

            if backend == "neo4j":
                try:
                    result = session.run("SHOW CONSTRAINTS")
                    schema["constraints"] = [dict(record) for record in result]
                except Exception:
                    pass
                try:
                    result = session.run("SHOW INDEXES")
                    schema["indexes"] = [dict(record) for record in result]
                except Exception:
                    pass

        return schema

    def _repo_scope_params(self, repo_path: Path) -> Dict[str, str]:
        repo_str = repo_path.resolve().as_posix()
        return {"repo_path": repo_str, "repo_prefix": repo_str + "/"}

    def _run_session_query(self, session, query: str, params: Dict[str, str]):
        try:
            return session.run(query, **params)
        except TypeError:
            return session.run(query)

    def _normalize_labels(self, labels) -> List[str]:
        if labels is None:
            return []
        if isinstance(labels, str):
            return [labels]
        if isinstance(labels, list):
            return labels
        return list(labels)

    def _node_to_dict(self, node) -> Dict[str, Any]:
        try:
            node_dict = dict(node)
        except TypeError:
            node_dict = {}
            if hasattr(node, '_properties'):
                node_dict = dict(node._properties)
            elif hasattr(node, 'properties'):
                node_dict = dict(node.properties)
        node_dict.pop('_label', None)
        for key, val in list(node_dict.items()):
            if key != '_id' and val is None:
                node_dict.pop(key)
        return node_dict

    def _node_identity(self, node, labels: List[str], node_dict: Dict[str, Any]) -> str:
        if '_id' in node_dict:
            return str(node_dict['_id'])
        if hasattr(node, 'element_id'):
            return str(node.element_id)
        if hasattr(node, 'id'):
            return str(node.id)
        label = labels[0] if labels else ''
        return f"{label}:{node_dict.get('name', '')}:{node_dict.get('path', '')}"

    def _repo_node_queries(self) -> List[str]:
        return [
            """
            MATCH (n)
            WHERE n.path = $repo_path OR n.path STARTS WITH $repo_prefix
            RETURN n, labels(n) as labels
            """,
            """
            MATCH (f:File)-[:IMPORTS]->(n:Module)
            WHERE f.path = $repo_path OR f.path STARTS WITH $repo_prefix
            RETURN n, labels(n) as labels
            """,
            """
            MATCH (c)-[:INHERITS|IMPLEMENTS]->(n:ExternalClass)
            WHERE c.path = $repo_path OR c.path STARTS WITH $repo_prefix
            RETURN n, labels(n) as labels
            """,
        ]

    def _repo_edge_queries(self) -> List[str]:
        return [
            """
            MATCH (n)-[r]->(m)
            WHERE (n.path = $repo_path OR n.path STARTS WITH $repo_prefix)
               OR (m.path = $repo_path OR m.path STARTS WITH $repo_prefix)
            RETURN n, r, m, type(r) as rel_type
            """,
            """
            MATCH (f:File)-[r:IMPORTS]->(m:Module)
            WHERE f.path = $repo_path OR f.path STARTS WITH $repo_prefix
            RETURN f as n, r, m, type(r) as rel_type
            """,
            """
            MATCH (c)-[r:INHERITS|IMPLEMENTS]->(ec:ExternalClass)
            WHERE c.path = $repo_path OR c.path STARTS WITH $repo_prefix
            RETURN c as n, r, ec as m, type(r) as rel_type
            """,
        ]
    
    def _extract_nodes(self, output_file: Path, repo_path: Optional[Path]) -> int:
        """Extract all nodes to JSONL format."""
        count = 0
        seen_nodes = set()
        
        with self.db_manager.get_driver(self._active_graph).session() as session:
            if repo_path:
                queries = self._repo_node_queries()
                params = self._repo_scope_params(repo_path)
            else:
                queries = ["MATCH (n) RETURN n, labels(n) as labels"]
                params = {}
            
            with open(output_file, 'w') as f:
                for query in queries:
                    result = self._run_session_query(session, query, params)
                    for record in result:
                        node = record['n']
                        labels = self._normalize_labels(record['labels'])
                        node_dict = self._node_to_dict(node)
                        node_key = self._node_identity(node, labels, node_dict)
                        if node_key in seen_nodes:
                            continue
                        seen_nodes.add(node_key)
                    
                        # Clean up absolute path prefix to keep it relative
                        if repo_path:
                            repo_str = repo_path.resolve().as_posix()
                            repo_prefix = repo_str + "/"
                            for key, val in list(node_dict.items()):
                                if not isinstance(val, str):
                                    continue
                                if val == repo_str:
                                    node_dict[key] = "."
                                elif val.startswith(repo_prefix):
                                    rel = val[len(repo_prefix):].lstrip('/\\')
                                    node_dict[key] = "./" + rel if rel else "."
                    
                        node_dict['_labels'] = labels
                    
                        if '_id' not in node_dict:
                            if hasattr(node, 'element_id'):
                                node_dict['_id'] = node.element_id
                            elif hasattr(node, 'id'):
                                node_dict['_id'] = str(node.id)
                    
                        f.write(json.dumps(node_dict, cls=_BundleEncoder) + '\n')
                        count += 1
        
        return count
    
    def _extract_edges(self, output_file: Path, repo_path: Optional[Path]) -> int:
        """Extract all relationships to JSONL format."""
        count = 0
        seen_edges = set()
        
        with self.db_manager.get_driver(self._active_graph).session() as session:
            if repo_path:
                queries = self._repo_edge_queries()
                params = self._repo_scope_params(repo_path)
            else:
                queries = ["MATCH (n)-[r]->(m) RETURN n, r, m, type(r) as rel_type"]
                params = {}
            
            with open(output_file, 'w') as f:
                for query in queries:
                    result = self._run_session_query(session, query, params)
                    for record in result:
                        source = record['n']
                        target = record['m']
                        rel = record['r']
                        rel_type = record['rel_type']

                        # Get relationship properties
                        try:
                            rel_props = dict(rel)
                        except TypeError:
                            rel_props = {}
                            if hasattr(rel, '_properties'):
                                rel_props = dict(rel._properties)
                            elif hasattr(rel, 'properties'):
                                rel_props = dict(rel.properties)

                        # Kùzu/Ladybug-style relationship records expose stable
                        # endpoint IDs as properties. Prefer those over Python
                        # wrapper object ids so exported edges can be re-linked to
                        # the node rows in nodes.jsonl.
                        from_id = rel_props.pop('_src', None)
                        to_id = rel_props.pop('_dst', None)
                        rel_props.pop('_label', None)
                        rel_props.pop('_id', None)
                        for key, val in list(rel_props.items()):
                            if val is None:
                                rel_props.pop(key)

                        # Get source and target IDs (handle Neo4j/FalkorDB fallback)
                        if from_id is None:
                            if hasattr(source, 'element_id'):
                                from_id = source.element_id
                            elif hasattr(source, 'id'):
                                from_id = str(source.id)
                            else:
                                from_id = str(id(source))

                        if to_id is None:
                            if hasattr(target, 'element_id'):
                                to_id = target.element_id
                            elif hasattr(target, 'id'):
                                to_id = str(target.id)
                            else:
                                to_id = str(id(target))

                        # Clean up absolute path prefix inside edge properties
                        if repo_path:
                            repo_str = repo_path.resolve().as_posix()
                            repo_prefix = repo_str + "/"
                            for key, val in list(rel_props.items()):
                                if not isinstance(val, str):
                                    continue
                                if val == repo_str:
                                    rel_props[key] = "."
                                elif val.startswith(repo_prefix):
                                    rel = val[len(repo_prefix):].lstrip('/\\')
                                    rel_props[key] = "./" + rel if rel else "."

                        props_key = tuple(
                            sorted(
                                (k, json.dumps(v, sort_keys=True, default=str))
                                for k, v in rel_props.items()
                            )
                        )
                        edge_key = (str(from_id), str(rel_type), str(to_id), props_key)
                        if edge_key in seen_edges:
                            continue
                        seen_edges.add(edge_key)
                        
                        # Create edge representation
                        edge_dict = {
                            'from': from_id,
                            'to': to_id,
                            'type': rel_type,
                            'properties': rel_props
                        }
                        
                        f.write(json.dumps(edge_dict, cls=_BundleEncoder) + '\n')
                        count += 1
        
        return count
    
    def _generate_stats(self, repo_path: Optional[Path], node_count: int, edge_count: int) -> Dict[str, Any]:
        """Generate statistics about the graph."""
        stats = {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "generated_at": datetime.now().isoformat()
        }
        
        with self.db_manager.get_driver(self._active_graph).session() as session:
            # Count by node type
            if repo_path:
                repo_str = repo_path.resolve().as_posix()
                result = session.run("""
                    MATCH (n)
                    WHERE n.path = $repo_path OR n.path STARTS WITH $repo_prefix
                    RETURN labels(n)[0] as label, count(*) as count
                    ORDER BY count DESC
                """, repo_path=repo_str, repo_prefix=repo_str + "/")
            else:
                result = session.run("""
                    MATCH (n)
                    RETURN labels(n)[0] as label, count(*) as count
                    ORDER BY count DESC
                """)
            stats["nodes_by_type"] = {record["label"]: record["count"] for record in result if record["label"]}
            
            # Count by relationship type
            if repo_path:
                result = session.run("""
                    MATCH (n)-[r]->(m)
                    WHERE (n.path = $repo_path OR n.path STARTS WITH $repo_prefix)
                       OR (m.path = $repo_path OR m.path STARTS WITH $repo_prefix)
                    RETURN type(r) as type, count(*) as count
                    ORDER BY count DESC
                """, repo_path=repo_str, repo_prefix=repo_str + "/")
            else:
                result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as type, count(*) as count
                    ORDER BY count DESC
                """)
            stats["edges_by_type"] = {record["type"]: record["count"] for record in result}
            
            # File count
            if repo_path:
                result = session.run(
                    "MATCH (f:File) WHERE f.path = $repo_path OR f.path STARTS WITH $repo_prefix RETURN count(f) as count",
                    repo_path=repo_str,
                    repo_prefix=repo_str + "/",
                )
            else:
                result = session.run("MATCH (f:File) RETURN count(f) as count")
            
            file_count = result.single()
            stats["files"] = file_count["count"] if file_count else 0
        
        return stats
    
    def _create_readme(self, output_file: Path, metadata: Dict, stats: Optional[Dict]):
        """Create a human-readable README for the bundle."""
        readme_content = f"""# CodeGraphContext Bundle

## Repository Information
- **Repository**: {metadata.get('repo', 'Unknown')}
- **Exported**: {metadata.get('exported_at', 'Unknown')}
- **CGC Version**: {metadata.get('cgc_version', 'Unknown')}
"""
        
        if 'commit' in metadata:
            readme_content += f"- **Commit**: {metadata['commit']}\n"
        
        if 'languages' in metadata:
            readme_content += f"- **Languages**: {', '.join(metadata['languages'])}\n"
        
        if stats:
            readme_content += f"""
## Statistics
- **Total Nodes**: {stats.get('total_nodes', 0):,}
- **Total Edges**: {stats.get('total_edges', 0):,}
- **Files**: {stats.get('files', 0):,}

### Nodes by Type
"""
            for label, count in stats.get('nodes_by_type', {}).items():
                readme_content += f"- {label}: {count:,}\n"
            
            readme_content += "\n### Edges by Type\n"
            for rel_type, count in stats.get('edges_by_type', {}).items():
                readme_content += f"- {rel_type}: {count:,}\n"
        
        readme_content += """
## Usage

Load this bundle with:
```bash
cgc load <bundle-file>.cgc
```

Or import into existing graph:
```bash
cgc import <bundle-file>.cgc
```
"""
        
        with open(output_file, 'w') as f:
            f.write(readme_content)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _canonical_json(data: Dict[str, Any]) -> bytes:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), cls=_BundleEncoder).encode("utf-8")

    def _create_manifest(self, bundle_dir: Path) -> Dict[str, Any]:
        """Create a checksum manifest for every payload file in the bundle."""
        files = {}
        for path in sorted(bundle_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(bundle_dir).as_posix()
            if rel in {"manifest.json", "signature.json"}:
                continue
            files[rel] = {
                "sha256": self._sha256_file(path),
                "size": path.stat().st_size,
            }

        manifest = {
            "manifest_version": "1.0.0",
            "digest": "sha256",
            "files": files,
            "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with open(bundle_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, cls=_BundleEncoder)
        return manifest

    def _load_manifest(self, bundle_dir: Path) -> Optional[Dict[str, Any]]:
        manifest_path = bundle_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _verify_manifest(self, bundle_dir: Path) -> Tuple[bool, str]:
        manifest = self._load_manifest(bundle_dir)
        if manifest is None:
            return True, "No manifest present; skipped checksum verification"

        expected_files = manifest.get("files", {})
        if not isinstance(expected_files, dict):
            return False, "Invalid manifest: files must be an object"

        actual_files = {
            path.relative_to(bundle_dir).as_posix()
            for path in bundle_dir.rglob("*")
            if path.is_file() and path.relative_to(bundle_dir).as_posix() not in {"manifest.json", "signature.json"}
        }
        expected_names = set(expected_files)
        missing = sorted(expected_names - actual_files)
        extra = sorted(actual_files - expected_names)
        if missing:
            return False, f"Manifest mismatch: missing file(s): {', '.join(missing)}"
        if extra:
            return False, f"Manifest mismatch: unexpected file(s): {', '.join(extra)}"

        for rel, expected in expected_files.items():
            path = bundle_dir / rel
            if path.stat().st_size != expected.get("size"):
                return False, f"Checksum mismatch for {rel}: size changed"
            digest = self._sha256_file(path)
            if not hmac.compare_digest(digest, str(expected.get("sha256", ""))):
                return False, f"Checksum mismatch for {rel}"

        return True, "Manifest checksums verified"

    def _create_signature(self, bundle_dir: Path, sign_key: str) -> Dict[str, Any]:
        """Create an HMAC-SHA256 signature over manifest.json."""
        manifest = self._load_manifest(bundle_dir) or self._create_manifest(bundle_dir)
        signature = hmac.new(
            sign_key.encode("utf-8"),
            self._canonical_json(manifest),
            hashlib.sha256,
        ).hexdigest()
        payload = {
            "signature_version": "1.0.0",
            "algorithm": "HMAC-SHA256",
            "signature": signature,
        }
        with open(bundle_dir / "signature.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return payload

    def _verify_signature(self, bundle_dir: Path, verify_key: Optional[str]) -> Tuple[bool, str]:
        signature_path = bundle_dir / "signature.json"
        if not signature_path.exists():
            return True, "No signature present"
        if not verify_key:
            return False, "Bundle is signed; provide a verification key"

        manifest = self._load_manifest(bundle_dir)
        if manifest is None:
            return False, "Signature present but manifest.json is missing"
        with open(signature_path, "r", encoding="utf-8") as f:
            signature = json.load(f)
        if signature.get("algorithm") != "HMAC-SHA256":
            return False, f"Unsupported signature algorithm: {signature.get('algorithm')}"
        expected = hmac.new(
            verify_key.encode("utf-8"),
            self._canonical_json(manifest),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, str(signature.get("signature", ""))):
            return False, "Signature verification failed"
        return True, "Signature verified"

    @staticmethod
    def _derive_encryption_key(password: str, salt: bytes, iterations: int) -> bytes:
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except ImportError as exc:
            raise RuntimeError("Encrypted bundles require the 'cryptography' package") from exc

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))

    def _create_encrypted_zip(self, payload_dir: Path, output_file: Path, password: str):
        """Create an encrypted .cgc outer ZIP containing an encrypted bundle payload."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("Encrypted bundles require the 'cryptography' package") from exc

        with tempfile.TemporaryDirectory() as enc_dir:
            enc_path = Path(enc_dir)
            payload_zip = enc_path / "payload.zip"
            self._create_zip(payload_dir, payload_zip)

            salt = secrets.token_bytes(16)
            nonce = secrets.token_bytes(12)
            iterations = 390000
            key = self._derive_encryption_key(password, salt, iterations)
            plaintext = payload_zip.read_bytes()
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

            (enc_path / "payload.enc").write_bytes(ciphertext)
            metadata = {
                "encryption_version": "1.0.0",
                "algorithm": "AES-256-GCM",
                "kdf": "PBKDF2-HMAC-SHA256",
                "iterations": iterations,
                "salt": base64.b64encode(salt).decode("ascii"),
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "payload_sha256": hashlib.sha256(ciphertext).hexdigest(),
            }
            with open(enc_path / "encryption.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            payload_zip.unlink()
            self._create_zip(enc_path, output_file)

    def _extract_zip_safely(self, zip_path: Path, target_dir: Path) -> Tuple[bool, str]:
        target_root = target_dir.resolve()
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for entry in zip_ref.namelist():
                resolved = (target_dir / entry).resolve()
                try:
                    resolved.relative_to(target_root)
                except ValueError:
                    return False, f"Zip Slip detected: entry '{entry}' escapes target directory"
            zip_ref.extractall(target_dir)
        return True, "Extracted"

    def _extract_bundle_archive(
        self,
        bundle_path: Path,
        target_dir: Path,
        password: Optional[str] = None,
    ) -> Tuple[Optional[Path], str]:
        ok, message = self._extract_zip_safely(bundle_path, target_dir)
        if not ok:
            return None, message

        encryption_path = target_dir / "encryption.json"
        encrypted_payload = target_dir / "payload.enc"
        if not encryption_path.exists() and not encrypted_payload.exists():
            return target_dir, "Extracted plaintext bundle"
        if not encryption_path.exists() or not encrypted_payload.exists():
            return None, "Encrypted bundle is missing encryption.json or payload.enc"
        if not password:
            return None, "Bundle is encrypted; provide a password"

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("Encrypted bundles require the 'cryptography' package") from exc

        with open(encryption_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        if metadata.get("algorithm") != "AES-256-GCM":
            return None, f"Unsupported encryption algorithm: {metadata.get('algorithm')}"

        ciphertext = encrypted_payload.read_bytes()
        expected_digest = metadata.get("payload_sha256")
        if expected_digest and not hmac.compare_digest(hashlib.sha256(ciphertext).hexdigest(), expected_digest):
            return None, "Encrypted payload checksum mismatch"

        salt = base64.b64decode(metadata["salt"])
        nonce = base64.b64decode(metadata["nonce"])
        key = self._derive_encryption_key(password, salt, int(metadata.get("iterations", 390000)))
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception:
            return None, "Failed to decrypt bundle payload"

        payload_zip = target_dir / "payload.zip"
        payload_zip.write_bytes(plaintext)
        payload_dir = target_dir / "payload"
        payload_dir.mkdir()
        ok, message = self._extract_zip_safely(payload_zip, payload_dir)
        if not ok:
            return None, message
        return payload_dir, "Extracted encrypted bundle"

    def verify_bundle(
        self,
        bundle_path: Path,
        password: Optional[str] = None,
        verify_key: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Verify bundle structure, checksums, optional signature, and encryption envelope."""
        if not bundle_path.exists():
            return False, f"Bundle file not found: {bundle_path}"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                payload_dir, message = self._extract_bundle_archive(bundle_path, Path(temp_dir), password)
                if payload_dir is None:
                    return False, message
                valid, validation_msg = self._validate_bundle(payload_dir, verify_key=verify_key)
                if not valid:
                    return False, validation_msg
                return True, validation_msg
        except Exception as exc:
            return False, str(exc)

    def inspect_bundle(
        self,
        bundle_path: Path,
        password: Optional[str] = None,
        verify_key: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Return metadata, stats, and verification status for a bundle."""
        if not bundle_path.exists():
            return False, {"error": f"Bundle file not found: {bundle_path}"}
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                payload_dir, message = self._extract_bundle_archive(bundle_path, Path(temp_dir), password)
                if payload_dir is None:
                    return False, {"error": message}
                valid, validation_msg = self._validate_bundle(payload_dir, verify_key=verify_key)
                with open(payload_dir / "metadata.json", "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                stats = {}
                stats_path = payload_dir / "stats.json"
                if stats_path.exists():
                    with open(stats_path, "r", encoding="utf-8") as f:
                        stats = json.load(f)
                manifest = self._load_manifest(payload_dir) or {}
                return True, {
                    "path": str(bundle_path),
                    "encrypted": message == "Extracted encrypted bundle",
                    "valid": valid,
                    "validation": validation_msg,
                    "signed": (payload_dir / "signature.json").exists(),
                    "metadata": metadata,
                    "stats": stats,
                    "manifest": manifest,
                }
        except Exception as exc:
            return False, {"error": str(exc)}

    @staticmethod
    def _node_key(node: Dict[str, Any]) -> str:
        labels = node.get("labels") or []
        if isinstance(labels, str):
            labels = [labels]
        props = node.get("properties") or {}
        primary = labels[0] if labels else "Node"
        for field in ("uid", "id", "path", "name"):
            if props.get(field) is not None:
                return f"{primary}:{field}:{props[field]}"
        return json.dumps(node, sort_keys=True, cls=_BundleEncoder)

    @staticmethod
    def _edge_key(edge: Dict[str, Any]) -> str:
        rel_type = edge.get("type", "REL")
        props = edge.get("properties") or {}
        from_id = edge.get("from")
        to_id = edge.get("to")
        return json.dumps(
            {"type": rel_type, "from": from_id, "to": to_id, "properties": props},
            sort_keys=True,
            cls=_BundleEncoder,
        )

    @classmethod
    def _load_jsonl_index(cls, file_path: Path, kind: str) -> Dict[str, str]:
        key_fn = cls._node_key if kind == "node" else cls._edge_key
        indexed = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                key = key_fn(item)
                indexed[key] = hashlib.sha256(
                    json.dumps(item, sort_keys=True, cls=_BundleEncoder).encode("utf-8")
                ).hexdigest()
        return indexed

    def diff_bundles(
        self,
        left_path: Path,
        right_path: Path,
        left_password: Optional[str] = None,
        right_password: Optional[str] = None,
        left_verify_key: Optional[str] = None,
        right_verify_key: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Compare two bundles without importing them."""
        try:
            with tempfile.TemporaryDirectory() as left_tmp, tempfile.TemporaryDirectory() as right_tmp:
                left_dir, left_msg = self._extract_bundle_archive(left_path, Path(left_tmp), left_password)
                right_dir, right_msg = self._extract_bundle_archive(right_path, Path(right_tmp), right_password)
                if left_dir is None:
                    return False, {"error": f"Left bundle: {left_msg}"}
                if right_dir is None:
                    return False, {"error": f"Right bundle: {right_msg}"}

                for payload_dir, verify_key in ((left_dir, left_verify_key), (right_dir, right_verify_key)):
                    valid, validation_msg = self._validate_bundle(payload_dir, verify_key=verify_key)
                    if not valid:
                        return False, {"error": validation_msg}

                left_nodes = self._load_jsonl_index(left_dir / "nodes.jsonl", "node")
                right_nodes = self._load_jsonl_index(right_dir / "nodes.jsonl", "node")
                left_edges = self._load_jsonl_index(left_dir / "edges.jsonl", "edge")
                right_edges = self._load_jsonl_index(right_dir / "edges.jsonl", "edge")

                def compare(left: Dict[str, str], right: Dict[str, str]) -> Dict[str, Any]:
                    left_keys = set(left)
                    right_keys = set(right)
                    common = left_keys & right_keys
                    changed = sorted(key for key in common if left[key] != right[key])
                    return {
                        "added": sorted(right_keys - left_keys),
                        "removed": sorted(left_keys - right_keys),
                        "changed": changed,
                    }

                with open(left_dir / "metadata.json", "r", encoding="utf-8") as f:
                    left_metadata = json.load(f)
                with open(right_dir / "metadata.json", "r", encoding="utf-8") as f:
                    right_metadata = json.load(f)

                return True, {
                    "left": {"path": str(left_path), "metadata": left_metadata},
                    "right": {"path": str(right_path), "metadata": right_metadata},
                    "nodes": compare(left_nodes, right_nodes),
                    "edges": compare(left_edges, right_edges),
                }
        except Exception as exc:
            return False, {"error": str(exc)}
    
    def _create_zip(self, source_dir: Path, output_file: Path):
        """Create a ZIP archive from the bundle directory."""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for path in source_dir.rglob('*'):
                if path.is_file():
                    arcname = path.relative_to(source_dir)
                    zipf.write(path, arcname)
    
    # ========================================================================
    # IMPORT HELPERS
    # ========================================================================
    
    def _validate_bundle(self, bundle_dir: Path, verify_key: Optional[str] = None) -> Tuple[bool, str]:
        """Validate that the bundle contains all required files."""
        required_files = ['metadata.json', 'schema.json', 'nodes.jsonl', 'edges.jsonl']
        
        for file_name in required_files:
            if not (bundle_dir / file_name).exists():
                return False, f"Missing required file: {file_name}"
        
        # Validate metadata
        try:
            with open(bundle_dir / "metadata.json", 'r') as f:
                metadata = json.load(f)
                if 'cgc_version' not in metadata:
                    return False, "Invalid metadata: missing cgc_version"
        except json.JSONDecodeError as e:
            return False, f"Invalid metadata.json: {e}"

        manifest_ok, manifest_msg = self._verify_manifest(bundle_dir)
        if not manifest_ok:
            return False, manifest_msg

        signature_ok, signature_msg = self._verify_signature(bundle_dir, verify_key)
        if not signature_ok:
            return False, signature_msg

        # Reject unsafe identifiers up front. The import writes in batches with
        # no transaction, so validating lazily would let a malicious label
        # halfway through the file execute after earlier nodes were committed.
        ok, message = self._validate_bundle_identifiers(bundle_dir)
        if not ok:
            return False, message

        return True, "Valid bundle"

    @staticmethod
    def _validate_bundle_identifiers(bundle_dir: Path) -> Tuple[bool, str]:
        """Check every node label and relationship type before importing anything."""
        try:
            with open(bundle_dir / "nodes.jsonl", 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    labels = json.loads(line).get('_labels') or []
                    if isinstance(labels, str):
                        labels = [labels]
                    for label in labels:
                        _validate_cypher_identifier(label, "node label")

            with open(bundle_dir / "edges.jsonl", 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    _validate_cypher_identifier(
                        json.loads(line).get('type'), "relationship type"
                    )
        except BundleValidationError as e:
            error_logger(f"Bundle rejected: {e}")
            return False, str(e)
        except json.JSONDecodeError as e:
            return False, f"Malformed JSON Lines in bundle: {e}"

        return True, "Valid bundle"
    
    def _check_existing_repository(self, repo_name: str, repo_path: Optional[str]) -> bool:
        """Check if a repository already exists in the database."""
        with self.db_manager.get_driver(self._active_graph).session() as session:
            # Try to find by name first
            result = session.run(
                "MATCH (r:Repository {name: $name}) RETURN r LIMIT 1",
                name=repo_name
            )
            if result.single():
                return True
            
            # If repo_path is provided, also check by path
            if repo_path:
                result = session.run(
                    "MATCH (r:Repository {path: $path}) RETURN r LIMIT 1",
                    path=repo_path
                )
                if result.single():
                    return True
        
        return False
    
    def _delete_repository(self, repo_identifier: str):
        """Delete a specific repository and all its related nodes from the graph."""
        with self.db_manager.get_driver(self._active_graph).session() as session:
            # First, try to find the repository by name or path
            result = session.run("""
                MATCH (r:Repository)
                WHERE r.name = $identifier OR r.path = $identifier
                RETURN r.path as path
                LIMIT 1
            """, identifier=repo_identifier)
            
            record = result.single()
            if not record:
                warning_logger(f"Repository '{repo_identifier}' not found for deletion")
                return
            
            repo_path = record['path']
            
            repo_prefix = repo_path if repo_path.endswith("/") else f"{repo_path}/"
            # Delete all nodes that belong to this repository
            session.run("""
                MATCH (n)
                WHERE n.path STARTS WITH $repo_prefix OR n.path = $repo_path
                DETACH DELETE n
            """, repo_path=repo_path, repo_prefix=repo_prefix)

            # Remove pathless import Module nodes left without references
            while True:
                result = session.run("""
                    MATCH (m:Module) WHERE NOT ()-[:IMPORTS|INCLUDES]->(m)
                    WITH m LIMIT 5000 DETACH DELETE m RETURN count(m) AS deleted
                """)
                record = result.single()
                if not record or record["deleted"] == 0:
                    break
            
            # Delete the repository node itself
            session.run("""
                MATCH (r:Repository)
                WHERE r.path = $repo_path
                DELETE r
            """, repo_path=repo_path)
            
            info_logger(f"Deleted repository: {repo_identifier}")
    
    def _clear_graph(self):
        """Clear all nodes and relationships from the graph in batches."""
        with self.db_manager.get_driver(self._active_graph).session() as session:
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 500 DETACH DELETE n RETURN count(n) as deleted"
                )
                record = result.single()
                if not record or record["deleted"] == 0:
                    break
    
    def _import_schema(self, schema_file: Path):
        """Import schema (constraints and indexes)."""
        with open(schema_file, 'r') as f:
            schema = json.load(f)
        
        # Note: Schema import is complex and database-specific
        # For now, we'll rely on the application to create the schema
        # This is a placeholder for future enhancement
        debug_log("Schema import not yet implemented - relying on application schema")
    
    def _import_nodes(self, nodes_file: Path) -> int:
        """Import nodes from JSONL file."""
        count = 0
        batch_size = 1000
        batch = []
        
        # Create a mapping from old IDs to new IDs
        id_mapping = {}
        
        with self.db_manager.get_driver(self._active_graph).session() as session:
            with open(nodes_file, 'r') as f:
                for line in f:
                    node_data = json.loads(line)
                    
                    # Extract labels and old ID (handle both Neo4j and KuzuDB formats)
                    labels = node_data.pop('_labels', None) or node_data.pop('_label', None) or []
                    if isinstance(labels, str):
                        labels = [labels]
                    old_id = node_data.pop('_id', None)
                    # Convert dict IDs to hashable tuples for mapping
                    if isinstance(old_id, dict):
                        old_id = (old_id.get('table', 0), old_id.get('offset', 0))
                    
                    # Remove internal properties
                    node_data.pop('_element_id', None)
                    
                    batch.append((labels, node_data, old_id))
                    
                    if len(batch) >= batch_size:
                        count += self._import_node_batch(session, batch, id_mapping)
                        batch = []
                
                # Import remaining nodes
                if batch:
                    count += self._import_node_batch(session, batch, id_mapping)
        
        # Store ID mapping for edge import
        self._id_mapping = id_mapping
        
        return count
    
    # Must stay in step with the node tables declared in
    # database_embedded_kuzu.py. A label missing here falls through to the
    # `CREATE (n:Label) SET n = $props` branch, which Kùzu rejects with
    # "Create node n expects primary key <field> as input" — so an omission is
    # not a slow path, it is a hard import failure for any bundle containing
    # that label (#1322).
    #
    # Not yet covered: DbColumn PK(name, table_fqn) and RedisKeyPattern
    # PK(pattern, datasource_name). Composite keys need a multi-key MERGE and a
    # wider `_node_lookup_key` tuple; tracked separately.
    _PK_MAP = {
        'Repository': 'path', 'File': 'path', 'Directory': 'path',
        'Module': 'name',
        'Function': 'uid', 'Class': 'uid', 'Variable': 'uid',
        'Trait': 'uid', 'Interface': 'uid', 'Macro': 'uid',
        'Struct': 'uid', 'Enum': 'uid', 'Union': 'uid',
        'Annotation': 'uid', 'Record': 'uid', 'Property': 'uid',
        'Parameter': 'uid', 'EnumMember': 'uid', 'Mixin': 'uid',
        'Extension': 'uid', 'Object': 'uid',
        'DbTable': 'name', 'Datasource': 'name', 'ExternalClass': 'name',
    }
    _UID_PARTS = {
        'Function': ['name', 'path', 'line_number'],
        'Class': ['name', 'path', 'line_number'],
        'Variable': ['name', 'path', 'line_number'],
        'Trait': ['name', 'path', 'line_number'],
        'Interface': ['name', 'path', 'line_number'],
        'Macro': ['name', 'path', 'line_number'],
        'Struct': ['name', 'path', 'line_number'],
        'Enum': ['name', 'path', 'line_number'],
        'Union': ['name', 'path', 'line_number'],
        'Annotation': ['name', 'path', 'line_number'],
        'Record': ['name', 'path', 'line_number'],
        'Property': ['name', 'path', 'line_number'],
        'Parameter': ['name', 'path', 'function_line_number'],
        'EnumMember': ['name', 'path', 'line_number'],
        'Mixin': ['name', 'path', 'line_number'],
        'Extension': ['name', 'path', 'line_number'],
        'Object': ['name', 'path', 'line_number'],
    }

    def _import_node_batch(self, session, batch: List[Tuple], id_mapping: Dict) -> int:
        """Import a batch of nodes."""
        id_function = self._get_id_function()
        
        for labels, properties, old_id in batch:
            if not labels:
                continue
            
            if isinstance(labels, str):
                labels = [labels]
            labels = [_validate_cypher_identifier(l, "node label") for l in labels]
            label_str = ':'.join(labels)
            primary_label = labels[0]

            pk_field = self._PK_MAP.get(primary_label)
            if pk_field == 'uid' and 'uid' not in properties:
                parts = self._UID_PARTS.get(primary_label, [])
                properties['uid'] = ''.join(str(properties.get(p, '')) for p in parts)

            if pk_field and pk_field in properties:
                pk_val = properties[pk_field]
                remaining = {k: v for k, v in properties.items() if k != pk_field}
                query = (
                    f"MERGE (n:{label_str} {{{pk_field}: $pk_val}}) "
                    f"SET n += $props RETURN {id_function}(n) as new_id"
                )
                result = session.run(query, pk_val=pk_val, props=remaining)
            else:
                query = f"CREATE (n:{label_str}) SET n = $props RETURN {id_function}(n) as new_id"
                result = session.run(query, props=properties)

            record = result.single()
            if record and old_id:
                if self._uses_pk_edge_matching():
                    lookup = self._node_lookup_key(labels, properties)
                    if lookup:
                        id_mapping[old_id] = lookup
                else:
                    id_mapping[old_id] = record['new_id']
        
        return len(batch)
    
    def _import_edges(self, edges_file: Path) -> int:
        """Import edges from JSONL file."""
        count = 0
        batch_size = 1000
        batch = []
        
        with self.db_manager.get_driver(self._active_graph).session() as session:
            with open(edges_file, 'r') as f:
                for line in f:
                    edge_data = json.loads(line)
                    batch.append(edge_data)
                    
                    if len(batch) >= batch_size:
                        count += self._import_edge_batch(session, batch)
                        batch = []
                
                # Import remaining edges
                if batch:
                    count += self._import_edge_batch(session, batch)
        
        return count
    
    def _import_edge_batch(self, session, batch: List[Dict]) -> int:
        """Import a batch of edges."""
        id_mapping = getattr(self, '_id_mapping', {})
        # Detect database backend to use appropriate ID function
        id_function = self._get_id_function()
        
        for edge in batch:
            old_from = edge.get('from')
            old_to = edge.get('to')
            # Convert dict IDs to hashable tuples (matches node import conversion)
            if isinstance(old_from, dict):
                old_from = (old_from.get('table', 0), old_from.get('offset', 0))
            if isinstance(old_to, dict):
                old_to = (old_to.get('table', 0), old_to.get('offset', 0))
            rel_type = _validate_cypher_identifier(edge.get('type'), "relationship type")
            properties = edge.get('properties', {})
            
            # Map old IDs to new IDs
            new_from = id_mapping.get(old_from)
            new_to = id_mapping.get(old_to)
            
            # `is None`, not falsy: FalkorDB's id() is 0-based, so the first
            # node imported (the Repository) maps to 0. A truthiness test drops
            # every edge touching it -- silently, while the caller still reports
            # the full edge count. Neo4j elementIds (str) and Kuzu/Ladybug PK
            # tuples are never falsy, so this only ever bit FalkorDB.
            if new_from is None or new_to is None:
                warning_logger(f"Skipping edge: node IDs not found in mapping")
                continue
            
            if self._uses_pk_edge_matching():
                from_label, from_pk, from_val = new_from
                to_label, to_pk, to_val = new_to
                query = f"""
                    MATCH (a:{from_label} {{{from_pk}: $from_val}}), (b:{to_label} {{{to_pk}: $to_val}})
                    CREATE (a)-[r:{rel_type}]->(b)
                    SET r = $props
                """
                session.run(
                    query,
                    from_val=from_val,
                    to_val=to_val,
                    props=properties,
                )
            else:
                query = f"""
                    MATCH (a), (b)
                    WHERE {id_function}(a) = $from_id AND {id_function}(b) = $to_id
                    CREATE (a)-[r:{rel_type}]->(b)
                    SET r = $props
                """
                session.run(query, from_id=new_from, to_id=new_to, props=properties)
        
        return len(batch)
