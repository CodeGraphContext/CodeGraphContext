"""CGCBundle binds every session to the graph_name it was constructed with."""

from unittest.mock import MagicMock

from codegraphcontext.core.cgc_bundle import CGCBundle


def test_cgc_bundle_stores_graph_name_on_construction():
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "neo4j"
    bundle = CGCBundle(db_manager, graph_name="tenant_a")
    assert bundle.graph_name == "tenant_a"


def test_cgc_bundle_default_graph_name_is_none():
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "neo4j"
    bundle = CGCBundle(db_manager)
    assert bundle.graph_name is None


def test_cgc_bundle_every_get_driver_call_uses_self_graph_name():
    """Structural guarantee: every ``get_driver`` call in cgc_bundle.py must pass
    ``graph_name=self.graph_name`` so bundle work is pinned to the constructor's
    target graph, even as the file grows new query methods.
    """
    import ast
    import inspect

    from codegraphcontext.core import cgc_bundle

    source = inspect.getsource(cgc_bundle)
    tree = ast.parse(source)

    bad_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match self.db_manager.get_driver(...)
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "get_driver"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "db_manager"
        ):
            continue
        # Require graph_name=self.graph_name as a kwarg.
        has_correct = any(
            kw.arg == "graph_name"
            and isinstance(kw.value, ast.Attribute)
            and kw.value.attr == "graph_name"
            and isinstance(kw.value.value, ast.Name)
            and kw.value.value.id == "self"
            for kw in node.keywords
        )
        if not has_correct:
            bad_calls.append(f"line {node.lineno}")

    assert not bad_calls, (
        "Every self.db_manager.get_driver(...) in cgc_bundle.py must pass "
        f"graph_name=self.graph_name. Offenders: {bad_calls}"
    )
