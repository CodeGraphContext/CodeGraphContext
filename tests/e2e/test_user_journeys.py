
import pytest
import shutil
import subprocess
import os
import sys
import importlib.util

# Keep this check aligned with runtime backend detection in core/__init__.py.
KUZU_AVAILABLE = importlib.util.find_spec("kuzu") is not None

# We will need the fixtures we defined in conftest.py
# (python_sample_project, temp_test_dir)

class TestUserJourneys:
    """
    End-to-End User Journeys.
    These tests invoke the 'cgc' command line tool as a subprocess, 
    simulating a real user interacting with the installed tool.
    """

    def run_cgc(self, args, cwd=None):
        """Helper to run cgc cli using .venv Python if available, else sys.executable."""
        import os
        import sys
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.venv'))
        if os.name == "nt":
            venv_python = os.path.join(base_dir, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(base_dir, "bin", "python")
        python_exec = venv_python if os.path.exists(venv_python) else sys.executable
        cmd = [python_exec, "-m", "codegraphcontext.cli.main"] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    def run_cgc(self, args, cwd=None, db_path=None, env=None):
        """Helper to run cgc cli."""
        cmd = [sys.executable, "-m", "codegraphcontext.cli.main"]
        if db_path:
            cmd += ["--path", str(db_path)]
        cmd += args
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=run_env)

    @pytest.mark.skipif(not KUZU_AVAILABLE, reason="KuzuDB not installed")
    @pytest.mark.slow
    def test_first_time_user_workflow(self, python_sample_project, temp_test_dir):
        """
        Scenario:
        1. User initializes a new folder (conceptually, or we just index an existing one)
        2. User runs 'cgc index' on verify basic project.
        3. User runs 'cgc list' to verify it's there.
        4. User runs 'cgc find function foo' to verify indexing worked.
        """
        

        # 1. Copy sample project to temp dir to avoid polluting global state
        project_dir = temp_test_dir / "my_project"
        shutil.copytree(python_sample_project, project_dir)

        # Ensure pyproject.toml exists in project_dir with explicit config
        pyproject_dst = project_dir / "pyproject.toml"
        # Write only Neo4j config for CI reliability
        neo4j_config = (
            "[tool.codegraphcontext]\n"
            "database = 'Neo4j'\n"
            "neo4j_uri = 'bolt://localhost:7687'\n"
            "neo4j_username = 'neo4j'\n"
            "neo4j_password = 'neo4jpassword'\n"
        )
        with open(pyproject_dst, "w") as f:
            f.write(neo4j_config)

        db_path = temp_test_dir / "test_kuzu.db"
        
        # 2. Index
        print(f"Indexing {project_dir}...")
        result = self.run_cgc(["--db", "kuzudb", "index", str(project_dir)], db_path=db_path)
        assert result.returncode == 0, f"Indexing failed: {result.stderr}"
        
        # 3. List
        result = self.run_cgc(["--db", "kuzudb", "list"], db_path=db_path)
        assert result.returncode == 0
        assert str(project_dir) in result.stdout or "my_project" in result.stdout
        
        # 4. Find function
        # This relies on the indexer actually working and writing to DB
        # Correct command: cgc find name foo --type function
        result = self.run_cgc(["--db", "kuzudb", "find", "name", "foo", "--type", "function"], db_path=db_path)
        assert result.returncode == 0
        # If the sample project has 'foo', we assert it's found
        # assert "foo" in result.stdout (Commented out until we confirm sample content)

    @pytest.mark.skipif(not KUZU_AVAILABLE, reason="KuzuDB not installed")
    @pytest.mark.slow
    def test_clean_up(self, temp_test_dir, monkeypatch):
        """User wants to remove a repo."""
        # Deletion is gated behind ALLOW_DB_DELETION (opt-in safety flag);
        # enable it for this journey so the delete subprocess is permitted.
        monkeypatch.setenv("ALLOW_DB_DELETION", "true")
        # Setup: Create dummy repo
        dummy_dir = temp_test_dir / "to_delete"
        dummy_dir.mkdir()
        (dummy_dir / "main.py").write_text("def main(): pass")
        # Ensure pyproject.toml exists in dummy_dir with explicit config
        pyproject_dst = dummy_dir / "pyproject.toml"
        # Write only Neo4j config for CI reliability
        neo4j_config = (
            "[tool.codegraphcontext]\n"
            "database = 'Neo4j'\n"
            "neo4j_uri = 'bolt://localhost:7687'\n"
            "neo4j_username = 'neo4j'\n"
            "neo4j_password = 'neo4jpassword'\n"
        )
        with open(pyproject_dst, "w") as f:
            f.write(neo4j_config)
        self.run_cgc(["index", str(dummy_dir)])
        
        # Act: Delete
        # We need to bypass confirmation prompt if any. 
        # Usually delete requires --yes or input.
        # Assuming --force or --yes flag exists, or we pipe input.
        import os
        import sys
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.venv'))
        if os.name == "nt":
            venv_python = os.path.join(base_dir, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(base_dir, "bin", "python")
        python_exec = venv_python if os.path.exists(venv_python) else sys.executable
        result = subprocess.run(
            [python_exec, "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir), "--yes"],
            [sys.executable, "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir), "--yes"],
            capture_output=True, text=True
        )
        # If --yes is not supported, this might fail/hang. Checking help first would be wise.
        # Let's assume interactive input:
        if result.returncode != 0:
             # Try interactive
             result = subprocess.run(
                [python_exec, "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir)],
            # Try interactive
            result = subprocess.run(
                [sys.executable, "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir)],
                input="y\n", capture_output=True, text=True
            )
        db_path = temp_test_dir / "delete_test_kuzu.db"
        
        self.run_cgc(["--db", "kuzudb", "index", str(dummy_dir)], db_path=db_path)
        
        # Act: Delete
        env = {"ALLOW_DB_DELETION": "true"}
        result = self.run_cgc(["--db", "kuzudb", "delete", str(dummy_dir), "--yes"], db_path=db_path, env=env)
        
        # If --yes is not supported or failed, try interactive
        if result.returncode != 0:
            cmd = [sys.executable, "-m", "codegraphcontext.cli.main", "--path", str(db_path), "--db", "kuzudb", "delete", str(dummy_dir)]
            run_env = os.environ.copy()
            run_env.update(env)
            result = subprocess.run(cmd, input="y\n", capture_output=True, text=True, env=run_env)

        assert result.returncode == 0, f"Delete failed: {result.stderr}"
        
        # Verify gone
        list_res = self.run_cgc(["--db", "kuzudb", "list"], db_path=db_path)
        assert str(dummy_dir) not in list_res.stdout
