"""Project configuration must not escape the current working directory (#1099)."""

import pytest

from codegraphcontext.cli import config_manager


@pytest.fixture
def project(tmp_path, monkeypatch):
    repo = tmp_path / "workspace" / "project"
    repo.mkdir(parents=True)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", tmp_path / "global" / ".env")
    monkeypatch.setattr(
        config_manager, "load_context_config",
        lambda: config_manager.ContextConfig(mode="per-repo"),
    )
    for key in ("CGC_LOAD_PROJECT_ENV", "CGC_IGNORE_PROJECT_ENV", "PARALLEL_WORKERS"):
        monkeypatch.delenv(key, raising=False)
    return repo


@pytest.mark.parametrize("relative", [".env", ".codegraphcontext/.env"])
def test_parent_project_settings_are_not_loaded(project, relative):
    parent_env = project.parent / relative
    parent_env.parent.mkdir(exist_ok=True)
    parent_env.write_text("PARALLEL_WORKERS=19\n", encoding="utf-8")

    assert config_manager.find_local_env() is None
    assert config_manager.load_config()["PARALLEL_WORKERS"] == config_manager.DEFAULT_CONFIG["PARALLEL_WORKERS"]


def test_project_specific_settings_win_over_cwd_dotenv(project):
    (project / ".env").write_text("PARALLEL_WORKERS=7\n", encoding="utf-8")
    cgc = project / ".codegraphcontext"
    cgc.mkdir()
    (cgc / ".env").write_text("PARALLEL_WORKERS=11\n", encoding="utf-8")

    assert config_manager.load_config()["PARALLEL_WORKERS"] == "11"


def test_cwd_dotenv_is_supported_and_environment_still_wins(project, monkeypatch):
    (project / ".env").write_text("PARALLEL_WORKERS=7\n", encoding="utf-8")
    assert config_manager.load_config()["PARALLEL_WORKERS"] == "7"
    monkeypatch.setenv("PARALLEL_WORKERS", "13")
    assert config_manager.load_config()["PARALLEL_WORKERS"] == "13"


def test_force_load_does_not_expand_search_to_parent(project, monkeypatch):
    monkeypatch.setattr(
        config_manager, "load_context_config",
        lambda: config_manager.ContextConfig(mode="global"),
    )
    monkeypatch.setenv("CGC_LOAD_PROJECT_ENV", "1")
    (project.parent / ".env").write_text("PARALLEL_WORKERS=19\n", encoding="utf-8")
    assert config_manager.find_local_env() is None
    (project / ".env").write_text("PARALLEL_WORKERS=7\n", encoding="utf-8")
    assert config_manager.load_config()["PARALLEL_WORKERS"] == "7"


def test_ignore_project_env_wins_over_force_load(project, monkeypatch):
    (project / ".env").write_text("PARALLEL_WORKERS=7\n", encoding="utf-8")
    monkeypatch.setenv("CGC_LOAD_PROJECT_ENV", "1")
    monkeypatch.setenv("CGC_IGNORE_PROJECT_ENV", "1")
    assert config_manager.find_local_env() is None
