# src/codegraphcontext/cli/visualizer.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .cli_helpers import visualize_helper


def resolve_visual_flag(ctx: Any, visual: bool) -> bool:
    """True when local or global --visual / -V was requested."""
    if visual:
        return True
    obj = getattr(ctx, "obj", None) if ctx is not None else None
    return bool(isinstance(obj, dict) and obj.get("visual"))


def check_visual_flag(ctx: Any, visual: bool) -> bool:
    """Return whether visualization was requested (does not launch UI)."""
    return resolve_visual_flag(ctx, visual)


def _escape_cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _file_props(name: str, file: Optional[str]) -> str:
    fn = _escape_cypher_string(name)
    if file:
        path = _escape_cypher_string(str(Path(file).resolve()))
        return f"{{name: '{fn}', path: '{path}'}}"
    return f"{{name: '{fn}'}}"


def _launch_visualizer(
    cypher_query: str,
    *,
    repo_path: Optional[str] = None,
    context: Optional[str] = None,
) -> None:
    visualize_helper(
        repo_path=repo_path,
        port=8000,
        context=context,
        cypher_query=cypher_query,
    )


def visualize_search_results(
    _results: Any,
    name: str,
    search_type: str = "name",
    **_: Any,
) -> None:
    term = _escape_cypher_string(name)
    if search_type == "pattern":
        query = (
            f"MATCH (n) WHERE n.name CONTAINS '{term}' "
            f"RETURN n AS n, null AS rel, null AS m LIMIT 80"
        )
    elif search_type == "type":
        label = term.capitalize()
        query = (
            f"MATCH (n:{label}) "
            f"RETURN n AS n, null AS rel, null AS m LIMIT 80"
        )
    else:
        query = (
            f"MATCH (n) WHERE n.name = '{term}' "
            f"RETURN n AS n, null AS rel, null AS m LIMIT 80"
        )
    _launch_visualizer(query)


def visualize_call_graph(
    _results: Any,
    function: str,
    direction: str = "outgoing",
    file: Optional[str] = None,
    **_: Any,
) -> None:
    props = _file_props(function, file)
    if direction == "incoming":
        query = (
            f"MATCH (caller)-[rel:CALLS]->(target:Function {props}) "
            f"RETURN caller AS n, rel AS rel, target AS m LIMIT 120"
        )
    else:
        query = (
            f"MATCH (caller:Function {props})-[rel:CALLS]->(called) "
            f"RETURN caller AS n, rel AS rel, called AS m LIMIT 120"
        )
    _launch_visualizer(query)


def visualize_call_chain(
    _results: Any,
    from_func: str,
    to_func: str,
    max_depth: int = 5,
    from_file: Optional[str] = None,
    to_file: Optional[str] = None,
    **_: Any,
) -> None:
    start = _file_props(from_func, from_file)
    end = _file_props(to_func, to_file)
    depth = max(1, min(int(max_depth), 15))
    query = (
        f"MATCH (start:Function {start}), (end:Function {end}) "
        f"MATCH p = (start)-[:CALLS*1..{depth}]->(end) "
        f"WITH nodes(p) AS ns, relationships(p) AS rs "
        f"UNWIND range(0, size(rs) - 1) AS i "
        f"RETURN ns[i] AS n, rs[i] AS rel, ns[i + 1] AS m "
        f"LIMIT 200"
    )
    _launch_visualizer(query)


def visualize_dependencies(
    _results: Any,
    target: str,
    **_: Any,
) -> None:
    term = _escape_cypher_string(target)
    query = (
        f"MATCH (f:File)-[rel:IMPORTS]->(m:Module) "
        f"WHERE m.name CONTAINS '{term}' OR m.full_import_name CONTAINS '{term}' "
        f"RETURN f AS n, rel AS rel, m AS m LIMIT 120"
    )
    _launch_visualizer(query)


def visualize_inheritance_tree(
    _results: Any,
    class_name: str,
    file: Optional[str] = None,
    **_: Any,
) -> None:
    props = _file_props(class_name, file)
    query = (
        f"MATCH (c:Class {props})-[rel:INHERITS]->(parent:Class) "
        f"RETURN c AS n, rel AS rel, parent AS m "
        f"UNION "
        f"MATCH (child:Class)-[rel:INHERITS]->(c:Class {props}) "
        f"RETURN child AS n, rel AS rel, c AS m "
        f"LIMIT 120"
    )
    _launch_visualizer(query)


def visualize_overrides(
    _results: Any,
    function_name: str,
    **_: Any,
) -> None:
    fn = _escape_cypher_string(function_name)
    query = (
        f"MATCH (class:Class)-[rel:CONTAINS]->(func:Function {{name: '{fn}'}}) "
        f"RETURN class AS n, rel AS rel, func AS m LIMIT 120"
    )
    _launch_visualizer(query)


def visualize_cypher_results(cypher_query: str, **_: Any) -> None:
    _launch_visualizer(cypher_query)
