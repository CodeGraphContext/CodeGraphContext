import subprocess
import shutil
import os
import json
import shlex
import sys
import pytest
import uuid
import time
import socket
import re
from pathlib import Path
from pathspec import PathSpec

# ✅ CORRECT IMPORT PATH
from codegraphcontext.tools.graph_builder import DEFAULT_IGNORE_PATTERNS
from codegraphcontext.core.cgcignore import build_ignore_spec

# Per-test isolation (#1422): BASE_TEST_DIR and TEST_HOME are rebound to a
# fresh pytest tmp dir for every test by the autouse fixture below. The old
# fixed /tmp/cgc_test/_home was shared by every test in every run — one
# accumulating database, wiped mid-suite by whichever test got there first,
# which made TC-12+ fail intermittently with a different name each full-suite
# run while passing in isolation.
BASE_TEST_DIR = Path("/tmp/cgc_test")  # rebound per test by _isolated_cgc_home
TEST_HOME = BASE_TEST_DIR / "_home"    # rebound per test by _isolated_cgc_home
CGC_CMD = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


@pytest.fixture(autouse=True)
def _isolated_cgc_home(tmp_path):
    global BASE_TEST_DIR, TEST_HOME
    old_base, old_home = BASE_TEST_DIR, TEST_HOME
    BASE_TEST_DIR = tmp_path
    TEST_HOME = tmp_path / "_home"
    TEST_HOME.mkdir(parents=True, exist_ok=True)
    yield
    BASE_TEST_DIR, TEST_HOME = old_base, old_home


def _test_env():
    """Run shell-based CGC tests against the current interpreter in an isolated HOME."""
    TEST_HOME.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(TEST_HOME)
    # Embedded backend: hermetic, no server, available everywhere. The old
    # DEFAULT_DATABASE=falkordb silently fell back anyway (#1387), and the
    # Neo4j-reachability gate left these tests permanently skipped on
    # machines without a local bolt endpoint.
    env["DEFAULT_DATABASE"] = "ladybugdb"
    env["CGC_CONTEXT_MODE"] = "global"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Ensure all current sys.path entries are in PYTHONPATH so dependencies and -m work
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return env

def get_unique_test_dir():
    """Generate unique test directory"""
    unique_id = str(uuid.uuid4())[:8]
    return BASE_TEST_DIR / f"test_{unique_id}"

def run(cmd):
    """Run command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=_test_env())
    return result.stdout + result.stderr


def _is_neo4j_reachable(host: str = "localhost", port: int = 7687, timeout: float = 1.0) -> bool:
    """Return True when a local Neo4j bolt endpoint is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def setup_test_dir(test_dir: Path):
    """Create clean test directory"""
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    return test_dir

def clean_db_completely():
    """Completely clean the database"""
    # Delete ALL nodes
    run(f'{CGC_CMD} query "MATCH (n) DETACH DELETE n"')
    time.sleep(1)  # Wait for DB to sync

def delete_repo_from_db(repo_path: Path):
    """Delete specific repository from database"""
    path_str = str(repo_path.resolve())
    # Escape quotes properly for shell
    escaped_path = path_str.replace('"', '\\"')
    run(f'{CGC_CMD} query "MATCH (r:Repository {{path: \\"{escaped_path}\\"}})-[:CONTAINS*]->(n) DETACH DELETE r, n"')
    run(f'{CGC_CMD} query "MATCH (r:Repository {{path: \\"{escaped_path}\\"}}) DETACH DELETE r"')

def index_repo(test_dir: Path):
    """Index the test repository"""
    output = run(f"{CGC_CMD} index {shlex.quote(str(test_dir))}")
    print(f"INDEX OUTPUT: {output}")  # Show FULL output
    time.sleep(0.5)  # Wait for indexing to complete
    return output

def query_all_files():
    """Query ALL files in database for debugging"""
    output = run(f'{CGC_CMD} query "MATCH (f:File) RETURN f.name, f.path LIMIT 20"')
    print(f"ALL FILES IN DB: {output}")
    return output

def query_all_repos():
    """Query ALL repositories in database for debugging"""
    output = run(f'{CGC_CMD} query "MATCH (r:Repository) RETURN r.name, r.path"')
    print(f"ALL REPOS IN DB: {output}")
    return output

def query_files_for_repo(test_dir: Path):
    """Query files ONLY from specific test repository"""
    repo_path = str(test_dir.resolve())
    
    # Debug: Show all repos first
    query_all_repos()
    
    # Use simpler query - match by repository name (folder name)
    repo_name = test_dir.name
    output = run(f'{CGC_CMD} query "MATCH (r:Repository)-[:CONTAINS*]->(f:File) WHERE r.path CONTAINS \\"{repo_name}\\" RETURN f.name"')
    
    print(f"QUERY OUTPUT for {repo_name}: {output}")
    
    return extract_file_names(output)

def extract_file_names(output):
    """Extract file names from JSON output"""
    file_names = []
    try:
        json_start = output.find('[')
        json_end = output.rfind(']') + 1
        if json_start != -1 and json_end > json_start:
            json_str = output[json_start:json_end]
            data = json.loads(json_str)
            for item in data:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, str) and not value.startswith('/'):
                            file_names.append(value)
    except json.JSONDecodeError:
        pass
    return file_names

# ============================================================
# TC-01 to TC-11: Unit Tests (No database needed)
# ============================================================

def test_tc01_default_ignore_patterns_exists():
    """Verify DEFAULT_IGNORE_PATTERNS list exists and is not empty"""
    assert DEFAULT_IGNORE_PATTERNS is not None
    assert isinstance(DEFAULT_IGNORE_PATTERNS, list)
    assert len(DEFAULT_IGNORE_PATTERNS) > 0

def test_tc02_validate_pattern_format():
    """Verify patterns are either glob extensions (*.foo) or gitignore-style directory names (name/)"""
    for pattern in DEFAULT_IGNORE_PATTERNS:
        ok = pattern.startswith("*.") or (pattern.endswith("/") and not pattern.startswith("*"))
        assert ok, f"Pattern '{pattern}' must be '*.ext' or a directory pattern like 'name/'"

def test_tc03_media_patterns_included():
    """Verify media patterns (*.png, *.jpg, *.mp4) are included in defaults"""
    assert "node_modules/" in DEFAULT_IGNORE_PATTERNS
    assert "*.png" in DEFAULT_IGNORE_PATTERNS
    assert "*.jpg" in DEFAULT_IGNORE_PATTERNS
    assert "*.mp4" in DEFAULT_IGNORE_PATTERNS

def test_tc04_archive_patterns_included():
    """Verify archive patterns (*.zip, *.tar, *.gz) are included in defaults"""
    assert "*.zip" in DEFAULT_IGNORE_PATTERNS
    assert "*.tar" in DEFAULT_IGNORE_PATTERNS
    assert "*.gz" in DEFAULT_IGNORE_PATTERNS

def test_tc05_pathspec_creation():
    """Verify PathSpec object is created successfully from default patterns"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec is not None
    assert isinstance(spec, PathSpec)

def test_tc06_match_media_files():
    """Verify image files (png, jpg, jpeg) are matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("image.png") == True
    assert spec.match_file("photo.jpg") == True
    assert spec.match_file("icon.jpeg") == True

def test_tc07_match_video_audio_files():
    """Verify video/audio files (mp4, mp3) are matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("video.mp4") == True
    assert spec.match_file("song.mp3") == True

def test_tc08_do_not_match_source_files():
    """Verify source files (.py, .js) are NOT matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("main.py") == False
    assert spec.match_file("app.js") == False

def test_tc09_do_not_match_config_files():
    """Verify config files (.json, .yaml, .md, .txt) are NOT matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("config.json") == False
    assert spec.match_file("settings.yaml") == False
    assert spec.match_file("README.md") == False
    assert spec.match_file("notes.txt") == False

def test_tc10_do_not_match_extensionless_files():
    """Verify extensionless files (Makefile) are NOT matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("Makefile") == False
    assert spec.match_file("empty_file") == False

def test_tc11_match_files_in_subdirectories():
    """Verify media files in subdirectories are also matched for ignoring"""
    spec = PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS)
    assert spec.match_file("assets/image.png") == True
    assert spec.match_file("src/images/photo.jpg") == True

