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
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import subprocess

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger


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
    
    def _get_id_function(self) -> str:
        """
        Get the appropriate ID function based on the database backend.
        
        Returns:
            str: 'elementId' for Neo4j, 'id' for FalkorDB
        """
        # Check if we're using Neo4j or FalkorDB
        backend = self.db_manager.get_backend_type()
        if backend == 'neo4j':
            return 'elementId'
        else:  # FalkorDB or other backends
            return 'id'

    
    def export_to_bundle(
        self,
        output_path: Path,
        repo_path: Optional[Path] = None,
        include_stats: bool = True
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
                
                # Step 1: Extract metadata
                info_logger("Extracting metadata...")
                metadata = self._extract_metadata(repo_path)
                with open(temp_path / "metadata.json", 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Step 2: Extract schema
                info_logger("Extracting schema...")
                schema = self._extract_schema()
                with open(temp_path / "schema.json", 'w') as f:
                    json.dump(schema, f, indent=2)
                
                # Step 3: Extract nodes
                info_logger("Extracting nodes...")
                node_count = self._extract_nodes(temp_path / "nodes.jsonl", repo_path)
                
                # Step 4: Extract edges
                info_logger("Extracting edges...")
                edge_count = self._extract_edges(temp_path / "edges.jsonl", repo_path)
                
                # Step 5: Generate statistics
                if include_stats:
                    info_logger("Generating statistics...")
                    stats = self._generate_stats(repo_path, node_count, edge_count)
                    with open(temp_path / "stats.json", 'w') as f:
                        json.dump(stats, f, indent=2)
                
                # Step 6: Create README
                self._create_readme(temp_path / "README.md", metadata, stats if include_stats else None)
                
                # Step 7: Create ZIP archive
                info_logger("Creating bundle archive...")
                self._create_zip(temp_path, output_path)
            
            success_msg = f"✅ Successfully exported to {output_path}\n"
            success_msg += f"   Nodes: {node_count:,} | Edges: {edge_count:,}"
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
        readonly: bool = False
    ) -> Tuple[bool, str]:
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
                
                # Step 1: Extract ZIP
                info_logger("Extracting bundle...")
                with zipfile.ZipFile(bundle_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)
                
                # Step 2: Validate bundle
                info_logger("Validating bundle...")
                is_valid, validation_msg = self._validate_bundle(temp_path)
                if not is_valid:
                    return False, f"Invalid bundle: {validation_msg}"
                
                # Step 3: Load metadata
                with open(temp_path / "metadata.json", 'r') as f:
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
                        return False, f"Repository '{repo_name}' already exists in the database. Use clear_existing=True to replace it."
                
                
                # Step 5: Create schema
                info_logger("Creating schema...")
                self._import_schema(temp_path / "schema.json")
                
                # Step 6: Import nodes
                info_logger("Importing nodes...")
                node_count = self._import_nodes(temp_path / "nodes.jsonl")
                
                # Step 7: Import edges
                info_logger("Importing edges...")
                edge_count = self._import_edges(temp_path / "edges.jsonl")
            
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
        with self.db_manager.get_driver().session() as session:
            if repo_path:
                # Specific repository
                result = session.run(
                    "MATCH (r:Repository {path: $path}) RETURN r",
                    path=str(repo_path.resolve())
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
                    
                    metadata["repo"] = repo.get('name', str(repo_path))
                    metadata["repo_path"] = repo.get('path')
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
                try:
                    commit = subprocess.check_output(
                        ['git', 'rev-parse', 'HEAD'],
                        cwd=repo_path,
                        stderr=subprocess.DEVNULL
                    ).decode().strip()
                    metadata["commit"] = commit[:8]
                    
                    # Get language statistics
                    result = session.run("""
                        MATCH (f:File)
                        WHERE f.path STARTS WITH $repo_path
                        RETURN f.language as language, count(*) as count
                        ORDER BY count DESC
                    """, repo_path=str(repo_path.resolve()))
                    
                    languages = {record["language"]: record["count"] for record in result if record["language"]}
                    metadata["languages"] = list(languages.keys())
                    
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
        
        return metadata
    
    def _extract_schema(self) -> Dict[str, Any]:
        """Extract the graph schema (node labels, relationship types, constraints)."""
        schema = {
            "node_labels": [],
            "relationship_types": [],
            "constraints": [],
            "indexes": []
        }
        
        with self.db_manager.get_driver().session() as session:
            # Get node labels
            try:
                result = session.run("CALL db.labels()")
                labels = []
                for record in result:
                    try:
                        labels.append(record[0])
                    except (KeyError, TypeError):
                        if hasattr(record, 'values'):
                            vals = list(record.values())
                            if vals:
                                labels.append(vals[0])
                schema["node_labels"] = labels
            except Exception:
                schema["node_labels"] = []
            
            # Get relationship types
            try:
                result = session.run("CALL db.relationshipTypes()")
                rel_types = []
                for record in result:
                    try:
                        rel_types.append(record[0])
                    except (KeyError, TypeError):
                        if hasattr(record, 'values'):
                            vals = list(record.values())
                            if vals:
                                rel_types.append(vals[0])
                schema["relationship_types"] = rel_types
            except Exception:
                schema["relationship_types"] = []
            
            # Get constraints (Neo4j specific, may not work on all backends)
            try:
                result = session.run("SHOW CONSTRAINTS")
                schema["constraints"] = [dict(record) for record in result]
            except:
                pass
            
            # Get indexes
            try:
                result = session.run("SHOW INDEXES")
                schema["indexes"] = [dict(record) for record in result]
            except:
                pass
        
        return schema
    
    def _extract_nodes(self, output_file: Path, repo_path: Optional[Path]) -> int:
        """Extract all nodes to JSONL format."""
        count = 0
        
        with self.db_manager.get_driver().session() as session:
            # Build query based on repo_path
            if repo_path:
                query = """
                    MATCH (n)
                    WHERE n.path STARTS WITH $repo_path OR n.path STARTS WITH $repo_path
                    RETURN n, labels(n) as labels
                """
                params = {"repo_path": str(repo_path.resolve())}
            else:
                query = "MATCH (n) RETURN n, labels(n) as labels"
                params = {}
            
            # Run query with proper parameter handling for both Neo4j and FalkorDB
            try:
                result = session.run(query, **params)
            except TypeError:
                # FalkorDB might not support **params, try without
                result = session.run(query)
            
            with open(output_file, 'w') as f:
                for record in result:
                    node = record['n']
                    labels = record['labels']
                    
                    # Convert node to dict (handle both Neo4j and FalkorDB)
                    try:
                        node_dict = dict(node)
                    except TypeError:
                        # FalkorDB nodes might not be directly convertible
                        node_dict = {}
                        if hasattr(node, '_properties'):
                            node_dict = dict(node._properties)
                        elif hasattr(node, 'properties'):
                            node_dict = dict(node.properties)
                    
                    node_dict['_labels'] = labels
                    
                    # Store internal ID for reference
                    if hasattr(node, 'element_id'):
                        node_dict['_id'] = node.element_id
                    elif hasattr(node, 'id'):
                        node_dict['_id'] = str(node.id)
                    
                    f.write(json.dumps(node_dict) + '\n')
                    count += 1
        
        return count
    
    def _extract_edges(self, output_file: Path, repo_path: Optional[Path]) -> int:
        """Extract all relationships to JSONL format."""
        count = 0
        
        with self.db_manager.get_driver().session() as session:
            # Build query based on repo_path
            if repo_path:
                query = """
                    MATCH (n)-[r]->(m)
                    WHERE (n.path STARTS WITH $repo_path OR n.path STARTS WITH $repo_path)
                       OR (m.path STARTS WITH $repo_path OR m.path STARTS WITH $repo_path)
                    RETURN n, r, m, type(r) as rel_type
                """
                params = {"repo_path": str(repo_path.resolve())}
            else:
                query = "MATCH (n)-[r]->(m) RETURN n, r, m, type(r) as rel_type"
                params = {}
            
            # Run query with proper parameter handling for both Neo4j and FalkorDB
            try:
                result = session.run(query, **params)
            except TypeError:
                # FalkorDB might not support **params, try without
                result = session.run(query)
            
            with open(output_file, 'w') as f:
                for record in result:
                    source = record['n']
                    target = record['m']
                    rel = record['r']
                    rel_type = record['rel_type']
                    
                    # Get source and target IDs (handle both Neo4j and FalkorDB)
                    if hasattr(source, 'element_id'):
                        from_id = source.element_id
                    elif hasattr(source, 'id'):
                        from_id = str(source.id)
                    else:
                        from_id = str(id(source))  # Fallback
                    
                    if hasattr(target, 'element_id'):
                        to_id = target.element_id
                    elif hasattr(target, 'id'):
                        to_id = str(target.id)
                    else:
                        to_id = str(id(target))  # Fallback
                    
                    # Get relationship properties
                    try:
                        rel_props = dict(rel)
                    except TypeError:
                        rel_props = {}
                        if hasattr(rel, '_properties'):
                            rel_props = dict(rel._properties)
                        elif hasattr(rel, 'properties'):
                            rel_props = dict(rel.properties)
                    
                    # Create edge representation
                    edge_dict = {
                        'from': from_id,
                        'to': to_id,
                        'type': rel_type,
                        'properties': rel_props
                    }
                    
                    f.write(json.dumps(edge_dict) + '\n')
                    count += 1
        
        return count
    
    def _generate_stats(self, repo_path: Optional[Path], node_count: int, edge_count: int) -> Dict[str, Any]:
        """Generate statistics about the graph."""
        stats = {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "generated_at": datetime.now().isoformat()
        }
        
        with self.db_manager.get_driver().session() as session:
            # Count by node type
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            stats["nodes_by_type"] = {record["label"]: record["count"] for record in result if record["label"]}
            
            # Count by relationship type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """)
            stats["edges_by_type"] = {record["type"]: record["count"] for record in result}
            
            # File count
            if repo_path:
                result = session.run(
                    "MATCH (f:File) WHERE f.path STARTS WITH $repo_path RETURN count(f) as count",
                    repo_path=str(repo_path.resolve())
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
    
    def _validate_bundle(self, bundle_dir: Path) -> Tuple[bool, str]:
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
        
        return True, "Valid bundle"
    
    def _check_existing_repository(self, repo_name: str, repo_path: Optional[str]) -> bool:
        """Check if a repository already exists in the database."""
        with self.db_manager.get_driver().session() as session:
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
        with self.db_manager.get_driver().session() as session:
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
            
            # Delete all nodes that belong to this repository
            # Files, Functions, Classes, Modules all have paths that start with repo_path
            session.run("""
                MATCH (n)
                WHERE n.path STARTS WITH $repo_path
                DETACH DELETE n
            """, repo_path=repo_path)
            
            # Delete the repository node itself
            session.run("""
                MATCH (r:Repository)
                WHERE r.path = $repo_path
                DELETE r
            """, repo_path=repo_path)
            
            info_logger(f"Deleted repository: {repo_identifier}")
    
    def _clear_graph(self):
        """Clear all nodes and relationships from the graph."""
        with self.db_manager.get_driver().session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
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
        
        with self.db_manager.get_driver().session() as session:
            with open(nodes_file, 'r') as f:
                for line in f:
                    node_data = json.loads(line)
                    
                    # Extract labels and old ID
                    labels = node_data.pop('_labels', [])
                    old_id = node_data.pop('_id', None)
                    
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
    
    def _import_node_batch(self, session, batch: List[Tuple], id_mapping: Dict) -> int:
        """Import a batch of nodes."""
        # Detect database backend to use appropriate ID function
        id_function = self._get_id_function()
        
        for labels, properties, old_id in batch:
            if not labels:
                continue
            
            # Create node with labels
            label_str = ':'.join(labels)
            query = f"CREATE (n:{label_str}) SET n = $props RETURN {id_function}(n) as new_id"
            
            result = session.run(query, props=properties)
            record = result.single()
            
            if record and old_id:
                id_mapping[old_id] = record['new_id']
        
        return len(batch)
    
    def _import_edges(self, edges_file: Path) -> int:
        """Import edges from JSONL file."""
        count = 0
        batch_size = 1000
        batch = []
        
        with self.db_manager.get_driver().session() as session:
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
            rel_type = edge.get('type')
            properties = edge.get('properties', {})
            
            # Map old IDs to new IDs
            new_from = id_mapping.get(old_from)
            new_to = id_mapping.get(old_to)
            
            if not new_from or not new_to:
                warning_logger(f"Skipping edge: node IDs not found in mapping")
                continue
            
            # Create relationship
            query = f"""
                MATCH (a), (b)
                WHERE {id_function}(a) = $from_id AND {id_function}(b) = $to_id
                CREATE (a)-[r:{rel_type}]->(b)
                SET r = $props
            """
            
            session.run(query, from_id=new_from, to_id=new_to, props=properties)
        
        return len(batch)

