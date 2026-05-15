# src/codegraphcontext/tools/report_generator.py
"""CGC Report Generator (#884).

Generates a CGC_REPORT.md summarising:
- God nodes (highest in-degree functions/classes)
- Most complex functions
- Cross-module surprising connections
- Spring endpoint and bean summary (--java flag)
- Suggested Cypher queries

Usage::

    from codegraphcontext.tools.report_generator import generate_report
    markdown = generate_report(db_manager, output_path=Path("CGC_REPORT.md"))
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.debug_log import info_logger


def _run_cypher(driver: Any, query: str, params: Optional[Dict] = None) -> List[Dict]:
    """Execute a read-only Cypher query and return a list of record dicts."""
    try:
        with driver.session() as session:
            result = session.run(query, **(params or {}))
            return [dict(record) for record in result]
    except Exception as exc:
        return [{"_error": str(exc)}]


def _h2(title: str) -> str:
    return f"\n## {title}\n"


def _h3(title: str) -> str:
    return f"\n### {title}\n"


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    """Render a simple markdown table."""
    sep = " | ".join("---" for _ in headers)
    head = " | ".join(headers)
    body = "\n".join(" | ".join(str(c) for c in row) for row in rows)
    return f"| {head} |\n| {sep} |\n" + "\n".join(f"| {' | '.join(str(c) for c in r)} |" for r in rows)


def _code_block(cypher: str) -> str:
    return f"```cypher\n{textwrap.dedent(cypher).strip()}\n```"


# ── Individual report sections ────────────────────────────────────────────────

def _section_god_nodes(driver: Any, limit: int = 15) -> str:
    """Functions / classes with the highest number of incoming CALLS edges."""
    rows = _run_cypher(
        driver,
        """
        MATCH ()-[:CALLS]->(target)
        WITH target, count(*) AS in_degree
        WHERE in_degree > 1
        RETURN labels(target)[0] AS kind, target.name AS name,
               target.path AS path, in_degree
        ORDER BY in_degree DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )
    if not rows or "_error" in rows[0]:
        return ""

    out = _h2("God Nodes — Highest Fan-In")
    out += (
        "_These nodes are called from many places. High fan-in increases risk: "
        "a change here affects every caller._\n\n"
    )
    table_rows = []
    for r in rows:
        path = str(r.get("path") or "")
        short_path = path.split("/")[-2] + "/" + path.split("/")[-1] if "/" in path else path
        table_rows.append([r.get("kind", "?"), r.get("name", "?"), short_path, r.get("in_degree", 0)])
    out += _table(["Kind", "Name", "File", "In-degree"], table_rows)
    out += "\n"
    return out


def _section_complexity(driver: Any, limit: int = 15) -> str:
    """Most complex functions by cyclomatic complexity."""
    rows = _run_cypher(
        driver,
        """
        MATCH (fn:Function)
        WHERE fn.cyclomatic_complexity IS NOT NULL AND fn.cyclomatic_complexity > 1
        RETURN fn.name AS name, fn.path AS path,
               fn.cyclomatic_complexity AS complexity
        ORDER BY complexity DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )
    if not rows or "_error" in rows[0]:
        return ""

    out = _h2("Most Complex Functions")
    out += "_Cyclomatic complexity > 10 is a refactoring candidate._\n\n"
    table_rows = []
    for r in rows:
        path = str(r.get("path") or "")
        short_path = "/".join(path.split("/")[-2:]) if "/" in path else path
        table_rows.append([r.get("name", "?"), short_path, r.get("complexity", "?")])
    out += _table(["Function", "File", "Cyclomatic Complexity"], table_rows)
    out += "\n"
    return out


def _section_cross_module_calls(driver: Any, limit: int = 20) -> str:
    """Cross-directory (cross-module) CALLS edges — potential surprising connections."""
    rows = _run_cypher(
        driver,
        """
        MATCH (caller)-[c:CALLS]->(callee)
        WHERE caller.path IS NOT NULL AND callee.path IS NOT NULL
          AND caller.path <> callee.path
        WITH caller, callee, c,
             [p IN split(caller.path, '/') WHERE p <> '' | p][-3] AS caller_pkg,
             [p IN split(callee.path, '/') WHERE p <> '' | p][-3] AS callee_pkg
        WHERE caller_pkg IS NOT NULL AND callee_pkg IS NOT NULL
          AND caller_pkg <> callee_pkg
        RETURN caller.name AS caller_name, caller.path AS caller_path,
               callee.name AS callee_name, callee.path AS callee_path,
               c.confidence_label AS label
        LIMIT $limit
        """,
        {"limit": limit},
    )
    if not rows or "_error" in rows[0]:
        return ""

    out = _h2("Cross-Module Connections")
    out += "_Calls that cross package boundaries — review for unexpected coupling._\n\n"
    table_rows = []
    for r in rows:
        cp = str(r.get("caller_path") or "")
        dp = str(r.get("callee_path") or "")
        short_cp = "/".join(cp.split("/")[-2:]) if "/" in cp else cp
        short_dp = "/".join(dp.split("/")[-2:]) if "/" in dp else dp
        table_rows.append([
            r.get("caller_name", "?"),
            short_cp,
            r.get("callee_name", "?"),
            short_dp,
            r.get("label") or "—",
        ])
    out += _table(["Caller", "Caller File", "Callee", "Callee File", "Confidence"], table_rows)
    out += "\n"
    return out


def _section_dead_code(driver: Any, limit: int = 20) -> str:
    """Functions with no incoming CALLS edges (potential dead code)."""
    rows = _run_cypher(
        driver,
        """
        MATCH (fn:Function)
        WHERE fn.is_dependency IS NULL OR fn.is_dependency = false
        AND NOT ()-[:CALLS]->(fn)
        RETURN fn.name AS name, fn.path AS path
        ORDER BY fn.path, fn.name
        LIMIT $limit
        """,
        {"limit": limit},
    )
    if not rows or "_error" in rows[0]:
        return ""

    out = _h2("Potential Dead Code")
    out += "_Functions with zero callers (not guaranteed dead — may be entry points or called via reflection)._\n\n"
    table_rows = []
    for r in rows:
        path = str(r.get("path") or "")
        short_path = "/".join(path.split("/")[-2:]) if "/" in path else path
        table_rows.append([r.get("name", "?"), short_path])
    out += _table(["Function", "File"], table_rows)
    out += "\n"
    return out


def _section_spring_endpoints(driver: Any) -> str:
    """Spring HTTP endpoints — table of method, path, handler function."""
    rows = _run_cypher(
        driver,
        """
        MATCH (fn:Function)
        WHERE fn.http_method IS NOT NULL
        RETURN fn.http_method AS method, fn.http_path AS path,
               fn.name AS handler, fn.path AS file
        ORDER BY fn.http_path, fn.http_method
        """,
    )
    if not rows or "_error" in rows[0] or not rows:
        return ""

    out = _h2("Spring HTTP Endpoints")
    table_rows = []
    for r in rows:
        file_path = str(r.get("file") or "")
        short_fp = "/".join(file_path.split("/")[-2:]) if "/" in file_path else file_path
        table_rows.append([
            r.get("method", "?"),
            r.get("path") or "—",
            r.get("handler", "?"),
            short_fp,
        ])
    out += _table(["HTTP Method", "Path", "Handler", "File"], table_rows)
    out += "\n"
    return out


def _section_spring_beans(driver: Any) -> str:
    """Spring bean stereotype summary."""
    rows = _run_cypher(
        driver,
        """
        MATCH (c:Class)
        WHERE c.spring_stereotype IS NOT NULL
        RETURN c.spring_stereotype AS stereotype, count(*) AS count
        ORDER BY count DESC
        """,
    )
    if not rows or "_error" in rows[0] or not rows:
        return ""

    out = _h2("Spring Bean Stereotypes")
    table_rows = [[r.get("stereotype", "?"), r.get("count", 0)] for r in rows]
    out += _table(["Stereotype", "Count"], table_rows)
    out += "\n"
    return out


def _section_maven_modules(driver: Any) -> str:
    """Maven module dependency summary."""
    rows = _run_cypher(
        driver,
        """
        MATCH (m:MavenModule)
        OPTIONAL MATCH (m)-[:MODULE_DEPENDS_ON]->(dep:MavenModule)
        RETURN m.artifact_id AS module, m.version AS version,
               collect(dep.artifact_id) AS internal_deps
        ORDER BY m.artifact_id
        LIMIT 30
        """,
    )
    if not rows or "_error" in rows[0] or not rows:
        return ""

    out = _h2("Maven Module Graph")
    table_rows = []
    for r in rows:
        deps = r.get("internal_deps") or []
        table_rows.append([r.get("module", "?"), r.get("version", "?"), len(deps)])
    out += _table(["Module", "Version", "Internal Deps"], table_rows)
    out += "\n"
    return out


def _section_suggested_queries() -> str:
    out = _h2("Suggested Cypher Queries")
    out += "_Copy these into `execute_cypher_query` to explore further._\n"

    queries = [
        (
            "Callers of a specific function",
            """
            MATCH (caller)-[:CALLS]->(fn:Function {name: 'yourFunctionName'})
            RETURN caller.name, caller.path LIMIT 20
            """,
        ),
        (
            "Class hierarchy for a specific class",
            """
            MATCH path = (c:Class {name: 'YourClass'})-[:INHERITS*]->(parent)
            RETURN [n IN nodes(path) | n.name] AS hierarchy
            """,
        ),
        (
            "Most-injected Spring beans",
            """
            MATCH ()-[:INJECTS]->(bean:Class)
            RETURN bean.name, count(*) AS injection_count
            ORDER BY injection_count DESC LIMIT 10
            """,
        ),
        (
            "All external library dependencies",
            """
            MATCH (m:MavenModule)-[:USES_LIBRARY]->(lib:ExternalLibrary)
            RETURN m.artifact_id, lib.group_id, lib.artifact_id, lib.version
            ORDER BY lib.artifact_id
            """,
        ),
        (
            "CALLS edges with low confidence (potential mis-resolutions)",
            """
            MATCH (a)-[c:CALLS]->(b)
            WHERE c.confidence_label = 'AMBIGUOUS'
            RETURN a.name, b.name, c.resolution_tier, a.path LIMIT 20
            """,
        ),
    ]

    for title, query in queries:
        out += _h3(title)
        out += _code_block(query) + "\n"
    return out


# ── Public entry point ───────────────────────────────────────────────────────

def generate_report(
    db_manager: Any,
    output_path: Optional[Path] = None,
    include_java: bool = False,
    god_node_limit: int = 15,
    complexity_limit: int = 15,
    cross_module_limit: int = 20,
) -> str:
    """Generate a CGC_REPORT.md and return the markdown string.

    Args:
        db_manager:      DatabaseManager instance.
        output_path:     If provided, write the report to this path.
        include_java:    Include Spring/Maven sections (--java flag).
        god_node_limit:  Max rows for god-nodes section.
        complexity_limit: Max rows for complexity section.
        cross_module_limit: Max rows for cross-module section.

    Returns:
        The full report as a markdown string.
    """
    driver = db_manager.get_driver()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    sections = []
    sections.append(f"# CGC Report\n\n_Generated: {now}_\n")
    sections.append(_section_god_nodes(driver, god_node_limit))
    sections.append(_section_complexity(driver, complexity_limit))
    sections.append(_section_cross_module_calls(driver, cross_module_limit))
    sections.append(_section_dead_code(driver))

    if include_java:
        sections.append(_section_spring_endpoints(driver))
        sections.append(_section_spring_beans(driver))
        sections.append(_section_maven_modules(driver))

    sections.append(_section_suggested_queries())

    report = "\n".join(s for s in sections if s)

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(report, encoding="utf-8")
        info_logger(f"[REPORT] Written to {output_path}")

    return report
