"""Unit tests for scip-typescript workspace detection in ScipIndexer._build_command."""

import json
from pathlib import Path

from codegraphcontext.tools.scip_indexer import ScipIndexer


def _ts_cmd(project_path: Path) -> list:
    out = project_path / "index.scip"
    return ScipIndexer()._build_command("typescript", "scip-typescript", project_path, out)


# --- pnpm ------------------------------------------------------------------

def test_pnpm_workspace(tmp_path: Path) -> None:
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    assert "--pnpm-workspaces" in _ts_cmd(tmp_path)


def test_pnpm_takes_precedence_over_root_tsconfig(tmp_path: Path) -> None:
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    (tmp_path / "tsconfig.json").write_text("{}")
    cmd = _ts_cmd(tmp_path)
    assert "--pnpm-workspaces" in cmd
    assert "--yarn-workspaces" not in cmd


def test_pnpm_wins_over_package_json_workspaces(tmp_path: Path) -> None:
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'p/*'\n")
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["p/*"]}))
    assert "--pnpm-workspaces" in _ts_cmd(tmp_path)


# --- yarn / npm (shared `workspaces` field) --------------------------------

def test_yarn_npm_workspaces_array_form(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/*"]}))
    assert "--yarn-workspaces" in _ts_cmd(tmp_path)


def test_yarn_workspaces_object_form(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": {"packages": ["a"]}}))
    assert "--yarn-workspaces" in _ts_cmd(tmp_path)


# --- single project --------------------------------------------------------

def test_single_project_with_tsconfig(tmp_path: Path) -> None:
    (tmp_path / "tsconfig.json").write_text("{}")
    out = tmp_path / "index.scip"
    assert _ts_cmd(tmp_path) == ["scip-typescript", "index", "--output", str(out)]


def test_package_json_without_workspaces_is_not_a_monorepo(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "app", "version": "1.0.0"}))
    (tmp_path / "tsconfig.json").write_text("{}")
    cmd = _ts_cmd(tmp_path)
    assert "--yarn-workspaces" not in cmd
    assert "--pnpm-workspaces" not in cmd


# --- robustness ------------------------------------------------------------

def test_malformed_package_json_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{ this is not valid json ")
    out = tmp_path / "index.scip"
    assert _ts_cmd(tmp_path) == ["scip-typescript", "index", "--output", str(out)]
