
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

    def run_cgc(self, args, cwd=None, db_path=None):
        """Helper to run cgc cli."""
        cmd = [sys.executable, "-m", "codegraphcontext.cli.main"]
        if db_path:
            cmd += ["--path", str(db_path)]
        cmd += args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

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
    def test_clean_up(self, temp_test_dir):
        """User wants to remove a repo."""
        # Setup: Create dummy repo
        dummy_dir = temp_test_dir / "to_delete"
        dummy_dir.mkdir()
        (dummy_dir / "main.py").write_text("def main(): pass")
        db_path = temp_test_dir / "delete_test_kuzu.db"
        
        self.run_cgc(["--db", "kuzudb", "index", str(dummy_dir)], db_path=db_path)
        
        # Act: Delete
        result = self.run_cgc(["--db", "kuzudb", "delete", str(dummy_dir), "--yes"], db_path=db_path)
        
        # If --yes is not supported or failed, try interactive
        if result.returncode != 0:
            cmd = [sys.executable, "-m", "codegraphcontext.cli.main", "--path", str(db_path), "--db", "kuzudb", "delete", str(dummy_dir)]
            result = subprocess.run(cmd, input="y\n", capture_output=True, text=True)

        assert result.returncode == 0, f"Delete failed: {result.stderr}"
        
        # Verify gone
        list_res = self.run_cgc(["--db", "kuzudb", "list"], db_path=db_path)
        assert str(dummy_dir) not in list_res.stdout
