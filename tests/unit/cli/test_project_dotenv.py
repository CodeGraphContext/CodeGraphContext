"""Tests for per-repo vs global project .env loading (BUG-001)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codegraphcontext.cli import config_manager


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CGC_LOAD_PROJECT_ENV", raising=False)
    monkeypatch.delenv("CGC_IGNORE_PROJECT_ENV", raising=False)
    return tmp_path


def test_global_mode_skips_project_dotenv_even_under_home(isolated_home):
    repo = isolated_home / "myrepo"
    cgc_dir = repo / ".codegraphcontext"
    cgc_dir.mkdir(parents=True)
    (cgc_dir / ".env").write_text("NEO4J_URI=bolt://repo-local:7687\n", encoding="utf-8")

    with patch.object(config_manager, "load_context_config") as mock_cfg:
        mock_cfg.return_value = config_manager.ContextConfig(mode="global")
        with patch.object(Path, "cwd", return_value=repo):
            assert config_manager.should_apply_project_dotenv() is False


def test_per_repo_mode_loads_project_dotenv(isolated_home):
    repo = isolated_home / "myrepo"
    cgc_dir = repo / ".codegraphcontext"
    cgc_dir.mkdir(parents=True)
    (cgc_dir / ".env").write_text("DEFAULT_DATABASE=kuzudb\n", encoding="utf-8")

    with patch.object(config_manager, "load_context_config") as mock_cfg:
        mock_cfg.return_value = config_manager.ContextConfig(mode="per-repo")
        with patch.object(Path, "cwd", return_value=repo):
            assert config_manager.should_apply_project_dotenv() is True


def test_cgc_load_project_env_forces_load_outside_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CGC_LOAD_PROJECT_ENV", "1")
    with patch.object(config_manager, "load_context_config") as mock_cfg:
        mock_cfg.return_value = config_manager.ContextConfig(mode="global")
        assert config_manager.should_apply_project_dotenv() is True
