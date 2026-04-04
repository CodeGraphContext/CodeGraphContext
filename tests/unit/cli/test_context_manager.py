from pathlib import Path


def _set_paths(cm, tmp_path: Path):
    cm.GLOBAL_CONFIG_DIR = tmp_path / ".codegraphcontext"
    cm.GLOBAL_CONFIG_YAML = cm.GLOBAL_CONFIG_DIR / "config.yaml"
    cm.CONTEXTS_DIR = cm.GLOBAL_CONFIG_DIR / "contexts"


def test_resolve_named_shared_context(tmp_path):
    from codegraphcontext.cli import context_manager as cm

    _set_paths(cm, tmp_path)

    resolution = cm.resolve_context(context_name="ProjectAB")

    assert resolution.mode == "shared"
    assert resolution.context_name == "ProjectAB"
    assert resolution.context_dir == cm.CONTEXTS_DIR / "ProjectAB"
    assert resolution.context_dir.exists()


def test_local_context_precedence_over_global_default(tmp_path):
    from codegraphcontext.cli import context_manager as cm

    _set_paths(cm, tmp_path)
    cm.save_global_context_config({"default_context_mode": "shared", "default_shared_context": "global-shared"})

    repo_root = tmp_path / "repo"
    (repo_root / ".codegraphcontext").mkdir(parents=True)

    resolution = cm.resolve_context(path_hint=repo_root)

    assert resolution.mode == "per-repo"
    assert resolution.context_dir == repo_root / ".codegraphcontext"
    assert resolution.source == "local-context-dir"


def test_set_default_context_mode_shared(tmp_path):
    from codegraphcontext.cli import context_manager as cm

    _set_paths(cm, tmp_path)

    cfg = cm.set_default_context_mode("shared", "Team-Context")
    reloaded = cm.load_global_context_config()

    assert cfg["default_context_mode"] == "shared"
    assert cfg["default_shared_context"] == "Team-Context"
    assert reloaded["default_context_mode"] == "shared"
    assert reloaded["default_shared_context"] == "Team-Context"
