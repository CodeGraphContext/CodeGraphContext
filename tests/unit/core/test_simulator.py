# tests/unit/core/test_simulator.py
import shutil
import subprocess

import pytest
from pathlib import Path
from codegraphcontext.core import simulator
from codegraphcontext.core.simulator import CodeGraphTwin, EvolutionTimeline, resolve_node_id


def test_resolve_node_id():
    assert resolve_node_id({"uid": "uid1", "path": "path1", "name": "name1"}) == "uid1"
    assert resolve_node_id({"path": "path1", "name": "name1"}) == "path1"
    assert resolve_node_id({"name": "name1"}) == "name1"
    assert resolve_node_id({}) == "unknown"


def test_simulator_twin_initialization():
    repo_dir = Path("/mock/repo").resolve().as_posix()
    twin = CodeGraphTwin(repo_dir)
    assert twin.repository_path == repo_dir
    assert twin.repo_name == "repo"
    assert len(twin.nodes) == 0
    assert len(twin.edges) == 0


def test_simulator_mutations():
    repo_dir = Path("/mock/repo").resolve().as_posix()
    twin = CodeGraphTwin(repo_dir)
    
    # Manually populate some nodes
    twin.nodes = {
        "n1": {"id": "n1", "name": "Func1", "path": f"{repo_dir}/src/auth/login.py", "complexity": 5},
        "n2": {"id": "n2", "name": "Func2", "path": f"{repo_dir}/src/auth/logout.py", "complexity": 3},
        "n3": {"id": "n3", "name": "Func3", "path": f"{repo_dir}/src/db/conn.py", "complexity": 2},
    }
    twin.edges = [
        {"source": "n1", "target": "n3", "type": "CALLS"},
        {"source": "n2", "target": "n3", "type": "CALLS"},
        {"source": "n1", "target": "n2", "type": "CALLS"},
    ]
    
    # 1. Test auto partition services
    twin.auto_partition_services()
    assert twin.service_mapping["n1"] == "src"
    
    # Let's adjust node paths to get better service boundaries
    twin.nodes["n1"]["path"] = f"{repo_dir}/auth/login.py"
    twin.nodes["n2"]["path"] = f"{repo_dir}/auth/logout.py"
    twin.nodes["n3"]["path"] = f"{repo_dir}/db/conn.py"
    twin.auto_partition_services()
    assert twin.service_mapping["n1"] == "auth"
    assert twin.service_mapping["n2"] == "auth"
    assert twin.service_mapping["n3"] == "db"

    # 2. Test decompose service
    twin.decompose_service({"auth": "AuthenticationService"})
    assert twin.service_mapping["n1"] == "AuthenticationService"
    assert twin.service_mapping["n2"] == "AuthenticationService"
    assert twin.service_mapping["n3"] == "db"

    # 3. Test add dependency
    twin.add_dependency("n3", "n1", "CALLS")
    assert len(twin.edges) == 4
    assert twin.edges[-1] == {"source": "n3", "target": "n1", "type": "CALLS"}

    # 4. Test remove dependency
    twin.remove_dependency("n3", "n1", "CALLS")
    assert len(twin.edges) == 3

    # 5. Test remove node
    twin.remove_node("n2")
    assert "n2" not in twin.nodes
    assert len(twin.edges) == 1  # only {"source": "n1", "target": "n3"} should remain
    assert twin.edges[0] == {"source": "n1", "target": "n3", "type": "CALLS"}


def test_metrics_calculation():
    repo_dir = Path("/mock/repo").resolve().as_posix()
    twin = CodeGraphTwin(repo_dir)
    twin.nodes = {
        "n1": {"id": "n1", "name": "Func1", "path": f"{repo_dir}/auth/login.py", "complexity": 10},
        "n2": {"id": "n2", "name": "Func2", "path": f"{repo_dir}/auth/logout.py", "complexity": 2},
        "n3": {"id": "n3", "name": "Func3", "path": f"{repo_dir}/db/conn.py", "complexity": 4},
        "n4": {"id": "n4", "name": "Func4", "path": f"{repo_dir}/ui/panel.py", "complexity": 1},
    }
    twin.edges = [
        {"source": "n1", "target": "n3", "type": "CALLS"},  # auth -> db
        {"source": "n2", "target": "n3", "type": "CALLS"},  # auth -> db
        {"source": "n4", "target": "n1", "type": "CALLS"},  # ui -> auth
        {"source": "n1", "target": "n2", "type": "CALLS"},  # auth -> auth (internal)
    ]
    twin.auto_partition_services()
    
    # Coupling
    coupling = twin.calculate_coupling()
    services_coupling = coupling["services"]
    
    # auth has outgoing external to db (n3)
    # auth has incoming external from ui (n4)
    assert services_coupling["auth"]["ca"] == 1  # from ui
    assert services_coupling["auth"]["ce"] == 1  # to db
    assert services_coupling["auth"]["instability"] == 0.5

    # Cohesion
    cohesion = twin.calculate_cohesion()
    # auth has 2 nodes (n1, n2), 1 internal edge (n1->n2), 2 external outgoing (n1->n3, n2->n3)
    assert cohesion["auth"]["nodes_count"] == 2
    assert cohesion["auth"]["internal_edges"] == 1
    assert cohesion["auth"]["cohesion_density"] == 0.5  # 1 / (2 * 1)
    assert abs(cohesion["auth"]["internal_edge_ratio"] - 0.333) < 0.01

    # SCCs (circular dependencies)
    # Right now, there are no cycles
    assert len(twin.find_strongly_connected_components()) == 0

    # Add cycle: db -> ui -> auth -> db
    twin.add_dependency("n3", "n4", "CALLS")
    sccs = twin.find_strongly_connected_components()
    assert len(sccs) == 1
    assert set(sccs[0]) == {"n1", "n2", "n3", "n4"}

    # Maintainability
    score = twin.get_maintainability_score()
    assert 0.0 <= score <= 100.0


def test_compare_scenarios():
    baseline = CodeGraphTwin("/mock/repo")
    baseline.nodes = {
        "n1": {"id": "n1", "name": "Func1", "path": "/mock/repo/auth/login.py", "complexity": 10},
        "n2": {"id": "n2", "name": "Func2", "path": "/mock/repo/db/conn.py", "complexity": 4},
    }
    baseline.edges = [
        {"source": "n1", "target": "n2", "type": "CALLS"},
        {"source": "n2", "target": "n1", "type": "CALLS"},  # cycle
    ]
    baseline.auto_partition_services()

    simulated = CodeGraphTwin("/mock/repo")
    simulated.nodes = baseline.nodes.copy()
    simulated.edges = baseline.edges.copy()
    simulated.auto_partition_services()
    
    # Simulate breaking the cycle
    simulated.remove_dependency("n2", "n1")

    diff = baseline.compare_scenarios(simulated)
    assert diff["circular_dependencies"]["baseline"] == 1
    assert diff["circular_dependencies"]["simulated"] == 0
    assert diff["circular_dependencies"]["delta"] == -1
    assert diff["maintainability_score"]["simulated"] > diff["maintainability_score"]["baseline"]


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_growth_trend_reads_non_ascii_commits(tmp_path):
    """git prints UTF-8; decoding it with a cp950 or cp1252 locale lost every commit."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Zoë Ångström")
    _git(tmp_path, "config", "user.email", "zoe@example.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "修正登入流程 café")

    growth = EvolutionTimeline.get_growth_trend(str(tmp_path), num_commits=5)

    assert [(c["author"], c["subject"]) for c in growth] == [("Zoë Ångström", "修正登入流程 café")]
    assert EvolutionTimeline.get_git_churn(str(tmp_path), num_commits=5) == {"a.txt": 1}


def test_git_output_is_decoded_as_utf8(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(simulator.subprocess, "run", fake_run)
    EvolutionTimeline.get_growth_trend("/repo")
    EvolutionTimeline.get_git_churn("/repo")

    assert len(calls) == 2
    assert all(kwargs.get("encoding") == "utf-8" for kwargs in calls)
