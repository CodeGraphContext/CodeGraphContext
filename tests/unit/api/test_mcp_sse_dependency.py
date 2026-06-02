import tomllib
from pathlib import Path


def test_mcp_sse_runtime_dependency_is_declared():
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())

    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.startswith("mcp") for dependency in dependencies)
