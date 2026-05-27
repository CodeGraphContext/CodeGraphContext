import os
import sys
import subprocess
import zipfile
import json
import shutil
from pathlib import Path
import pytest

TEST_ROOT = Path(__file__).parent.parent.absolute()
GOLDENS_DIR = TEST_ROOT / "fixtures" / "goldens"
PROJECTS_DIR = TEST_ROOT / "fixtures" / "sample_projects"
WORKSPACE_ROOT = TEST_ROOT.parent.absolute()

# Standardize path strings to use forward slashes
def clean_path(p):
    return str(p).replace("\\", "/")

def get_logical_key(node, normalized_path):
    labels = node.get("_labels", [])
    primary_label = labels[0] if labels else "Unknown"
    
    # Extract unique identifiers
    name = node.get("name") or ""
    line_number = str(node.get("line_number") or "")
    function_line_number = str(node.get("function_line_number") or "")
    class_context = node.get("class_context") or ""
    context = node.get("context") or ""
    
    # Build logical key
    key_parts = [primary_label, name, normalized_path]
    if line_number:
        key_parts.append(f"ln_{line_number}")
    if function_line_number:
        key_parts.append(f"fln_{function_line_number}")
    if class_context:
        key_parts.append(f"class_{class_context}")
    elif context:
        key_parts.append(f"ctx_{context}")
        
    return ":".join(key_parts)

def make_hashable(val):
    if isinstance(val, list):
        return tuple(make_hashable(item) for item in val)
    if isinstance(val, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in val.items()))
    return val

def stable_node_sort_key(node):
    labels = node.get("_labels", [])
    primary_label = labels[0] if labels else ""
    path = node.get("path") or ""
    name = node.get("name") or ""
    line_number = int(node.get("line_number") or 0)
    function_line_number = int(node.get("function_line_number") or 0)
    
    # Extract clean items (excluding volatile keys) to make sorting 100% deterministic
    clean_items = sorted((k, make_hashable(v)) for k, v in node.items() if k not in ["_id", "id", "indexed_at", "commit_hash"])
    return (primary_label, path, name, line_number, function_line_number, tuple(clean_items))

def load_and_normalize(nodes_path, edges_path, current_repo_root):
    current_repo_root_str = clean_path(current_repo_root)
    original_repo_root_str = "/home/shashank/Desktop/cgc/CodeGraphContext"
    
    # 1. Load and normalize Nodes
    nodes = []
    if os.path.exists(nodes_path):
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    nodes.append(json.loads(line))
                    
    # Stable sorting to ensure deterministic duplication suffixes
    nodes.sort(key=stable_node_sort_key)
    
    # Normalize paths and strip volatile fields
    id_to_key = {}
    normalized_nodes = {}
    
    for idx, node in enumerate(nodes):
        node_id = node.get("_id") or node.get("id")
        
        # Normalize path
        path = node.get("path") or ""
        normalized_path = clean_path(path)
        normalized_path = normalized_path.replace(original_repo_root_str, "<REPO_ROOT>")
        normalized_path = normalized_path.replace(current_repo_root_str, "<REPO_ROOT>")
        
        # Build logical key
        logical_key = get_logical_key(node, normalized_path)
        
        # Avoid collisions in case of duplicate node names/lines
        base_key = logical_key
        collision_counter = 1
        while logical_key in normalized_nodes:
            logical_key = f"{base_key}_dup{collision_counter}"
            collision_counter += 1
            
        id_to_key[str(node_id)] = logical_key
        
        # Strip volatile fields
        clean_node = {k: v for k, v in node.items() if k not in ["_id", "id", "indexed_at", "commit_hash"]}
        if "path" in clean_node:
            clean_node["path"] = normalized_path
            
        # Clean source if it contains path strings
        if "source" in clean_node and isinstance(clean_node["source"], str):
            clean_node["source"] = clean_node["source"].replace(original_repo_root_str, "<REPO_ROOT>")
            clean_node["source"] = clean_node["source"].replace(current_repo_root_str, "<REPO_ROOT>")
            
        # Sort order-insensitive list fields to prevent db concurrent extraction order variation
        for list_field in ["bases", "decorators"]:
            if list_field in clean_node and isinstance(clean_node[list_field], list):
                clean_node[list_field] = sorted([x for x in clean_node[list_field] if x])
                
        normalized_nodes[logical_key] = clean_node

    # 2. Load and normalize Edges
    edges = []
    if os.path.exists(edges_path):
        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    edges.append(json.loads(line))
                    
    normalized_edges = set()
    for edge in edges:
        from_id = str(edge.get("from"))
        to_id = str(edge.get("to"))
        edge_type = edge.get("type")
        
        from_key = id_to_key.get(from_id)
        to_key = id_to_key.get(to_id)
        
        if from_key and to_key:
            # Normalize edge properties if any
            props = edge.get("properties") or {}
            clean_props = {}
            for k, v in props.items():
                if isinstance(v, str):
                    v = v.replace(original_repo_root_str, "<REPO_ROOT>").replace(current_repo_root_str, "<REPO_ROOT>")
                clean_props[k] = make_hashable(v)
                
            # Serialize props as a sorted tuple of items to make it hashable
            props_tuple = tuple(sorted(clean_props.items()))
            normalized_edges.add((from_key, to_key, edge_type, props_tuple))
            
    return normalized_nodes, normalized_edges

def get_goldens_list():
    if not GOLDENS_DIR.exists():
        return []
    return sorted([d.name for d in GOLDENS_DIR.iterdir() if d.is_dir()])

@pytest.mark.parametrize("project_name", get_goldens_list())
def test_language_golden(project_name, update_goldens, tmp_path):
    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        pytest.skip(f"Sample project {project_name} not found in fixtures.")
        
    golden_proj_dir = GOLDENS_DIR / project_name
    
    # "What I Wanted" (Remediated Perfect Targets)
    wanted_nodes_path = golden_proj_dir / "nodes.jsonl"
    wanted_edges_path = golden_proj_dir / "edges.jsonl"
    expected_metadata_path = golden_proj_dir / "metadata.json"
    
    # "What We Have" (Current Parser Capabilities Regression Baselines)
    have_nodes_path = golden_proj_dir / "nodes_have.jsonl"
    have_edges_path = golden_proj_dir / "edges_have.jsonl"
    
    # 1. Environment Setup (Clean FalkorDBLite database per test)
    env = os.environ.copy()
    env["CGC_RUNTIME_DB_TYPE"] = "falkordb"
    env["FALKORDB_PATH"] = str(tmp_path / "test_falkor.db")
    env["FALKORDB_SOCKET_PATH"] = str(tmp_path / "test_falkor.sock")
    
    # 2. Run Indexing programmatically
    index_res = subprocess.run(
        [sys.executable, "cgc_entry.py", "index", str(project_path), "-f"],
        env=env,
        capture_output=True,
        text=True
    )
    assert index_res.returncode == 0, f"Indexing failed for {project_name}:\nSTDOUT: {index_res.stdout}\nSTDERR: {index_res.stderr}"
    
    # 3. Export Bundle
    bundle_path = tmp_path / "export.cgc"
    export_res = subprocess.run(
        [sys.executable, "cgc_entry.py", "bundle", "export", str(bundle_path), "--repo", str(project_path)],
        env=env,
        capture_output=True,
        text=True
    )
    assert export_res.returncode == 0, f"Export failed for {project_name}:\nSTDOUT: {export_res.stdout}\nSTDERR: {export_res.stderr}"
    
    # 4. Extract Bundle
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()
    with zipfile.ZipFile(bundle_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    actual_nodes_path = extract_dir / "nodes.jsonl"
    actual_edges_path = extract_dir / "edges.jsonl"
    actual_metadata_path = extract_dir / "metadata.json"
    
    # 5. Handle --update-goldens Option
    if update_goldens:
        # Overwrite the regression baselines ("What We Have") with current raw actual outputs
        golden_proj_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(actual_nodes_path, have_nodes_path)
        shutil.copy2(actual_edges_path, have_edges_path)
        if actual_metadata_path.exists():
            shutil.copy2(actual_metadata_path, expected_metadata_path)
        print(f"\n[UPDATED] Regression baseline ('What We Have') updated successfully for {project_name}")
        return
        
    # 6. Verify "What We Have" Regression Baseline Exists
    if not have_nodes_path.exists() or not have_edges_path.exists():
        pytest.fail(
            f"Regression baseline files {have_nodes_path.name}/{have_edges_path.name} not found for {project_name}. "
            f"Please run the test suite with '--update-goldens' to bootstrap/initialize them first."
        )

    # 7. Normalize and Compare against "What We Have" Regression Baseline
    expected_nodes, expected_edges = load_and_normalize(have_nodes_path, have_edges_path, WORKSPACE_ROOT)
    actual_nodes, actual_edges = load_and_normalize(actual_nodes_path, actual_edges_path, WORKSPACE_ROOT)
    
    # Assert Nodes match exactly
    missing_nodes = {k: v for k, v in expected_nodes.items() if k not in actual_nodes}
    unexpected_nodes = {k: v for k, v in actual_nodes.items() if k not in expected_nodes}
    
    node_mismatch_details = []
    if missing_nodes:
        node_mismatch_details.append(f"Missing {len(missing_nodes)} expected nodes:\n" + "\n".join(f"  - {k}: {v}" for k, v in list(missing_nodes.items())[:5]))
    if unexpected_nodes:
        node_mismatch_details.append(f"Unexpected {len(unexpected_nodes)} actual nodes:\n" + "\n".join(f"  - {k}: {v}" for k, v in list(unexpected_nodes.items())[:5]))
        
    # Property comparisons for matched nodes
    property_mismatches = []
    for k in expected_nodes:
        if k in actual_nodes:
            exp_node = expected_nodes[k]
            act_node = actual_nodes[k]
            # Strip source field comparison if there are slight whitespace formatting differences
            if "source" in exp_node: exp_node["source"] = "".join(exp_node["source"].split())
            if "source" in act_node: act_node["source"] = "".join(act_node["source"].split())
            if exp_node != act_node:
                property_mismatches.append(f"Node property mismatch for key: {k}\n  Expected: {expected_nodes[k]}\n  Actual  : {actual_nodes[k]}")
                
    if property_mismatches:
        node_mismatch_details.append(f"{len(property_mismatches)} property mismatches:\n" + "\n".join(property_mismatches[:5]))
        
    assert not node_mismatch_details, f"Nodes regression mismatch for project {project_name}:\n" + "\n\n".join(node_mismatch_details)
    
    # Assert Edges match exactly
    missing_edges = expected_edges - actual_edges
    unexpected_edges = actual_edges - expected_edges
    
    edge_mismatch_details = []
    if missing_edges:
        edge_mismatch_details.append(f"Missing {len(missing_edges)} expected edges:\n" + "\n".join(f"  - {e[0]} --[{e[2]}]--> {e[1]} with props: {e[3]}" for e in list(missing_edges)[:5]))
    if unexpected_edges:
        edge_mismatch_details.append(f"Unexpected {len(unexpected_edges)} actual edges:\n" + "\n".join(f"  - {e[0]} --[{e[2]}]--> {e[1]} with props: {e[3]}" for e in list(unexpected_edges)[:5]))
        
    assert not edge_mismatch_details, f"Edges regression mismatch for project {project_name}:\n" + "\n\n".join(edge_mismatch_details)

    # 8. Compute and Print Gap Analysis against "What I Wanted"
    wanted_nodes, wanted_edges = load_and_normalize(wanted_nodes_path, wanted_edges_path, WORKSPACE_ROOT)
    
    missing_nodes_wanted = {k: v for k, v in wanted_nodes.items() if k not in actual_nodes}
    missing_edges_wanted = wanted_edges - actual_edges
    
    total_wanted_nodes = len(wanted_nodes)
    total_wanted_edges = len(wanted_edges)
    
    captured_nodes = total_wanted_nodes - len(missing_nodes_wanted)
    captured_edges = total_wanted_edges - len(missing_edges_wanted)
    
    node_coverage = (captured_nodes / total_wanted_nodes * 100) if total_wanted_nodes > 0 else 100.0
    edge_coverage = (captured_edges / total_wanted_edges * 100) if total_wanted_edges > 0 else 100.0
    
    sys.stdout.write(f"\n\n[GAP ANALYSIS - {project_name}]\n")
    sys.stdout.write(f"  Nodes: {captured_nodes}/{total_wanted_nodes} captured ({node_coverage:.1f}%)\n")
    sys.stdout.write(f"  Edges: {captured_edges}/{total_wanted_edges} captured ({edge_coverage:.1f}%)\n")
    if missing_nodes_wanted:
        sys.stdout.write(f"  Missing Nodes: {len(missing_nodes_wanted)} (perfect target has more)\n")
    if missing_edges_wanted:
        sys.stdout.write(f"  Missing Edges: {len(missing_edges_wanted)} (perfect target has more)\n")
    sys.stdout.flush()

