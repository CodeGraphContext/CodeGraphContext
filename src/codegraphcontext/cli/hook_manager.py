"""Git hook management for keeping CGC indexes in sync."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
import subprocess


MANAGED_MARKER = "# CGC_MANAGED_HOOK"
HOOK_NAMES = ("post-commit", "post-checkout")
GITATTRIBUTES_ENTRY = "*.cgc merge=cgc-bundle"


class HookError(RuntimeError):
    """Raised when hook installation cannot proceed safely."""


@dataclass(frozen=True)
class GitRepository:
    root: Path
    git_dir: Path


@dataclass(frozen=True)
class HookStatus:
    repo_root: Path
    git_dir: Path
    installed_hooks: tuple[str, ...]
    unmanaged_hooks: tuple[str, ...]
    has_merge_driver: bool
    has_gitattributes_entry: bool

    @property
    def installed(self) -> bool:
        return (
            bool(self.installed_hooks)
            and self.has_merge_driver
            and self.has_gitattributes_entry
        )


def find_git_repository(start: Path | str | None = None) -> GitRepository:
    """Find the nearest Git repository root and git directory."""
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        git_path = candidate / ".git"
        if git_path.is_dir():
            return GitRepository(root=candidate, git_dir=git_path)
        if git_path.is_file():
            target = _read_worktree_gitdir(git_path)
            return GitRepository(root=candidate, git_dir=target)

    raise HookError("No Git repository found from the current directory.")


def install_hooks(start: Path | str | None = None, *, force: bool = False) -> HookStatus:
    repo = find_git_repository(start)
    hooks_dir = repo.git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    script = _hook_script(repo.root)
    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        if hook_path.exists() and not _is_managed_hook(hook_path) and not force:
            raise HookError(
                f"{hook_name} already exists and is not managed by CGC. "
                "Re-run with --force to replace it."
            )
        hook_path.write_text(script, encoding="utf-8")
        mode = hook_path.stat().st_mode
        hook_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    _ensure_gitattributes(repo.root)
    _configure_merge_driver(repo.root)
    return get_hook_status(repo.root)


def uninstall_hooks(start: Path | str | None = None) -> HookStatus:
    repo = find_git_repository(start)
    hooks_dir = repo.git_dir / "hooks"

    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        if hook_path.exists() and _is_managed_hook(hook_path):
            hook_path.unlink()

    _remove_gitattributes_entry(repo.root)
    _unset_git_config(repo.root, "merge.cgc-bundle.name")
    _unset_git_config(repo.root, "merge.cgc-bundle.driver")
    return get_hook_status(repo.root)


def get_hook_status(start: Path | str | None = None) -> HookStatus:
    repo = find_git_repository(start)
    hooks_dir = repo.git_dir / "hooks"
    installed_hooks: list[str] = []
    unmanaged_hooks: list[str] = []

    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        if not hook_path.exists():
            continue
        if _is_managed_hook(hook_path):
            installed_hooks.append(hook_name)
        else:
            unmanaged_hooks.append(hook_name)

    return HookStatus(
        repo_root=repo.root,
        git_dir=repo.git_dir,
        installed_hooks=tuple(installed_hooks),
        unmanaged_hooks=tuple(unmanaged_hooks),
        has_merge_driver=_has_git_config(repo.root, "merge.cgc-bundle.driver"),
        has_gitattributes_entry=_has_gitattributes_entry(repo.root),
    )


def _read_worktree_gitdir(git_file: Path) -> Path:
    content = git_file.read_text(encoding="utf-8").strip()
    prefix = "gitdir:"
    if not content.lower().startswith(prefix):
        raise HookError(f"Unsupported .git file format at {git_file}")

    raw_path = content[len(prefix):].strip()
    git_dir = Path(raw_path)
    if not git_dir.is_absolute():
        git_dir = (git_file.parent / git_dir).resolve()
    return git_dir


def _hook_script(repo_root: Path) -> str:
    repo_root_value = _sh_quote(str(repo_root))
    return (
        "#!/bin/sh\n"
        f"{MANAGED_MARKER}: CodeGraphContext auto-update hook\n"
        f"CGC_REPO_ROOT={repo_root_value}\n"
        "if command -v cgc >/dev/null 2>&1; then\n"
        '  cgc update "$CGC_REPO_ROOT" --quiet\n'
        "else\n"
        '  python -m codegraphcontext update "$CGC_REPO_ROOT" --quiet\n'
        "fi\n"
    )


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _is_managed_hook(path: Path) -> bool:
    try:
        return MANAGED_MARKER in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _ensure_gitattributes(repo_root: Path) -> None:
    path = repo_root / ".gitattributes"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    if any(line.strip() == GITATTRIBUTES_ENTRY for line in lines):
        return

    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    path.write_text(f"{prefix}{GITATTRIBUTES_ENTRY}\n", encoding="utf-8")


def _remove_gitattributes_entry(repo_root: Path) -> None:
    path = repo_root / ".gitattributes"
    if not path.exists():
        return

    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() != GITATTRIBUTES_ENTRY
    ]
    if lines:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        path.unlink()


def _has_gitattributes_entry(repo_root: Path) -> bool:
    path = repo_root / ".gitattributes"
    if not path.exists():
        return False
    return any(
        line.strip() == GITATTRIBUTES_ENTRY
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _configure_merge_driver(repo_root: Path) -> None:
    _git_config(repo_root, "merge.cgc-bundle.name", "CodeGraphContext bundle merge driver")
    _git_config(repo_root, "merge.cgc-bundle.driver", "cgc bundle merge %O %A %B")


def _git_config(repo_root: Path, key: str, value: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), "config", key, value], check=True)


def _unset_git_config(repo_root: Path, key: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), "config", "--unset-all", key], check=False)


def _has_git_config(repo_root: Path, key: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--get", key],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0
