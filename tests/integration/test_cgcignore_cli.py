"""Hermetic end-to-end .cgcignore tests through the real `cgc` CLI (#1422).

Moved out of tests/unit: each case spawns several `cgc` subprocesses against a
per-test embedded database (fresh HOME per test), which is integration-suite
work. The old version shared one /tmp/cgc_test/_home database across every
test and every run, gated the cases on a live Neo4j (so they were permanently
skipped on most machines), and wiped the shared DB mid-suite — the source of
the intermittent, name-shifting failures in full-suite runs.
"""
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
# TC-12 to TC-20: Integration Tests
# ============================================================

@pytest.fixture(autouse=True)
def clean_before_integration_test(request):
    """Prepare DB only for integration-style cases that require live cgc DB access."""
    name = request.node.name
    match = re.match(r"test_tc(\d+)_", name)
    case_id = int(match.group(1)) if match else 0

    # TC-12+ are integration tests that execute live `cgc` commands.
    if case_id < 12:
        yield
        return

    # Hermetic per-test HOME + embedded backend (#1422): no server gate and
    # no cross-test wipe needed — every test starts from an empty database.
    yield

def test_tc12_default_filtering_without_cgcignore():
    """Verify default patterns apply when .cgcignore file does not exist.
    
    Note: Only files with supported language extensions (.py, .js, .ts, etc.)
    are indexed as File nodes. Non-code files like .md are filtered by cgcignore
    but still won't appear in the graph because there is no parser for them.
    """
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "image.png").write_text("fake")
    (test_dir / "video.mp4").write_text("fake")
    (test_dir / "README.md").write_text("# readme")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-12 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "image.png" not in file_names
    assert "video.mp4" not in file_names

def test_tc13_cgcignore_adds_new_rules():
    """Verify user can add new ignore rules via .cgcignore (e.g., *.txt)"""
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "notes.txt").write_text("notes")
    (test_dir / ".cgcignore").write_text("*.txt\n")
    
    # Verify .cgcignore exists
    assert (test_dir / ".cgcignore").exists()
    print(f".cgcignore content: {(test_dir / '.cgcignore').read_text()}")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-13 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "notes.txt" not in file_names, f"notes.txt should be ignored but found in {file_names}"

def test_tc14_cgcignore_ignores_comments():
    """Verify comments (#) in .cgcignore are properly ignored"""
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "notes.txt").write_text("notes")
    
    cgcignore_content = """# This is a comment
*.txt
# Another comment
"""
    (test_dir / ".cgcignore").write_text(cgcignore_content)
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-14 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "notes.txt" not in file_names

def test_tc15_cgcignore_ignores_empty_lines():
    """Verify empty lines in .cgcignore are properly ignored"""
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "notes.txt").write_text("notes")
    
    cgcignore_content = """

*.txt

"""
    (test_dir / ".cgcignore").write_text(cgcignore_content)
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-15 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "notes.txt" not in file_names

def test_tc16_merge_default_and_user_patterns():
    """Verify default and user patterns are merged and both apply"""
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "image.png").write_text("fake")
    (test_dir / "config.json").write_text("{}")
    (test_dir / ".cgcignore").write_text("*.json\n")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-16 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "image.png" not in file_names  # Default pattern
    assert "config.json" not in file_names  # User pattern

def test_tc17_expected_output_validation():
    """Verify expected output matches in a mixed repository.
    
    Only files with supported language extensions appear as File nodes.
    """
    test_dir = setup_test_dir(get_unique_test_dir())
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "helper.py").write_text("def help(): pass")
    (test_dir / "README.md").write_text("# readme")
    (test_dir / "image.png").write_text("fake")
    (test_dir / "video.mp4").write_text("fake")
    (test_dir / "data.zip").write_text("fake")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-17 FILES: {file_names}")
    
    expected_present = ["main.py", "helper.py"]
    for f in expected_present:
        assert f in file_names, f"{f} should be present"
    
    expected_absent = ["image.png", "video.mp4", "data.zip"]
    for f in expected_absent:
        assert f not in file_names, f"{f} should be ignored"

def test_tc18_cgcignore_discovery_nested():
    """Verify .cgcignore is discovered and applied in nested directories"""
    test_dir = setup_test_dir(get_unique_test_dir())
    
    nested = test_dir / "src"
    nested.mkdir()
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / ".cgcignore").write_text("*.txt\n")
    (nested / "inner.py").write_text("# inner")
    (nested / "inner.txt").write_text("notes")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-18 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "inner.py" in file_names
    assert "inner.txt" not in file_names

def test_tc19_nested_filtering_merged():
    """Verify merged patterns correctly apply to nested files.
    
    CSS files don't have a parser so won't appear as File nodes.
    Use a supported extension (.py) in nested dir to verify nesting works.
    """
    test_dir = setup_test_dir(get_unique_test_dir())
    
    nested = test_dir / "assets"
    nested.mkdir()
    
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / ".cgcignore").write_text("*.log\n")
    (nested / "helper.py").write_text("def h(): pass")
    (nested / "debug.log").write_text("log")
    (nested / "icon.png").write_text("fake")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-19 FILES: {file_names}")
    
    assert "main.py" in file_names
    assert "helper.py" in file_names
    assert "debug.log" not in file_names  # User pattern
    assert "icon.png" not in file_names   # Default pattern

def test_tc20_combined_filtering_real_scenario():
    """Verify real-world scenario with DEFAULT + .cgcignore combined filtering.
    
    Only files with supported language extensions (.py, .js, etc.) appear as
    File nodes. Non-code files like .json and .md pass cgcignore but have no
    parser, so they won't be in the graph.
    """
    test_dir = setup_test_dir(get_unique_test_dir())
    
    src = test_dir / "src"
    assets = test_dir / "assets"
    src.mkdir()
    assets.mkdir()
    
    (test_dir / "main.py").write_text("print('hello')")
    (src / "app.py").write_text("# app")
    (src / "utils.py").write_text("# utils")
    (test_dir / "config.json").write_text("{}")
    (test_dir / "README.md").write_text("# Project")
    (assets / "logo.png").write_text("fake")
    (assets / "video.mp4").write_text("fake")
    (test_dir / ".cgcignore").write_text("*.log\n*.tmp\n")
    (test_dir / "debug.log").write_text("log")
    (test_dir / "cache.tmp").write_text("temp")
    
    index_repo(test_dir)
    file_names = query_files_for_repo(test_dir)
    
    print(f"TC-20 FILES: {file_names}")
    
    expected_present = ["main.py", "app.py", "utils.py"]
    for f in expected_present:
        assert f in file_names, f"{f} should be present"
    
    assert "logo.png" not in file_names   # Default pattern
    assert "video.mp4" not in file_names  # Default pattern
    assert "debug.log" not in file_names  # User pattern
    assert "cache.tmp" not in file_names  # User pattern


# ============================================================
# TC-21 to TC-23: .cgcignore Auto-Creation Tests
# ============================================================

def test_tc21_cgcignore_auto_created_when_not_exists():
    """
    Verify .cgcignore file is auto-created when it does not exist:
    1. Before indexing: .cgcignore does NOT exist
    2. After indexing: .cgcignore IS auto-created with default patterns
    3. Default patterns are correctly applied to filter files
    """
    test_dir = setup_test_dir(get_unique_test_dir())
    
    # Step 1: Create files WITHOUT .cgcignore
    (test_dir / "main.py").write_text("print('hello')")
    (test_dir / "app.js").write_text("console.log('hi')")
    (test_dir / "README.md").write_text("# Project")
    (test_dir / "config.json").write_text("{}")
    
    # Media files (should be ignored by DEFAULT patterns)
    (test_dir / "image.png").write_text("fake png")
    (test_dir / "photo.jpg").write_text("fake jpg")
    (test_dir / "video.mp4").write_text("fake mp4")
    (test_dir / "song.mp3").write_text("fake mp3")
    
    # Archive files (should be ignored by DEFAULT patterns)
    (test_dir / "archive.zip").write_text("fake zip")
    (test_dir / "backup.tar").write_text("fake tar")
    
    # ✅ CONFIRM: .cgcignore does NOT exist before indexing
    cgcignore_path = test_dir / ".cgcignore"
    assert not cgcignore_path.exists(), ".cgcignore should NOT exist before indexing"
    
    print(f"\n{'='*60}")
    print(f"BEFORE INDEXING:")
    print(f"  .cgcignore exists: {cgcignore_path.exists()}")
    print(f"  Files in directory: {[f.name for f in test_dir.iterdir()]}")
    print(f"{'='*60}\n")
    
    # Step 2: Index the repository
    index_output = index_repo(test_dir)
    
    # ✅ CONFIRM: .cgcignore IS AUTO-CREATED after indexing
    print(f"\n{'='*60}")
    print(f"AFTER INDEXING:")
    print(f"  .cgcignore exists: {cgcignore_path.exists()}")
    print(f"  Files in directory: {[f.name for f in test_dir.iterdir()]}")
    print(f"{'='*60}\n")
    
    assert cgcignore_path.exists(), \
        ".cgcignore should be AUTO-CREATED after indexing"
    
    # ✅ CONFIRM: Auto-created .cgcignore has content (default patterns)
    cgcignore_content = cgcignore_path.read_text()
    print(f"Auto-created .cgcignore content:\n{cgcignore_content}")
    assert len(cgcignore_content) > 0, ".cgcignore should have default patterns"
    
    # Step 3: Query indexed files
    file_names = query_files_for_repo(test_dir)
    
    print(f"\n{'='*60}")
    print(f"INDEXED FILES: {file_names}")
    print(f"{'='*60}\n")
    
    # ✅ CONFIRM: Source files with supported parsers ARE indexed
    expected_present = ["main.py", "app.js"]
    for f in expected_present:
        assert f in file_names, f"'{f}' should be indexed (not ignored)"
    
    # ✅ CONFIRM: Media/Archive files ARE ignored (by DEFAULT patterns)
    expected_ignored = ["image.png", "photo.jpg", "video.mp4", "song.mp3", "archive.zip", "backup.tar"]
    for f in expected_ignored:
        assert f not in file_names, f"'{f}' should be ignored by DEFAULT patterns"
    
    print(f"\n{'='*60}")
    print(f"✅ TEST PASSED!")
    print(f"   - .cgcignore WAS auto-created")
    print(f"   - Default patterns correctly applied")
    print(f"   - Source files indexed: {expected_present}")
    print(f"   - Media/Archive files ignored: {expected_ignored}")
    print(f"{'='*60}\n")


def test_tc22_empty_array_plus_default_patterns():
    """
    Verify merge logic: empty array + default patterns = default patterns only
    
    Logic:
        user_patterns = []  (when .cgcignore is empty)
        final = DEFAULT_IGNORE_PATTERNS + user_patterns
        final = DEFAULT_IGNORE_PATTERNS + []
        final = DEFAULT_IGNORE_PATTERNS
    """
    # Unit test: Verify the merge logic
    user_patterns = []  # Empty array (empty .cgcignore)
    
    # Simulate merge logic
    final_patterns = DEFAULT_IGNORE_PATTERNS + user_patterns
    
    # ✅ CONFIRM: Final patterns = Default patterns only
    assert final_patterns == DEFAULT_IGNORE_PATTERNS, \
        "Empty array + default patterns should equal default patterns only"
    
    # ✅ CONFIRM: PathSpec works with merged patterns
    spec = PathSpec.from_lines("gitwildmatch", final_patterns)
    
    # Media files should be ignored
    assert spec.match_file("image.png") == True
    assert spec.match_file("video.mp4") == True
    assert spec.match_file("archive.zip") == True
    
    # Source files should NOT be ignored
    assert spec.match_file("main.py") == False
    assert spec.match_file("config.json") == False
    
    print(f"\n{'='*60}")
    print(f"✅ TEST PASSED!")
    print(f"   - [] + DEFAULT_PATTERNS = DEFAULT_PATTERNS")
    print(f"   - Length: {len(final_patterns)} patterns")
    print(f"{'='*60}\n")


def test_tc23_cgcignore_auto_created_with_default_content():
    """
    Verify auto-created .cgcignore file contains default patterns:
    
    - Repo A: WITHOUT .cgcignore → auto-created after indexing with default content
    - Repo B: WITH empty .cgcignore → remains empty after indexing
    
    Both repos should apply default patterns for filtering
    """
    # Repo A: Without .cgcignore (will be auto-created)
    test_dir_a = setup_test_dir(get_unique_test_dir())
    (test_dir_a / "main.py").write_text("print('a')")
    (test_dir_a / "image.png").write_text("fake")
    # NO .cgcignore file
    
    # Repo B: With empty .cgcignore (will remain empty)
    test_dir_b = setup_test_dir(get_unique_test_dir())
    (test_dir_b / "main.py").write_text("print('b')")
    (test_dir_b / "image.png").write_text("fake")
    (test_dir_b / ".cgcignore").write_text("")  # Empty file
    
    # ✅ CONFIRM: Repo A has NO .cgcignore before indexing
    assert not (test_dir_a / ".cgcignore").exists(), "Repo A should not have .cgcignore before indexing"
    
    # ✅ CONFIRM: Repo B HAS .cgcignore before indexing
    assert (test_dir_b / ".cgcignore").exists(), "Repo B should have .cgcignore before indexing"
    
    # Index both repositories
    index_repo(test_dir_a)
    index_repo(test_dir_b)
    
    # ✅ CONFIRM: Repo A now HAS .cgcignore (auto-created)
    assert (test_dir_a / ".cgcignore").exists(), \
        ".cgcignore should be AUTO-CREATED in Repo A"
    
    # ✅ CONFIRM: Auto-created .cgcignore has content
    cgcignore_a_content = (test_dir_a / ".cgcignore").read_text()
    print(f"\nRepo A .cgcignore content (auto-created):\n{cgcignore_a_content[:200]}...")
    assert len(cgcignore_a_content) > 0, "Auto-created .cgcignore should have content"
    
    # Query files from both repositories
    files_a = query_files_for_repo(test_dir_a)
    files_b = query_files_for_repo(test_dir_b)
    
    print(f"\n{'='*60}")
    print(f"Repo A (auto-created .cgcignore): {files_a}")
    print(f"Repo B (empty .cgcignore): {files_b}")
    print(f"{'='*60}\n")
    
    # ✅ Both should have main.py indexed
    assert "main.py" in files_a, "Repo A should have main.py"
    assert "main.py" in files_b, "Repo B should have main.py"
    
    # ✅ Both should ignore image.png (default pattern)
    assert "image.png" not in files_a, "Repo A should ignore image.png"
    assert "image.png" not in files_b, "Repo B should ignore image.png"
    
    print(f"\n{'='*60}")
    print(f"✅ TEST PASSED!")
    print(f"   - Repo A: .cgcignore auto-created with default content")
    print(f"   - Repo B: .cgcignore remained empty")
    print(f"   - Both repos correctly ignore media files")
    print(f"{'='*60}\n")


# ============================================================
# Run tests directly
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


# --- Root anchoring of multi-segment patterns (#1513) -------------------------
#
# Under gitignore semantics a slash anywhere except the trailing position
# anchors the pattern to the ignore root. Previously only a *leading* slash
# anchored, so `src/generated` also ignored `vendor/src/generated` -- copying a
# line out of .gitignore, which the docs encourage, silently over-ignored real
# source. Every expectation below was cross-checked against `git check-ignore`.


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        # multi-segment patterns are anchored to the root
        ("src/generated", "src/generated/a.py", True),
        ("src/generated", "vendor/src/generated/a.py", False),
        ("a/**/b", "a/b/f.py", True),
        ("a/**/b", "a/x/y/b/f.py", True),
        ("a/**/b", "z/a/b/f.py", False),
        ("docs/**", "docs/a.md", True),
        ("docs/**", "vendor/docs/a.md", False),
        # a trailing slash is not an internal slash: still matches at any depth
        ("build/", "build/a.py", True),
        ("build/", "sub/build/a.py", True),
        # ...but must still respect segment boundaries
        ("build/", "layout/a.py", False),
        # single-segment patterns keep matching at any depth
        ("node_modules", "node_modules/x.js", True),
        ("node_modules", "web/node_modules/x.js", True),
        # a leading `**/` means any depth even though a slash is present
        ("**/dist", "dist/a.js", True),
        ("**/dist", "web/dist/a.js", True),
        # an explicit leading slash anchors, as before
        ("/foo", "foo/a.py", True),
        ("/foo", "bar/foo/a.py", False),
    ],
)
def test_multi_segment_patterns_are_root_anchored(tmp_path, pattern, path, expected):
    (tmp_path / ".cgcignore").write_text(pattern + "\n", encoding="utf-8")
    spec, _ = build_ignore_spec(
        ignore_root=tmp_path, default_patterns=[], explicit_path=None
    )
    assert bool(spec.match_file(path)) is expected
