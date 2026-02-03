
import pytest
from pathlib import Path
import os
import shutil
import tempfile

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
    temp_dir = tempfile.mkdtemp(prefix="cgc_test_unit_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

