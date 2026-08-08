# src/codegraphcontext/core/simulator.py
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from codegraphcontext.utils.debug_log import info_logger, error_logger, warning_logger


def resolve_node_id(row: Dict[str, Any]) -> str:
    """Helper to get a unique identifier for a node based on its properties."""
    uid = row.get("uid")
    if uid:
        return str(uid)
    path = row.get("path")
    if path:
        return str(path)
    name = row.get("name")
    if name:
        return str(name)
    return "unknown"


class CodeGraphTwin:
    """In-memory representation of the Code Graph for architectural simulations."""

    def __init__(self, repository_path: str):
        self.repository_path = Path(repository_path).resolve().as_posix()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.service_mapping: Dict[str, str] = {}
        self.repo_name = Path(repository_path).name

    def load_from_db(self, db_manager) -> "CodeGraphTwin":
        """Fetches the repository structure and relationships from the database."""
        info_logger(f"Loading digital twin from DB for repo path: {self.repository_path}")
        
        # 1. Fetch all nodes contained by the repository
        node_query = """
        MATCH (r:Repository {path: $path})
        OPTIONAL MATCH (r)-[:CONTAINS*]->(n)
        RETURN 
          r.path as repo_path, r.name as repo_name,
          labels(n)[0] as label,
          n.uid as uid,
          n.name as name,
          n.path as path,
          n.cyclomatic_complexity as complexity
        """
        
        # 2. Fetch all relationships originating from nodes in the repository
        rel_query = """
        MATCH (r:Repository {path: $path})
        MATCH (n1) WHERE n1 = r OR (r)-[:CONTAINS*]->(n1)
        MATCH (n1)-[rel]->(n2)
        RETURN 
          labels(n1)[0] as source_label,
          n1.uid as source_uid,
          n1.path as source_path,
          n1.name as source_name,
          type(rel) as rel_type,
          labels(n2)[0] as target_label,
          n2.uid as target_uid,
          n2.path as target_path,
          n2.name as target_name
        """
        
        with db_manager.get_driver().session() as session:
            node_rows = session.run(node_query, path=self.repository_path).data()
            rel_rows = session.run(rel_query, path=self.repository_path).data()

        # Build nodes
        for row in node_rows:
            label = row.get("label")
            if not label:
                # If repository is empty or n is null
                if row.get("repo_name"):
                    self.repo_name = row.get("repo_name")
                continue
            
            node_id = resolve_node_id(row)
            self.nodes[node_id] = {
                "id": node_id,
                "label": label,
                "name": row.get("name") or "unknown",
                "path": row.get("path"),
                "complexity": row.get("complexity"),
                "is_external": False
            }

        # Build edges
        for row in rel_rows:
            s_uid = row.get("source_uid")
            s_path = row.get("source_path")
            s_name = row.get("source_name")
            s_label = row.get("source_label")
            
            t_uid = row.get("target_uid")
            t_path = row.get("target_path")
            t_name = row.get("target_name")
            t_label = row.get("target_label")
            
            source_id = resolve_node_id({"uid": s_uid, "path": s_path, "name": s_name})
            target_id = resolve_node_id({"uid": t_uid, "path": t_path, "name": t_name})
            rel_type = row.get("rel_type")
            
            # Ensure source and target nodes exist (target might be external)
            if source_id not in self.nodes and source_id != "unknown":
                self.nodes[source_id] = {
                    "id": source_id,
                    "label": s_label or "Unknown",
                    "name": s_name or "unknown",
                    "path": s_path,
                    "complexity": None,
                    "is_external": True
                }
            if target_id not in self.nodes and target_id != "unknown":
                self.nodes[target_id] = {
                    "id": target_id,
                    "label": t_label or "Unknown",
                    "name": t_name or "unknown",
                    "path": t_path,
                    "complexity": None,
                    "is_external": True
                }
                
            if source_id != "unknown" and target_id != "unknown" and rel_type:
                self.edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": rel_type
                })

        self.auto_partition_services()
        return self

    def auto_partition_services(self):
        """Automatically partitions repository nodes into services based on directory structures."""
        self.service_mapping = {}
        for nid, ndata in self.nodes.items():
            if ndata.get("is_external"):
                self.service_mapping[nid] = "External"
                continue
            
            path = ndata.get("path")
            if not path:
                self.service_mapping[nid] = "Default"
                continue
                
            try:
                rel_path = Path(path).relative_to(Path(self.repository_path))
                parts = rel_path.parts
                if len(parts) > 1:
                    # Use first directory as service name
                    self.service_mapping[nid] = parts[0]
                else:
                    self.service_mapping[nid] = "Root"
            except Exception:
                self.service_mapping[nid] = "Default"

    # --- Mutation Operations ---

    def decompose_service(self, mapping: Dict[str, str]):
        """Sets custom service boundaries. Mapping is node_id or path -> service_name."""
        for target, service in mapping.items():
            # Check if target is a node_id
            if target in self.nodes:
                self.service_mapping[target] = service
            else:
                # Treat target as path prefix/substring
                target_norm = Path(target).as_posix()
                for nid, ndata in self.nodes.items():
                    npath = ndata.get("path")
                    if npath and (target_norm in npath or npath.startswith(target_norm)):
                        self.service_mapping[nid] = service

    def remove_dependency(self, source_id: str, target_id: str, rel_type: Optional[str] = None):
        """Simulates removing dependency edges."""
        new_edges = []
        for e in self.edges:
            matches_source = (e["source"] == source_id or self.nodes.get(e["source"], {}).get("name") == source_id)
            matches_target = (e["target"] == target_id or self.nodes.get(e["target"], {}).get("name") == target_id)
            matches_type = (rel_type is None or e["type"] == rel_type)
            if matches_source and matches_target and matches_type:
                continue
            new_edges.append(e)
        self.edges = new_edges

    def add_dependency(self, source_id: str, target_id: str, rel_type: str):
        """Simulates adding a new dependency edge."""
        if source_id in self.nodes and target_id in self.nodes:
            self.edges.append({
                "source": source_id,
                "target": target_id,
                "type": rel_type
            })

    def remove_node(self, node_id: str):
        """Simulates deleting a class, function, or file."""
        target_ids = {node_id}
        if node_id not in self.nodes:
            # Match by name or path
            for nid, ndata in self.nodes.items():
                if ndata.get("name") == node_id or ndata.get("path") == node_id:
                    target_ids.add(nid)
                    
        for tid in target_ids:
            if tid in self.nodes:
                del self.nodes[tid]
                if tid in self.service_mapping:
                    del self.service_mapping[tid]
        
        self.edges = [e for e in self.edges if e["source"] not in target_ids and e["target"] not in target_ids]

    # --- Metrics Calculations ---

    def calculate_coupling(self) -> Dict[str, Any]:
        """Computes Afferent/Efferent coupling and instability per service."""
        services = set(self.service_mapping.values())
        coupling_data = {}
        
        # Initialize
        for s in services:
            coupling_data[s] = {
                "afferent_coupling_nodes": set(),
                "efferent_coupling_nodes": set(),
                "ca": 0,  # Afferent coupling (incoming dependencies count)
                "ce": 0,  # Efferent coupling (outgoing dependencies count)
                "instability": 0.0
            }

        # Calculate
        for e in self.edges:
            # We only care about CALLS, INHERITS, IMPORTS for coupling metrics
            if e["type"] == "CONTAINS":
                continue
                
            src_service = self.service_mapping.get(e["source"], "Unknown")
            tgt_service = self.service_mapping.get(e["target"], "Unknown")
            
            if src_service != tgt_service:
                coupling_data[src_service]["efferent_coupling_nodes"].add(e["target"])
                coupling_data[tgt_service]["afferent_coupling_nodes"].add(e["source"])

        # Compute scores
        total_inter_service_edges = 0
        for s, data in coupling_data.items():
            data["ca"] = len(data["afferent_coupling_nodes"])
            data["ce"] = len(data["efferent_coupling_nodes"])
            total_inter_service_edges += data["ce"]
            
            total_c = data["ca"] + data["ce"]
            data["instability"] = float(data["ce"]) / total_c if total_c > 0 else 0.0
            
            # Clean sets for JSON serialization
            del data["afferent_coupling_nodes"]
            del data["efferent_coupling_nodes"]

        return {
            "services": coupling_data,
            "total_inter_service_dependencies": total_inter_service_edges
        }

    def calculate_cohesion(self) -> Dict[str, Any]:
        """Computes cohesion metrics per service."""
        services = set(self.service_mapping.values())
        cohesion_data = {}
        
        for s in services:
            cohesion_data[s] = {
                "nodes_count": 0,
                "internal_edges": 0,
                "external_outgoing_edges": 0,
                "cohesion_density": 1.0,
                "internal_edge_ratio": 1.0
            }
            
        for nid, svc in self.service_mapping.items():
            cohesion_data[svc]["nodes_count"] += 1

        for e in self.edges:
            if e["type"] == "CONTAINS":
                continue
            src_service = self.service_mapping.get(e["source"], "Unknown")
            tgt_service = self.service_mapping.get(e["target"], "Unknown")
            
            if src_service == tgt_service:
                cohesion_data[src_service]["internal_edges"] += 1
            else:
                cohesion_data[src_service]["external_outgoing_edges"] += 1

        for s, data in cohesion_data.items():
            v = data["nodes_count"]
            e_int = data["internal_edges"]
            e_ext = data["external_outgoing_edges"]
            
            # Cohesion density: internal_edges / (nodes * (nodes - 1))
            if v > 1:
                data["cohesion_density"] = float(e_int) / (v * (v - 1))
            else:
                data["cohesion_density"] = 1.0
                
            # Internal edge ratio: internal_edges / total_outgoing_edges
            total_out = e_int + e_ext
            if total_out > 0:
                data["internal_edge_ratio"] = float(e_int) / total_out
            else:
                data["internal_edge_ratio"] = 1.0

        return cohesion_data

    def find_strongly_connected_components(self) -> List[List[str]]:
        """Identifies circular dependencies using Tarjan's SCC algorithm."""
        # Build adjacency list (excluding CONTAINS relationships)
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            if e["type"] == "CONTAINS":
                continue
            src = e["source"]
            tgt = e["target"]
            if src in adj and tgt in adj:
                adj[src].append(tgt)

        index = 0
        stack: List[str] = []
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {}
        sccs: List[List[str]] = []

        def strongconnect(v: str):
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack[v] = True

            for w in adj.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack.get(w, False):
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                sccs.append(scc)

        for nid in self.nodes:
            if nid not in indices:
                strongconnect(nid)

        # Filter out trivial SCCs (single nodes without self-loops)
        circular_sccs = []
        for scc in sccs:
            if len(scc) > 1:
                circular_sccs.append(scc)
            elif len(scc) == 1:
                node = scc[0]
                if node in adj.get(node, []):  # Self-loop
                    circular_sccs.append(scc)

        return circular_sccs

    def get_maintainability_score(self) -> float:
        """Computes a composite architectural maintainability score from 0 to 100."""
        # 1. Circular dependency penalty
        sccs = self.find_strongly_connected_components()
        cycle_count = len(sccs)
        cycle_penalty = min(30.0, cycle_count * 5.0)

        # 2. Coupling penalty
        coupling = self.calculate_coupling()
        services = coupling["services"]
        internal_services = [s for s in services if s not in ("External", "Unknown")]
        
        if internal_services:
            avg_instability = sum(services[s]["instability"] for s in internal_services) / len(internal_services)
        else:
            avg_instability = 0.5
        coupling_penalty = avg_instability * 25.0

        # 3. Cohesion bonus/penalty
        cohesion = self.calculate_cohesion()
        internal_cohesion = [s for s in cohesion if s not in ("External", "Unknown")]
        if internal_cohesion:
            avg_cohesion_ratio = sum(cohesion[s]["internal_edge_ratio"] for s in internal_cohesion) / len(internal_cohesion)
        else:
            avg_cohesion_ratio = 1.0
        cohesion_penalty = (1.0 - avg_cohesion_ratio) * 25.0

        # 4. Complexity penalty
        complexities = [ndata["complexity"] for ndata in self.nodes.values() if ndata.get("complexity") is not None]
        if complexities:
            avg_complexity = sum(complexities) / len(complexities)
        else:
            avg_complexity = 1.0
        complexity_penalty = min(20.0, (avg_complexity / 15.0) * 20.0)

        score = 100.0 - cycle_penalty - coupling_penalty - cohesion_penalty - complexity_penalty
        return max(0.0, min(100.0, score))

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Assembles all architectural metrics into a unified summary."""
        coupling = self.calculate_coupling()
        cohesion = self.calculate_cohesion()
        sccs = self.find_strongly_connected_components()
        
        # Map node IDs in SCCs back to labels/names for readable reporting
        readable_sccs = []
        for scc in sccs:
            nodes_info = []
            for nid in scc:
                ndata = self.nodes.get(nid, {})
                nodes_info.append({
                    "id": nid,
                    "name": ndata.get("name", "unknown"),
                    "label": ndata.get("label", "Unknown"),
                    "path": ndata.get("path")
                })
            readable_sccs.append(nodes_info)

        return {
            "maintainability_score": round(self.get_maintainability_score(), 1),
            "nodes_count": len([n for n in self.nodes.values() if not n.get("is_external")]),
            "external_nodes_count": len([n for n in self.nodes.values() if n.get("is_external")]),
            "edges_count": len([e for e in self.edges if e["type"] != "CONTAINS"]),
            "circular_dependencies_count": len(sccs),
            "circular_dependency_groups": readable_sccs,
            "coupling": coupling,
            "cohesion": cohesion
        }

    def compare_scenarios(self, other: "CodeGraphTwin") -> Dict[str, Any]:
        """Compares this (baseline) twin against another (simulated) twin."""
        base_metrics = self.get_metrics_summary()
        sim_metrics = other.get_metrics_summary()
        
        return {
            "maintainability_score": {
                "baseline": base_metrics["maintainability_score"],
                "simulated": sim_metrics["maintainability_score"],
                "delta": round(sim_metrics["maintainability_score"] - base_metrics["maintainability_score"], 1)
            },
            "circular_dependencies": {
                "baseline": base_metrics["circular_dependencies_count"],
                "simulated": sim_metrics["circular_dependencies_count"],
                "delta": sim_metrics["circular_dependencies_count"] - base_metrics["circular_dependencies_count"]
            },
            "coupling_edges": {
                "baseline": base_metrics["coupling"]["total_inter_service_dependencies"],
                "simulated": sim_metrics["coupling"]["total_inter_service_dependencies"],
                "delta": sim_metrics["coupling"]["total_inter_service_dependencies"] - base_metrics["coupling"]["total_inter_service_dependencies"]
            },
            "nodes_count": {
                "baseline": base_metrics["nodes_count"],
                "simulated": sim_metrics["nodes_count"],
                "delta": sim_metrics["nodes_count"] - base_metrics["nodes_count"]
            },
            "edges_count": {
                "baseline": base_metrics["edges_count"],
                "simulated": sim_metrics["edges_count"],
                "delta": sim_metrics["edges_count"] - base_metrics["edges_count"]
            }
        }


class EvolutionTimeline:
    """Uses git history and graph database metrics to analyze codebase growth and hotspots."""

    @staticmethod
    def get_git_churn(repo_path: str, num_commits: int = 50) -> Dict[str, int]:
        """Measures file edit frequency in git history."""
        try:
            # run command to get list of files changed in last N commits
            cmd = ["git", "log", "--name-only", "--pretty=format:", f"-n {num_commits}"]
            res = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            churn: Dict[str, int] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if line:
                    # Normalize to relative posix path
                    posix_path = Path(line).as_posix()
                    churn[posix_path] = churn.get(posix_path, 0) + 1
            return churn
        except Exception as e:
            warning_logger(f"Failed to read git log churn: {e}")
            return {}

    @classmethod
    def analyze_hotspots(cls, db_manager, repo_path: str, num_commits: int = 50) -> List[Dict[str, Any]]:
        """Combines complexity from DB and churn from Git to rank Technical Debt Hotspots."""
        churn = cls.get_git_churn(repo_path, num_commits=num_commits)
        if not churn:
            return []

        # Query complexities of files and their functions from the database
        query = """
        MATCH (r:Repository {path: $path})-[:CONTAINS*]->(f:File)
        OPTIONAL MATCH (f)-[:CONTAINS*]->(func:Function)
        RETURN f.relative_path as rel_path, f.path as abs_path, sum(func.cyclomatic_complexity) as complexity
        """
        
        with db_manager.get_driver().session() as session:
            rows = session.run(query, path=Path(repo_path).resolve().as_posix()).data()

        max_complexity = 1.0
        max_churn = max(churn.values()) if churn else 1
        
        file_metrics = []
        for r in rows:
            rel_path = r.get("rel_path")
            if not rel_path:
                continue
                
            complexity = float(r.get("complexity") or 0)
            rel_path_posix = Path(rel_path).as_posix()
            file_churn = churn.get(rel_path_posix, 0)
            
            if complexity > max_complexity:
                max_complexity = complexity
                
            file_metrics.append({
                "relative_path": rel_path,
                "absolute_path": r.get("abs_path"),
                "complexity": complexity,
                "churn": file_churn
            })

        # Calculate scores
        for fm in file_metrics:
            churn_score = float(fm["churn"]) / max_churn
            comp_score = float(fm["complexity"]) / max_complexity
            # Hotspot score = churn_score * comp_score * 100
            fm["hotspot_score"] = round(churn_score * comp_score * 100, 1)

        # Sort descending by hotspot score
        file_metrics.sort(key=lambda x: x["hotspot_score"], reverse=True)
        return file_metrics

    @staticmethod
    def get_growth_trend(repo_path: str, num_commits: int = 20) -> List[Dict[str, Any]]:
        """Parses git log shortstat to show growth over commits."""
        try:
            cmd = ["git", "log", "--shortstat", f"-n {num_commits}", "--pretty=format:%h|%ad|%an|%s", "--date=short"]
            res = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            commits = []
            current_commit = None
            
            # Regex for shortstat: e.g., " 3 files changed, 24 insertions(+), 8 deletions(-)"
            stat_re = re.compile(r"(\d+)\s+files?\s+changed(?:,\s+(\d+)\s+insertions?\(\+\))?(?:,\s+(\d+)\s+deletions?\(-\))?")
            
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                    
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        current_commit = {
                            "hash": parts[0],
                            "date": parts[1],
                            "author": parts[2],
                            "subject": parts[3],
                            "files_changed": 0,
                            "insertions": 0,
                            "deletions": 0
                        }
                        commits.append(current_commit)
                elif current_commit and ("changed" in line):
                    match = stat_re.search(line)
                    if match:
                        current_commit["files_changed"] = int(match.group(1) or 0)
                        current_commit["insertions"] = int(match.group(2) or 0)
                        current_commit["deletions"] = int(match.group(3) or 0)
                        
            return commits
        except Exception as e:
            warning_logger(f"Failed to read git growth trend: {e}")
            return []
