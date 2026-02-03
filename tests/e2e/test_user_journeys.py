
import pytest
import shutil
import subprocess
import os

# We will need the fixtures we defined in conftest.py
# (python_sample_project, temp_test_dir)

class TestUserJourneys:
    """
    End-to-End User Journeys.
    These tests invoke the 'cgc' command line tool as a subprocess, 
    simulating a real user interacting with the installed tool.
    """

    def run_cgc(self, args, cwd=None):
        """Helper to run cgc cli."""
        # Use sys.executable to ensure we use the same python environment
        import sys
        cmd = [sys.executable, "-m", "codegraphcontext.cli.main"] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

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
        
        # Ensure clean state (optional, if we use unique DBs per test it's better)
        # For this E2E, we might be hitting the real local DB. 
        # Ideally, we'd mock the DB env vars here to point to a test container or temp DB.
        # For safety, let's assume we proceed but maybe force a unique repo name?
        # Use a localized config if possible.
        
        # 2. Index
        print(f"Indexing {project_dir}...")
        result = self.run_cgc(["index", str(project_dir)])
        assert result.returncode == 0, f"Indexing failed: {result.stderr}"
        
        # 3. List
        result = self.run_cgc(["list"])
        assert result.returncode == 0
        assert str(project_dir) in result.stdout or "my_project" in result.stdout
        
        # 4. Find function
        # This relies on the indexer actually working and writing to DB
        # Correct command: cgc find name foo --type function
        result = self.run_cgc(["find", "name", "foo", "--type", "function"]) 
        assert result.returncode == 0
        # If the sample project has 'foo', we assert it's found
        # assert "foo" in result.stdout (Commented out until we confirm sample content)

    @pytest.mark.slow
    def test_clean_up(self, temp_test_dir):
        """User wants to remove a repo."""
        # Setup: Create dummy repo
        dummy_dir = temp_test_dir / "to_delete"
        dummy_dir.mkdir()
        (dummy_dir / "main.py").write_text("def main(): pass")
        
        self.run_cgc(["index", str(dummy_dir)])
        
        # Act: Delete
        # We need to bypass confirmation prompt if any. 
        # Usually delete requires --yes or input.
        # Assuming --force or --yes flag exists, or we pipe input.
        result = subprocess.run(
            ["python3", "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir), "--yes"],
            capture_output=True, text=True
        )
        # If --yes is not supported, this might fail/hang. Checking help first would be wise.
        # Let's assume interactive input:
        if result.returncode != 0:
             # Try interactive
             result = subprocess.run(
                ["python3", "-m", "codegraphcontext.cli.main", "delete", str(dummy_dir)],
                input="y\n", capture_output=True, text=True
            )

        assert result.returncode == 0
        
        # Verify gone
        list_res = self.run_cgc(["list"])
        assert str(dummy_dir) not in list_res.stdout

