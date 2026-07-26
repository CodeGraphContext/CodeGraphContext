from __future__ import annotations
# src/codegraphcontext/viz/server.py
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uvicorn
import json
import os
import sys
import re
import requests
import traceback
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.database import DatabaseManager
from ..utils.debug_log import debug_log
from ..utils.path_sandbox import is_path_allowed
from ..utils.cypher_readonly import is_read_only_cypher as _is_read_only_cypher, read_only_rejection_message

app = FastAPI()


def _read_session_kwargs(manager) -> dict:
    """Session kwargs that request READ access for read-only endpoints.

    Neo4j honours ``default_access_mode`` natively; the FalkorDB wrapper routes
    READ sessions through ``GRAPH.RO_QUERY`` for server-enforced read-only
    execution. Other backends' session shims ignore unknown kwargs, so this is
    safe to pass unconditionally for those we know enforce it.
    """
    backend = getattr(manager, "get_backend_type", lambda: "neo4j")()
    if backend in ("neo4j", "falkordb", "falkordb-remote"):
        return {"default_access_mode": "READ"}
    return {}


def _static_root() -> Path:
    if not _static_dir:
        raise HTTPException(status_code=500, detail="Static directory not configured")
    return Path(_static_dir).resolve()


def _safe_static_file(relative_path: str) -> Path:
    """Resolve *relative_path* under the static root; reject traversal."""
    root = _static_root()
    candidate = (root / relative_path).resolve()
    if not is_path_under_static(candidate, root):
        raise HTTPException(status_code=403, detail="Access denied")
    return candidate


def is_path_under_static(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_read_text_file(path: str) -> str:
    file_path = Path(path).resolve()
    if not is_path_allowed(file_path):
        raise HTTPException(status_code=403, detail="File path is outside allowed roots")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()

# CORS: only allow requests from the local visualization frontend.
# The server binds to 127.0.0.1 (localhost) so only local origins are legitimate.
_ALLOWED_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Global database manager (will be initialized when server starts)
db_manager: Optional[DatabaseManager] = None
# Path to static directory
_static_dir: Optional[str] = None

def set_db_manager(manager: DatabaseManager):
    global db_manager
    db_manager = manager

def _get_eid(element):
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


@app.get("/api/graph")
async def get_graph(repo_path: Optional[str] = None, cypher_query: Optional[str] = None):
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    get_eid = _get_eid

    try:
        nodes_dict = {}
        edges = []

        print(f"DEBUG: Starting get_graph with repo_path={repo_path}", flush=True)

        # This endpoint only ever reads. Open the session in READ access mode so
        # the database enforces read-only (Neo4j default_access_mode / FalkorDB
        # GRAPH.RO_QUERY) in addition to the regex guard on any user query.
        with db_manager.get_driver().session(**_read_session_kwargs(db_manager)) as session:
            if cypher_query:
                if not _is_read_only_cypher(cypher_query):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "This endpoint only supports read-only Cypher queries. "
                            "Prohibited keywords like CREATE, MERGE, DELETE, SET, REMOVE, "
                            "DROP, or CALL apoc are not allowed."
                        ),
                    )
                print(f"DEBUG: Executing custom query: {cypher_query}", flush=True)
                result = session.run(cypher_query)
            elif repo_path:
                repo_path = str(Path(repo_path).resolve())
                print(f"DEBUG: Fetching subgraph for: {repo_path}", flush=True)
                # Get all nodes within the repository scope
                query = """
                MATCH (r:Repository {path: $repo_path})
                OPTIONAL MATCH (r)-[:CONTAINS*0..]->(n)
                WITH DISTINCT r, COLLECT(DISTINCT n) as repo_nodes
                UNWIND repo_nodes as node
                OPTIONAL MATCH (node)-[rel]->(target)
                WITH r, node, rel, target, repo_nodes
                WHERE target IN repo_nodes OR target = r
                RETURN node as n, rel, target as m
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

        # Read file contents so the frontend never needs a separate API call
        file_contents: dict[str, str] = {}
        for fp in file_paths:
            try:
                resolved = Path(fp).resolve()
                if not is_path_allowed(resolved):
                    continue
                file_contents[fp] = _safe_read_text_file(str(resolved))
            except HTTPException:
                continue
            except Exception:
                pass

        response_data = {
            "nodes": list(nodes_dict.values()), 
            "links": edges,
            "files": file_paths,
            "fileContents": file_contents,
        }
        
        print(f"API SUCCESS: Returning graph with {len(response_data['nodes'])} nodes and {len(response_data['links'])} links.", file=sys.stderr, flush=True)
        return response_data

    except HTTPException:
        # Preserve intentional HTTP errors (e.g. 400 for forbidden write queries).
        raise
    except Exception as e:
        debug_log(f"Error fetching graph: {str(e)}")
        import traceback
        traceback.print_exc()
        # Still return a valid structure so the frontend doesn't crash, but with 500 status if raised
        # Actually, let's just return a 500 error but with JSON body if possible
        raise HTTPException(status_code=500, detail=str(e))

def call_llm(system_prompt: str, user_prompt: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not gemini_key and not openai_key:
        raise ValueError("Neither GEMINI_API_KEY nor OPENAI_API_KEY environment variable is set.")
    
    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nUser Prompt:\n{user_prompt}"}]
                }
            ]
        }
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"Gemini API returned error {res.status_code}: {res.text}")
        data = res.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Failed to parse Gemini API response: {data}") from e
    else:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"OpenAI API returned error {res.status_code}: {res.text}")
        data = res.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Failed to parse OpenAI API response: {data}") from e


def parse_json_from_llm(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    else:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse valid JSON from LLM response:\n{text}")


def parse_node(node, nodes_dict):
    eid = _get_eid(node)
    if not eid or eid in nodes_dict:
        return
        
    labels = []
    if isinstance(node, dict):
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
        if not props and hasattr(node, 'items'):
            try:
                props = dict(node.items())
            except: pass
            
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


def parse_rel(rel, edges):
    rid = _get_eid(rel)
    if isinstance(rel, dict):
        src = rel.get('_src', rel.get('src_node'))
        dst = rel.get('_dst', rel.get('dest_node'))
        source = _get_eid(src) if src is not None else None
        target = _get_eid(dst) if dst is not None else None
        rel_type = str(rel.get('_label', rel.get('relation', rel.get('type', 'RELATED')))).upper()
    else:
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
        source = _get_eid(start_node) if start_node is not None else None
        target = _get_eid(end_node) if end_node is not None else None
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


def parse_element(val, nodes_dict, edges):
    if val is None:
        return
    
    # If it is a Path
    if hasattr(val, 'nodes') and hasattr(val, 'relationships'):
        for n in val.nodes:
            parse_element(n, nodes_dict, edges)
        for r in val.relationships:
            parse_element(r, nodes_dict, edges)
        return
        
    type_name = type(val).__name__
    
    if type_name in ('Node', 'KuzuNode') or (isinstance(val, dict) and ('_label' in val or 'labels' in val) and not any(k in val for k in ('_src', '_dst', 'src_node', 'dest_node'))):
        parse_node(val, nodes_dict)
    elif type_name in ('Relationship', 'KuzuRelationship') or (isinstance(val, dict) and any(k in val for k in ('_src', '_dst', 'src_node', 'dest_node'))):
        parse_rel(val, edges)
    elif isinstance(val, (list, tuple)):
        for item in val:
            parse_element(item, nodes_dict, edges)


class AIQueryRequest(BaseModel):
    query: str
    repo_path: Optional[str] = None


@app.post("/api/ai_query")
async def ai_query(request: AIQueryRequest):
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")
        
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not gemini_key and not openai_key:
        raise HTTPException(
            status_code=400,
            detail="AI querying requires GEMINI_API_KEY or OPENAI_API_KEY environment variable. Please set it in your configuration or .env."
        )
        
    query = request.query
    repo_path = request.repo_path
    
    translation_prompt = """You are an expert graph database administrator. Translate the user's natural language question about a codebase into a valid read-only Cypher query.

The graph database represents the codebase structure with the following schema:
### Nodes & Properties:
* **`Repository`**: `name` (string), `path` (string, absolute path), `is_dependency` (boolean)
* **`File`**: `name` (string), `path` (string, absolute path), `relative_path` (string), `is_dependency` (boolean)
* **`Function`**: `name` (string), `path` (string, absolute path), `line_number` (int), `end_line` (int), `args` (list of strings), `cyclomatic_complexity` (int), `decorators` (list of strings), `lang` (string), `source` (string), `is_dependency` (boolean)
* **`Class`**: `name` (string), `path` (string, absolute path), `line_number` (int), `end_line` (int), `bases` (list of strings), `decorators` (list of strings), `lang` (string), `source` (string), `is_dependency` (boolean)
* **`Interface`**, **`Struct`**, **`Enum`**, **`Trait`**: similar properties to Class/Function
* **`Module`**: `name` (string)

### Relationships:
* **`CONTAINS`**: (Repository)-[:CONTAINS]->(File), (File)-[:CONTAINS]->(Function), (File)-[:CONTAINS]->(Class)
* **`CALLS`**: (Function)-[:CALLS]->(Function)
* **`IMPORTS`**: (File)-[:IMPORTS]->(Module)
* **`INHERITS`**: (Class)-[:INHERITS]->(Class)
* **`IMPLEMENTS`**: (Class)-[:IMPLEMENTS]->(Interface)

### Query Writing Rules:
1. Only write SELECT/MATCH read-only queries. Do NOT use CREATE, MERGE, DELETE, SET, REMOVE, or other modifying keywords.
2. Return nodes using the variable names `n` and `m`, and relationships using `rel` where possible. This is critical for the visualizer.
   Example: MATCH (n:Class)-[rel:INHERITS]->(m:Class) RETURN n, rel, m
3. Keep the query simple and efficient. Limit results using `LIMIT 150` unless more are needed.
4. If the user asks about dependencies or paths, try to return paths using variables, and return nodes/relationships.
5. Make property matches case-insensitive or fuzzy if appropriate (e.g. using `toLower(n.name) CONTAINS 'auth'` or `n.name =~ '(?i).*auth.*'`).
6. If the user is querying a specific repository, you can filter by `Repository.path` or `Repository.name` if path is supplied.

Respond ONLY with a JSON object in this format:
{
  "cypher_query": "MATCH ... RETURN n, rel, m LIMIT 100",
  "explanation": "Brief description of what this Cypher query does"
}
"""
    
    try:
        # Call LLM to get Cypher
        llm_response = call_llm(translation_prompt, query)
        parsed_response = parse_json_from_llm(llm_response)
        cypher_query = parsed_response.get("cypher_query", "")
        translation_explanation = parsed_response.get("explanation", "")
        
        if not cypher_query:
            raise ValueError("No Cypher query was generated by the AI.")
            
        # Validate Cypher
        if not _is_read_only_cypher(cypher_query):
            raise HTTPException(
                status_code=400,
                detail=f"The generated Cypher query was rejected for safety reasons: {read_only_rejection_message()}"
            )
            
        # Step 2: Run Cypher query
        nodes_dict = {}
        edges = []
        records_data = []

        with db_manager.get_driver().session(**_read_session_kwargs(db_manager)) as session:
            result = session.run(cypher_query)
            for record in result:
                # Store truncated record data for explanation phase
                record_dict = {}
                for k, v in record.items():
                    if isinstance(v, dict):
                        record_dict[k] = {prop_k: (prop_v[:200] + "..." if isinstance(prop_v, str) and len(prop_v) > 200 else prop_v) for prop_k, prop_v in v.items()}
                    elif hasattr(v, 'properties'):
                        props = dict(v.properties)
                        record_dict[k] = {prop_k: (prop_v[:200] + "..." if isinstance(prop_v, str) and len(prop_v) > 200 else prop_v) for prop_k, prop_v in props.items()}
                    else:
                        record_dict[k] = str(v)[:200] + "..." if isinstance(v, str) and len(v) > 200 else v
                records_data.append(record_dict)
                
                # Parse elements for visualization
                for val in record.values():
                    parse_element(val, nodes_dict, edges)
                    
        # Truncate results for LLM context (e.g. limit to first 30 records to save tokens)
        results_for_explanation = records_data[:30]
        results_json = json.dumps(results_for_explanation, indent=2)
        
        # Step 3: Generate Explanation
        explanation_prompt = f"""You are an expert software developer and repository assistant. Explain the answer to the user's question about the codebase based on the query results.

User Question: {query}
Cypher Query Executed: {cypher_query}
Query Results (truncated if large):
{results_json}

Write a clear, concise, and professional explanation of the results in Markdown format.
Focus on explaining:
1. What the query found.
2. The architectural relationships between the components.
3. How this answers the user's question.

After your explanation, provide a section:
### Context-Aware Recommendations
Suggest 2-3 specific follow-up questions or related areas the user might want to explore based on this result. Keep suggestions bulleted and actionable.
"""
        explanation = call_llm(explanation_prompt, "Explain the results.")
        
        return {
            "success": True,
            "cypher_query": cypher_query,
            "translation_explanation": translation_explanation,
            "explanation": explanation,
            "nodes": list(nodes_dict.values()),
            "links": edges
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/file")
async def get_file(path: str):
    try:
        return {"content": _safe_read_text_file(path)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# SPA fallback handler
@app.get("/{full_path:path}")
async def spa_fallback(request: Request, full_path: str):
    try:
        root = _static_root()
    except HTTPException as exc:
        return HTMLResponse(exc.detail, status_code=exc.status_code)

    try:
        file_path = _safe_static_file(full_path)
    except HTTPException:
        file_path = None

    if file_path and file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    index_path = root / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    return HTMLResponse("Not Found (Built UI not found in viz/dist)", status_code=404)

def run_server(host: str = "127.0.0.1", port: int = 8000, static_dir: Optional[str] = None):
    global _static_dir
    _static_dir = static_dir
    uvicorn.run(app, host=host, port=port)
