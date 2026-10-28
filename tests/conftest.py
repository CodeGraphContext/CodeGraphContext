
import sys
from pathlib import Path
import tempfile
import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
# Repo root, so test modules import as ``tests.<module>`` no matter how pytest
# was launched.
REPO_ROOT = SRC_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Update the golden files with the new exported results."
    )

@pytest.fixture
def update_goldens(request):
    return request.config.getoption("--update-goldens")

# Root of the test folder
TEST_ROOT = Path(__file__).parent.absolute()
FIXTURES_DIR = TEST_ROOT / "fixtures"
SAMPLE_PROJECTS_DIR = FIXTURES_DIR / "sample_projects"

@pytest.fixture(scope="session")
def sample_projects_path():
    """Returns the path to the directory containing all sample projects."""
    if not SAMPLE_PROJECTS_DIR.exists():
        pytest.fail(f"Sample projects directory not found at {SAMPLE_PROJECTS_DIR}")
    return SAMPLE_PROJECTS_DIR

@pytest.fixture(scope="session")
def python_sample_project(sample_projects_path):
    """Returns path to the Python sample project."""
    path = sample_projects_path / "sample_project" # Confusing name in old tests, it was just "sample_project"
    if not path.exists():
        pytest.fail(f"Python sample project not found at {path}")
    return path

@pytest.fixture(scope="session")
def javascript_sample_project(sample_projects_path):
    """Returns path to the JavaScript sample project."""
    path = sample_projects_path / "sample_project_javascript"
    if not path.exists():
        pytest.fail(f"JavaScript sample project not found at {path}")
    return path

@pytest.fixture
def temp_test_dir():
    """Creates a temporary directory for file operations, cleaned up after test."""
    with tempfile.TemporaryDirectory(prefix="cgc_test_unit_") as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def assert_parser_result():
    """Fail fast when a parser unexpectedly returns a non-dict payload."""
    def _assert(result):
        if not isinstance(result, dict):
            pytest.fail(f"Expected parser result to be a dict, got {type(result).__name__}: {result!r}")
        return result

    return _assert


#: The embedded native libraries that must never share one interpreter: a
#: full-suite run did end in "double free or corruption" once a test loaded
#: ladybug in-process (#1731's probe, called from an e2e test) next to kuzu.
_EMBEDDED_NATIVE_MODULES = ("kuzu", "ladybug")


def _loaded_embedded_natives():
    return {m for m in _EMBEDDED_NATIVE_MODULES if m in sys.modules}


@pytest.fixture(autouse=True)
def _one_embedded_native_library_per_process():
    """Fail the test that loads the second embedded library into this process.

    Without it the damage surfaces far away: the process may abort at exit, or
    later tests of the first backend fail. Load the other backend in a
    subprocess instead (as the native-backend tests do)."""
    before = _loaded_embedded_natives()
    yield
    after = _loaded_embedded_natives()
    if len(after) > 1 and len(before) <= 1:
        pytest.fail(
            f"this test loaded {sorted(after - before)} into a process that already held "
            f"{sorted(before)}: both embedded native libraries are now in one interpreter. "
            "Load the other backend in a subprocess.",
            pytrace=False,
        )
