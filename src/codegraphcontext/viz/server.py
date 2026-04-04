from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uvicorn
import json
import os
import sys
from typing import Optional, List, Dict, Any

from ..core.database import DatabaseManager
from ..utils.debug_log import debug_log

app = FastAPI()

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database manager (will be initialized when server starts)
db_manager: Optional[DatabaseManager] = None
# Path to static directory
_static_dir: Optional[str] = None

def set_db_manager(manager: DatabaseManager):
    global db_manager
    db_manager = manager

@app.get("/api/graph")
async def get_graph(repo_path: Optional[str] = None, cypher_query: Optional[str] = None):
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    def get_eid(element):
        if element is None: return None
        if isinstance(element, (int, str)):
            return str(element)
        
        # If element is a dict (like Neo4j returned items or KuzuDB node/rel dicts)
        if isinstance(element, dict):
            # KuzuDB _src / _dst are directly {'offset': X, 'table': Y}
            if 'offset' in element and 'table' in element:
                return f"{element.get('table')}_{element.get('offset')}"
                
            for key in ['_id', 'id', 'element_id']:
                if key in element:
                    val = element[key]
                    if val is not None:
                        # KuzuDB returns dict IDs like {'offset': 1, 'table': 0} inside nodes
                        if isinstance(val, dict):
                            return f"{val.get('table', 0)}_{val.get('offset', 0)}"
                        return str(val)
            return str(id(element))
            
        # Try various ways to get ID (Neo4j, FalkorDB, etc. objects)
        for attr in ['element_id', 'id', '_id']:
            if hasattr(element, attr):
                val = getattr(element, attr)
                if val is not None: 
                    # KuzuDB objects if any
                    if isinstance(val, dict):
                        return f"{val.get('table', 0)}_{val.get('offset', 0)}"
                    return str(val)
        return str(id(element))

    try:
        nodes_dict = {}
        edges = []

        print(f"DEBUG: Starting get_graph with repo_path={repo_path}", flush=True)

        with db_manager.get_driver().session() as session:
            if cypher_query:
                print(f"DEBUG: Executing custom query: {cypher_query}", flush=True)
                result = session.run(cypher_query)
            elif repo_path:
                repo_path = str(Path(repo_path).resolve())
                print(f"DEBUG: Fetching subgraph for: {repo_path}", flush=True)
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
                print("DEBUG: Fetching global graph", flush=True)
                query = "MATCH (n) OPTIONAL MATCH (n)-[rel]->(m) RETURN n, rel, m LIMIT 50000"
                result = session.run(query)

            record_count = 0
            for record in result:
                record_count += 1
                # Use .get() to avoid KeyError if the query doesn't return all fields (n, rel, m)
                for key in ['n', 'm']:
                    try:
                        node = record.get(key)
                        if node:
                            eid = get_eid(node)
                            if eid and eid not in nodes_dict:
                                # Extract labels
                                labels = []
                                if isinstance(node, dict):
                                    # KuzuDB node label is under '_label'
                                    if '_label' in node:
                                        labels = [node['_label']]
                                    elif 'label' in node:
                                        labels = [node['label']]
                                else:
                                    for label_attr in ['_labels', 'labels']:
                                        if hasattr(node, label_attr):
                                            attr_val = getattr(node, label_attr)
                                            if attr_val:
                                                labels = list(attr_val)
                                                break
                                
                                # Extract properties
                                props = {}
                                if isinstance(node, dict):
                                    props = {k: v for k, v in node.items() if not k.startswith('_')}
                                else:
                                    for prop_attr in ['properties', '_properties']:
                                        if hasattr(node, prop_attr):
                                            attr_val = getattr(node, prop_attr)
                                            if attr_val:
                                                props = dict(attr_val)
                                                break
                                                
                                    # Fallback if props still empty but node acts like dict
                                    if not props and hasattr(node, 'items'):
                                        try:
                                            props = dict(node.items())
                                        except: pass
                                
                                # Extract name/label for frontend
                                # Prefer 'name' property, fallback to 'label', then 'path' or 'Unknown'
                                display_name = str(props.get('name', props.get('label', props.get('path', 'Unknown'))))
                                
                                nodes_dict[eid] = {
                                    "id": eid,
                                    "name": display_name,
                                    "label": display_name,
                                    "type": str(labels[0]).capitalize() if labels else "Other",
                                    "file": str(props.get('path', props.get('file', ''))),
                                    "val": 4 if (labels and labels[0] in ['Repository', 'Class', 'Interface', 'Trait']) else 2,
                                    "properties": props
                                }
                    except Exception as e:
                        print(f"DEBUG: Error parsing node: {e}", file=sys.stderr, flush=True)
                        continue
                
                try:
                    rel = record.get('rel')
                    if rel is not None:
                        # One-shot debug: print type and keys/attrs of first rel
                        if not edges:
                            if isinstance(rel, dict):
                                print(f"DEBUG rel (dict): keys={list(rel.keys())}", file=sys.stderr, flush=True)
                            else:
                                print(f"DEBUG rel (obj): type={type(rel).__name__}, attrs={[a for a in dir(rel) if not a.startswith('__')]}", file=sys.stderr, flush=True)

                        # FalkorDB / KuzuDB may return rels as dicts OR objects
                        if isinstance(rel, dict):
                            rid = get_eid(rel)
                            # KuzuDB uses _src and _dst, FalkorDB uses src_node/dest_node
                            src = rel.get('_src', rel.get('src_node'))
                            dst = rel.get('_dst', rel.get('dest_node'))
                            
                            source = get_eid(src) if src is not None else None
                            target = get_eid(dst) if dst is not None else None
                            rel_type = str(rel.get('_label', rel.get('relation', rel.get('type', 'RELATED')))).upper()
                        else:
                            rid = get_eid(rel)
                            start_node = None
                            end_node = None
                            for src_attr in ['start_node', 'src_node', '_src_node']:
                                if hasattr(rel, src_attr):
                                    start_node = getattr(rel, src_attr)
                                    break
                            for dest_attr in ['end_node', 'dest_node', '_dest_node']:
                                if hasattr(rel, dest_attr):
                                    end_node = getattr(rel, dest_attr)
                                    break
                            source = get_eid(start_node) if start_node is not None else None
                            target = get_eid(end_node) if end_node is not None else None
                            rel_type = "RELATED"
                            for rel_attr in ['type', 'relation', '_relation']:
                                if hasattr(rel, rel_attr):
                                    rel_type = str(getattr(rel, rel_attr)).upper()
                                    break

                        if source and target:
                            edges.append({
                                "id": rid,
                                "source": source,
                                "target": target,
                                "type": rel_type
                            })
                except Exception as e:
                    print(f"DEBUG: Error parsing relationship: {e}", file=sys.stderr, flush=True)
                    pass

        print(f"DEBUG: Processed {record_count} records. extracted {len(nodes_dict)} nodes and {len(edges)} edges.", file=sys.stderr, flush=True)

        # Build a list of unique file paths from File-type nodes for the tree
        file_paths = []
        for n in nodes_dict.values():
            if n.get("file") and str(n.get("type", "")).lower() == "file":
                file_paths.append(str(n["file"]))
        file_paths = sorted(list(set(file_paths)))

        response_data = {
            "nodes": list(nodes_dict.values()), 
            "links": edges,
            "files": file_paths,
        }
        
        print(f"API SUCCESS: Returning graph with {len(response_data['nodes'])} nodes and {len(response_data['links'])} links.", file=sys.stderr, flush=True)
        return response_data

    except Exception as e:
        debug_log(f"Error fetching graph: {str(e)}")
        import traceback
        traceback.print_exc()
        # Still return a valid structure so the frontend doesn't crash, but with 500 status if raised
        # Actually, let's just return a 500 error but with JSON body if possible
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file")
async def get_file(path: str):
    file_path = Path(path)
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
    
    # If the file exists and is a file, serve it normally
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Otherwise serve index.html (Standard SPA routing)
    index_path = Path(_static_dir) / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    return HTMLResponse("Not Found (Built UI not found in viz/dist)", status_code=404)

def run_server(host: str = "127.0.0.1", port: int = 8000, static_dir: Optional[str] = None):
    global _static_dir
    _static_dir = static_dir
    uvicorn.run(app, host=host, port=port)
