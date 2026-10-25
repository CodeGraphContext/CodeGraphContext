"""package_resolver runs npm, go, gem and pkg-config by name and reads their output.

On Windows, npm and gem are batch files (npm.cmd, gem.cmd) that a bare name doesn't
launch, and the tools print UTF-8 rather than the locale's code page.
"""
import os
import subprocess
import sys
from pathlib import Path

from codegraphcontext.tools import package_resolver
from codegraphcontext.tools.package_resolver import get_local_package_path


def _fake_npm(bin_dir: Path, global_root: Path) -> None:
    """Install an `npm` on PATH whose `npm root -g` prints global_root as UTF-8."""
    emit = bin_dir / "emit.py"
    emit.write_text(
        "import sys\n"
        f"sys.stdout.buffer.write({str(global_root)!r}.encode('utf-8') + b'\\n')\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        (bin_dir / "npm.cmd").write_text(f'@"{sys.executable}" "{emit}"\r\n', encoding="utf-8")
    else:
        npm = bin_dir / "npm"
        npm.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{emit}"\n', encoding="utf-8")
        npm.chmod(0o755)


def test_global_npm_package_under_a_non_ascii_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    global_root = tmp_path / "Zoë 使用者" / "npm" / "node_modules"
    (global_root / "left-pad").mkdir(parents=True)
    _fake_npm(bin_dir, global_root)

    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.chdir(tmp_path)  # no ./node_modules here

    assert get_local_package_path("left-pad", "javascript") == str(
        (global_root / "left-pad").resolve()
    )


def test_tools_are_resolved_on_path_and_read_as_utf8(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr(package_resolver.shutil, "which", lambda name: f"/opt/bin/{name}.cmd")
    monkeypatch.setattr(package_resolver.subprocess, "run", fake_run)
    monkeypatch.chdir(Path(__file__).parent)

    get_local_package_path("surely-not-installed-xyz", "javascript")
    get_local_package_path("example.com/surely/not/installed", "go")
    get_local_package_path("surely-not-installed-xyz", "ruby")

    tools = [args[0] for args, _ in calls]
    assert "/opt/bin/npm.cmd" in tools
    assert "/opt/bin/go.cmd" in tools
    assert "/opt/bin/gem.cmd" in tools
    for _, kwargs in calls:
        assert kwargs.get("encoding") == "utf-8"
