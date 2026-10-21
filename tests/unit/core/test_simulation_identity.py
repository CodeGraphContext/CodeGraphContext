import copy

import pytest

from codegraphcontext.core.simulator import CodeGraphTwin
from codegraphcontext.server import MCPServer


def twin():
    value = CodeGraphTwin("/repo")
    value.nodes = {
        "uid-1": {"name": "entry", "path": "/repo/app.py"},
        "uid-2": {"name": "helper", "path": "/repo/helpers.py"},
    }
    return value


@pytest.mark.parametrize("source,target", [("entry", "helper"), ("uid-1", "uid-2"), ("/repo/app.py", "/repo/helpers.py")])
def test_add_remove_dependency_resolve_supported_identities(source, target):
    value = twin()
    assert value.add_dependency(source, target, None) == 1
    assert value.edges == [{"source": "uid-1", "target": "uid-2", "type": "CALLS"}]
    assert value.add_dependency(source, target, "CALLS") == 0
    assert value.remove_dependency(source, target) == 1
    assert value.edges == []


def test_missing_and_ambiguous_names_are_explicit_errors():
    value = twin()
    before = copy.deepcopy(value.edges)
    with pytest.raises(ValueError, match="No node"):
        value.add_dependency("missing", "helper", "CALLS")
    value.nodes["uid-3"] = {"name": "helper", "path": "/repo/other.py"}
    with pytest.raises(ValueError, match="Ambiguous"):
        value.add_dependency("entry", "helper", "CALLS")
    assert value.edges == before


def test_remove_node_reports_match_and_drops_edges_and_service_mapping():
    value = twin()
    value.add_dependency("entry", "helper", "CALLS")
    value.service_mapping = {"uid-1": "Root", "uid-2": "Helpers"}
    assert value.remove_node("helper") == 1
    assert "uid-2" not in value.nodes and "uid-2" not in value.service_mapping
    assert value.edges == []
    with pytest.raises(ValueError, match="No node"): value.remove_node("missing")


@pytest.mark.parametrize("method", ["simulate_metrics_tool", "simulate_architectural_change_tool", "analyze_architectural_evolution_tool"])
def test_context_is_never_silently_ignored(method):
    value = MCPServer.__new__(MCPServer)
    result = getattr(value, method)(context="another-context")
    assert result["unsupported_argument"] == "context"
    assert "switch_context" in result["error"]
