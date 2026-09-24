"""#1317: named-context repo registration must run BEFORE the skip guard.

A graph populated by a path that skipped registration (MCP tool, interrupted
run) left config.yaml permanently desynced — every later `cgc index` hit
"already indexed. Skipping." above the registration line, so `cgc context
list` showed "Repos Linked: 0" forever. Hermetic: per-test HOME, embedded db.
"""
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CGC = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


def _env(home: Path):
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DEFAULT_DATABASE"] = "kuzudb"
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env.pop("CGC_CONTEXT_MODE", None)
    return env


def _run(cmd: str, env, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, cwd=cwd)
    return r.stdout + r.stderr


def _config_path(home: Path) -> Path:
    return home / ".codegraphcontext" / "config.yaml"


def _linked_repos(home: Path, ctx_name: str):
    cfg = yaml.safe_load(_config_path(home).read_text()) or {}
    ctx = (cfg.get("contexts") or {}).get(ctx_name) or {}
    return ctx.get("repos") or []


def test_reindex_of_skipped_repo_still_registers_in_context(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    env = _env(home)

    out = _run(f"{CGC} context create proj --database kuzudb", env)
    assert "proj" in out, out
    out = _run(f"{CGC} config set mode named", env)
    out = _run(f"{CGC} context default proj", env)

    # First index: registers and indexes.
    out = _run(f"{CGC} index {shlex.quote(str(repo))} --context proj", env)
    assert "Successfully finished indexing" in out or "already indexed" in out, out
    assert _linked_repos(home, "proj"), "first index did not register the repo"

    # Simulate the desync: graph stays populated, config loses the repo.
    cfg_file = _config_path(home)
    cfg = yaml.safe_load(cfg_file.read_text())
    cfg["contexts"]["proj"]["repos"] = []
    cfg_file.write_text(yaml.safe_dump(cfg))
    assert _linked_repos(home, "proj") == []

    # Second index hits the "already indexed. Skipping." early return —
    # registration must have happened BEFORE it.
    out = _run(f"{CGC} index {shlex.quote(str(repo))} --context proj", env)
    assert "Skipping" in out or "already indexed" in out, out
    assert _linked_repos(home, "proj"), (
        "the skip guard returned before registration — #1317 regressed:\n" + out
    )


def test_default_named_context_registers_without_explicit_flag(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    env = _env(home)

    _run(f"{CGC} context create proj --database kuzudb", env)
    _run(f"{CGC} config set mode named", env)
    _run(f"{CGC} context default proj", env)

    # No --context flag: the resolved default context must still register.
    out = _run(f"{CGC} index {shlex.quote(str(repo))}", env)
    assert _linked_repos(home, "proj"), (
        "indexing under the default named context did not register the repo:\n" + out
    )
