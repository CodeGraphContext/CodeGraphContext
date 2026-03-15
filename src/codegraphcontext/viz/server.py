
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uvicorn
import json
import os
from typing import Optional, List, Dict, Any

from ..core.database import DatabaseManager
from ..utils.debug_log import debug_log

app = FastAPI()

# Enable CORS - restrict to local origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database manager (will be initialized when server starts)
db_manager: Optional[DatabaseManager] = None
# Path to static directory
_static_dir: Optional[str] = None
# Allowed base directories for file access (set when server starts)
_allowed_dirs: List[str] = []

def set_db_manager(manager: DatabaseManager):
    global db_manager
    db_manager = manager

@app.get("/api/graph")
async def get_graph(repo_path: Optional[str] = None):
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    def get_eid(element):
        if not element: return None
        if isinstance(element, (int, str)):
            return str(element)
        # Try various ways to get ID (Neo4j, FalkorDB, etc.)
        for attr in ['element_id', 'id', '_id']:
            if hasattr(element, attr):
                val = getattr(element, attr)
                if val is not None: return str(val)
        return str(id(element))

    try:
        nodes_dict = {}
        edges = []

        with db_manager.get_driver().session() as session:
            if repo_path:
                repo_path = str(Path(repo_path).resolve())
                # Optimized subgraph query
                query = """
                MATCH (r:Repository {path: $repo_path})
                OPTIONAL MATCH (r)-[:CONTAINS*0..]->(n)
                WITH DISTINCT n
                WHERE n IS NOT NULL
                OPTIONAL MATCH (n)-[rel]->(m)
                RETURN n, rel, m
                """
                result = session.run(query, repo_path=repo_path)
            else:
                query = "MATCH (n) OPTIONAL MATCH (n)-[rel]->(m) RETURN n, rel, m LIMIT 5000"
                result = session.run(query)

            for record in result:
                for key in ['n', 'm']:
                    node = record[key]
                    if node:
                        eid = get_eid(node)
                        if eid not in nodes_dict:
                            # FalkorDB / Neo4j labels compatibility
                            labels = []
                            if hasattr(node, 'labels'):
                                labels = list(node.labels)
                            
                            # FalkorDB / Neo4j properties compatibility
                            props = {}
                            if hasattr(node, 'properties'):
                                props = node.properties
                            elif hasattr(node, 'items'):
                                props = dict(node.items())
                                
                            nodes_dict[eid] = {
                                "id": eid,
                                "label": props.get('name', props.get('label', 'Unknown')),
                                "type": labels[0].lower() if labels else "default",
                                "file": props.get('path', ''),
                                "properties": props
                            }
                
                rel = record['rel']
                if rel:
                    rid = get_eid(rel)
                    
                    # FalkorDB / Neo4j compatibility for source/target nodes
                    start_node = getattr(rel, 'start_node', getattr(rel, 'src_node', None))
                    end_node = getattr(rel, 'end_node', getattr(rel, 'dest_node', None))
                    
                    source = get_eid(start_node)
                    target = get_eid(end_node)
                    
                    if source and target:
                        # relationship type/relation
                        rel_type = "related"
                        if hasattr(rel, 'type'):
                            rel_type = rel.type
                        elif hasattr(rel, 'relation'):
                            rel_type = rel.relation
                            
                        edges.append({
                            "id": rid,
                            "source": source,
                            "target": target,
                            "type": str(rel_type).lower()
                        })

        return {
            "nodes": list(nodes_dict.values()), 
            "edges": edges,
            "files": {}
        }

    except Exception as e:
        debug_log(f"Error fetching graph: {str(e)}")
        # Print stack trace for debugging if possible
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file")
async def get_file(path: str):
    file_path = Path(path).resolve()

    # Validate that the resolved path is within an allowed directory
    if not _allowed_dirs or not any(
        str(file_path).startswith(allowed) for allowed in _allowed_dirs
    ):
        raise HTTPException(status_code=403, detail="Access denied: path outside allowed directories")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# SPA fallback handler
@app.get("/{full_path:path}")
async def spa_fallback(request: Request, full_path: str):
    global _static_dir
    if not _static_dir:
        return HTMLResponse("Static directory not configured", status_code=500)
    
    # Filesystem path
    file_path = Path(_static_dir) / full_path
    
    # If the file exists and is a file, serve it normally (handled by StaticFiles usually, 
    # but we need this for routes that don't match StaticFiles mount)
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Otherwise serve index.html
    index_path = Path(_static_dir) / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    return HTMLResponse("Not Found", status_code=404)

def run_server(host: str = "127.0.0.1", port: int = 8000, static_dir: Optional[str] = None, allowed_dirs: Optional[List[str]] = None):
    global _static_dir, _allowed_dirs
    _static_dir = static_dir
    if allowed_dirs:
        _allowed_dirs = [str(Path(d).resolve()) for d in allowed_dirs]
    if static_dir:
        # Mount API first
        # We don't mount "/" with StaticFiles because we use spa_fallback for all routes
        pass

    uvicorn.run(app, host=host, port=port)
