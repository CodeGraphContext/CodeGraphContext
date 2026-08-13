import os
import stat
import subprocess

import pytest

from codegraphcontext.cli.hook_manager import (
    GITATTRIBUTES_ENTRY,
    HookError,
    find_git_repository,
    get_hook_status,
    install_hooks,
    uninstall_hooks,
)


def _init_repo(path):
    path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL)
    return path


def test_find_git_repository_from_nested_directory(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    nested = repo / "src" / "pkg"
    nested.mkdir(parents=True)

    found = find_git_repository(nested)

    assert found.root == repo
    assert found.git_dir == repo / ".git"


def test_install_hooks_writes_managed_hooks_and_merge_driver(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    status = install_hooks(repo)

    assert status.installed
    assert set(status.installed_hooks) == {"post-commit", "post-checkout"}
    for hook_name in status.installed_hooks:
        hook = repo / ".git" / "hooks" / hook_name
        text = hook.read_text(encoding="utf-8")
        assert "CGC_MANAGED_HOOK" in text
        assert "cgc update" in text
        assert os.access(hook, os.X_OK)

    assert (repo / ".gitattributes").read_text(encoding="utf-8").strip() == GITATTRIBUTES_ENTRY
    driver = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "merge.cgc-bundle.driver"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert driver == "cgc bundle merge %O %A %B"


def test_install_hooks_refuses_unmanaged_existing_hook_without_force(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

    with pytest.raises(HookError, match="not managed by CGC"):
        install_hooks(repo)


def test_install_hooks_force_replaces_existing_hook(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")

    install_hooks(repo, force=True)

    assert "CGC_MANAGED_HOOK" in hook.read_text(encoding="utf-8")


def test_uninstall_removes_only_cgc_managed_artifacts(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    install_hooks(repo)

    unmanaged = repo / ".git" / "hooks" / "pre-commit"
    unmanaged.write_text("#!/bin/sh\necho keep\n", encoding="utf-8")

    status = uninstall_hooks(repo)

    assert not status.installed_hooks
    assert unmanaged.exists()
    assert not (repo / ".git" / "hooks" / "post-commit").exists()
    assert not (repo / ".git" / "hooks" / "post-checkout").exists()
    assert not (repo / ".gitattributes").exists()
    assert not get_hook_status(repo).has_merge_driver


def test_gitattributes_update_is_idempotent(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    install_hooks(repo)
    install_hooks(repo)

    lines = (repo / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert lines.count(GITATTRIBUTES_ENTRY) == 1
