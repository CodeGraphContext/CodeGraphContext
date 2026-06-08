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
VOLATILE_NODE_KEYS = {"_id", "id", "indexed_at", "commit_hash", "uid", "bases", "type"}
CONTAINER_KEY_LABELS = {"Function", "Macro"}
GENERATED_BUILD_DIRS = {"obj"}

# Standardize path strings to use forward slashes
def clean_path(p):
    return str(p).replace("\\", "/")

def normalize_labels(labels):
    if labels is None:
        return []
    if isinstance(labels, str):
        return [labels]
    return list(labels)

def normalize_path(p, current_repo_root, bundle_repo_root=None):
    normalized_path = clean_path(p)

    if bundle_repo_root:
        bundle_repo_root_str = clean_path(bundle_repo_root)
        if normalized_path == ".":
            normalized_path = bundle_repo_root_str
        elif normalized_path.startswith("./"):
            normalized_path = f"{bundle_repo_root_str}/{normalized_path[2:]}"

    original_repo_root_str = "/home/shashank/Desktop/cgc/CodeGraphContext"
    current_repo_root_str = clean_path(current_repo_root)
    normalized_path = normalized_path.replace(original_repo_root_str, "<REPO_ROOT>")
    normalized_path = normalized_path.replace(current_repo_root_str, "<REPO_ROOT>")
    return normalized_path

def is_generated_build_artifact(normalized_path):
    path_parts = [part for part in normalized_path.split("/") if part]
    return any(part in GENERATED_BUILD_DIRS for part in path_parts)

def get_logical_key(node, normalized_path):
    labels = normalize_labels(node.get("_labels") or node.get("_label"))
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
    container_context = class_context or context
    if container_context and primary_label in CONTAINER_KEY_LABELS:
        key_parts.append(f"ctx_{container_context}")
        
    return ":".join(key_parts)

def make_hashable(val):
    if isinstance(val, list):
        return tuple(make_hashable(item) for item in val)
    if isinstance(val, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in val.items()))
    return val

def normalize_id(val):
    return repr(make_hashable(val))

def stable_node_sort_key(node):
    labels = normalize_labels(node.get("_labels") or node.get("_label"))
    primary_label = labels[0] if labels else ""
    path = node.get("path") or ""
    name = node.get("name") or ""
    line_number = int(node.get("line_number") or 0)
    function_line_number = int(node.get("function_line_number") or 0)
    
    # Extract clean items (excluding volatile keys) to make sorting 100% deterministic
    sort_node = dict(node)
    sort_node["_labels"] = labels
    sort_node.pop("_label", None)
    clean_items = sorted((k, make_hashable(v)) for k, v in sort_node.items() if k not in VOLATILE_NODE_KEYS and v is not None)
    return (primary_label, path, name, line_number, function_line_number, tuple(clean_items))

def load_and_normalize(nodes_path, edges_path, current_repo_root, bundle_repo_root=None):
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
        node["_labels"] = normalize_labels(node.get("_labels") or node.get("_label"))
        node.pop("_label", None)
        
        # Normalize path
        path = node.get("path") or ""
        normalized_path = normalize_path(path, current_repo_root, bundle_repo_root)
        if is_generated_build_artifact(normalized_path):
            continue
        
        # Build logical key
        logical_key = get_logical_key(node, normalized_path)
        
        # Avoid collisions in case of duplicate node names/lines
        base_key = logical_key
        collision_counter = 1
        while logical_key in normalized_nodes:
            logical_key = f"{base_key}_dup{collision_counter}"
            collision_counter += 1
            
        id_to_key[normalize_id(node_id)] = logical_key
        
        # Strip volatile fields
        clean_node = {k: v for k, v in node.items() if k not in VOLATILE_NODE_KEYS and v is not None}
        if "path" in clean_node:
            clean_node["path"] = normalized_path
            
        # Clean source if it contains path strings
        if "source" in clean_node and isinstance(clean_node["source"], str):
            clean_node["source"] = normalize_path(clean_node["source"], current_repo_root)

        if clean_node.get("class_context") == clean_node.get("context"):
            clean_node.pop("class_context", None)
            
        # Sort order-insensitive list fields to prevent db concurrent extraction order variation
        for list_field in ["decorators"]:
            if list_field in clean_node and isinstance(clean_node[list_field], list):
                normalized_list = sorted([x for x in clean_node[list_field] if x])
                if normalized_list:
                    clean_node[list_field] = normalized_list
                else:
                    clean_node.pop(list_field)
                
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
        from_id = normalize_id(edge.get("from"))
        to_id = normalize_id(edge.get("to"))
        edge_type = edge.get("type")
        # CALLS edges are generated by heuristic resolver fallbacks whose
        # confidence tiers and candidate choices vary across parser/backend
        # versions. Parser goldens still assert nodes and structural edges.
        if edge_type == "CALLS":
            continue
        
        from_key = id_to_key.get(from_id)
        to_key = id_to_key.get(to_id)
        
        if from_key and to_key:
            # Normalize edge properties if any
            props = edge.get("properties") or {}
            clean_props = {}
            for k, v in props.items():
                if k == "args_key":
                    continue
                if isinstance(v, str):
                    v = normalize_path(v, current_repo_root, bundle_repo_root if "path" in k else None)
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
    test_home = tmp_path / "home"
    test_home.mkdir()
    env["HOME"] = str(test_home)
    env["USERPROFILE"] = str(test_home)
    env["SCIP_INDEXER"] = "false"
    env["ENABLE_INHERIT_RESOLVE"] = "false"
    env["ENABLE_VECTOR_RESOLVE"] = "false"
    env["CGC_RUNTIME_DB_TYPE"] = "falkordb"
    env["FALKORDB_PATH"] = str(tmp_path / "test_falkor.db")
    env["FALKORDB_SOCKET_PATH"] = str(tmp_path / "test_falkor.sock")
    src_path = str(WORKSPACE_ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    # 2-3. Run indexing and export in one interpreter. FalkorDB Lite runs in a
    # worker subprocess; keeping both commands in the same parent process avoids
    # depending on Redis persistence timing between separate CLI invocations.
    bundle_path = tmp_path / "export.cgc"
    index_and_export_script = """
import sys

from codegraphcontext.cli.main import bundle_export, index

project_path = sys.argv[1]
bundle_path = sys.argv[2]

index(path=project_path, force=True, context=None)
bundle_export(output=bundle_path, repo=project_path, no_stats=False, context=None)
"""
    run_res = subprocess.run(
        [sys.executable, "-c", index_and_export_script, str(project_path), str(bundle_path)],
        env=env,
        capture_output=True,
        text=True
    )
    assert run_res.returncode == 0, f"Index/export failed for {project_name}:\nSTDOUT: {run_res.stdout}\nSTDERR: {run_res.stderr}"
    assert bundle_path.exists(), f"Bundle export did not create {bundle_path} for {project_name}:\nSTDOUT: {run_res.stdout}\nSTDERR: {run_res.stderr}"
    
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
    expected_nodes, expected_edges = load_and_normalize(have_nodes_path, have_edges_path, WORKSPACE_ROOT, project_path)
    actual_nodes, actual_edges = load_and_normalize(actual_nodes_path, actual_edges_path, WORKSPACE_ROOT, project_path)
    
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
            if isinstance(exp_node.get("source"), str): exp_node["source"] = "".join(exp_node["source"].split())
            if isinstance(act_node.get("source"), str): act_node["source"] = "".join(act_node["source"].split())
            common_keys = set(exp_node).intersection(act_node)
            exp_common = {prop: exp_node[prop] for prop in common_keys}
            act_common = {prop: act_node[prop] for prop in common_keys}
            if exp_common != act_common:
                property_mismatches.append(f"Node property mismatch for key: {k}\n  Expected: {exp_common}\n  Actual  : {act_common}")
                
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
    wanted_nodes, wanted_edges = load_and_normalize(wanted_nodes_path, wanted_edges_path, WORKSPACE_ROOT, project_path)
    
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
