"""
E2E test: index the TypeScript sample project into the DB, then query
to verify Module nodes have resolved absolute paths for alias/relative
imports, and bare specifiers stay as-is.
"""

import pytest
import shutil
import subprocess
import sys


def run_cgc(args, cwd=None):
    cmd = [sys.executable, "-m", "codegraphcontext.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def query(cypher):
    """Run a Cypher query and return stdout."""
    result = run_cgc(["query", cypher])
    assert result.returncode == 0, f"Query failed: {result.stderr}"
    return result.stdout


def query_value(cypher, key):
    """Run a Cypher query and return a single value from the first result row."""
    result = run_cgc(["query", cypher])
    assert result.returncode == 0, f"Query failed: {result.stderr}"
    import json
    # The CLI may print init messages before JSON; find the JSON array.
    stdout = result.stdout
    idx = stdout.find("[")
    assert idx != -1, f"No JSON array in output: {stdout}"
    rows = json.loads(stdout[idx:])
    assert len(rows) > 0, f"No results for query: {cypher}"
    return rows[0][key]


@pytest.mark.slow
class TestTypescriptIndexing:
    """Index the TS fixture and validate the graph via Cypher queries."""

    @pytest.fixture(scope="class", autouse=True)
    def indexed_project(self, typescript_sample_project, tmp_path_factory):
        """Copy fixture to temp dir, index it, yield, then clean up from graph."""
        project_dir = tmp_path_factory.mktemp("ts_project")
        shutil.copytree(typescript_sample_project, project_dir, dirs_exist_ok=True)

        result = run_cgc(["index", str(project_dir)])
        assert result.returncode == 0, f"Indexing failed: {result.stderr}"

        yield project_dir

        # Cleanup: delete just this repo from the graph
        subprocess.run(
            [sys.executable, "-m", "codegraphcontext.cli.main", "delete", str(project_dir)],
            input="y\n", capture_output=True, text=True,
        )

    def test_ts_files_indexed(self):
        count = query_value("MATCH (f:File) WHERE f.path ENDS WITH '.ts' RETURN count(f) as c", "c")
        assert count > 0

    def test_tsx_files_indexed(self):
        count = query_value("MATCH (f:File) WHERE f.path ENDS WITH '.tsx' RETURN count(f) as c", "c")
        assert count > 0

    def test_alias_imports_resolved_to_absolute_paths(self):
        """Module nodes for alias imports should have absolute paths, not raw specifiers."""
        out = query(
            "MATCH (m:Module) WHERE m.name CONTAINS 'string-helpers' RETURN m.name"
        )
        assert "/" in out
        assert "string-helpers.ts" in out

    def test_alias_module_has_raw_specifier(self):
        out = query(
            "MATCH (m:Module) WHERE m.name CONTAINS 'string-helpers.ts' "
            "RETURN m.raw_specifier"
        )
        assert "@utils/string-helpers" in out

    def test_relative_imports_resolved(self):
        out = query(
            "MATCH (m:Module) WHERE m.name CONTAINS 'types-interfaces' RETURN m.name"
        )
        assert "/" in out
        assert "types-interfaces.ts" in out

    def test_bare_specifiers_stay_raw(self):
        out = query("MATCH (m:Module) WHERE m.name = 'react' RETURN m.name")
        assert "react" in out

    def test_file_imports_module(self):
        out = query(
            "MATCH (f:File)-[:IMPORTS]->(m:Module) "
            "WHERE f.path CONTAINS 'app-service.ts' "
            "RETURN m.name"
        )
        assert "string-helpers.ts" in out
        assert "constants.ts" in out

    def test_tsx_file_imports_resolved(self):
        out = query(
            "MATCH (f:File)-[:IMPORTS]->(m:Module) "
            "WHERE f.path CONTAINS 'App.tsx' "
            "RETURN m.name"
        )
        assert "Layout.tsx" in out
        assert "Button.tsx" in out

    def test_jsx_component_calls_detected(self):
        out = query(
            "MATCH (f:Function)-[:CALLS]->(t) "
            "WHERE f.path CONTAINS 'App.tsx' "
            "RETURN t.name"
        )
        assert "Layout" in out or "Button" in out

    def test_no_duplicate_modules_for_same_file(self, indexed_project):
        """Two files importing @shared/constants should share one Module node."""
        root = str(indexed_project).replace("\\", "\\\\").replace("'", "\\'")
        count = query_value(
            "MATCH (f:File)-[:IMPORTS]->(m:Module) "
            f"WHERE f.path STARTS WITH '{root}' "
            "AND m.name CONTAINS 'constants.ts' "
            "RETURN count(DISTINCT m) as c",
            "c",
        )
        assert count == 1
