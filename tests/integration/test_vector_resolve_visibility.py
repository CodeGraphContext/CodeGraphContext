"""#1597 end-to-end: an enabled-but-unrunnable vector resolve must be visible.

Uses CGC_EMBEDDING_MODEL=openai with no OPENAI_API_KEY so the probe fails
deterministically regardless of which embedding packages the environment has.
"""
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


def _env(home: Path):
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DEFAULT_DATABASE"] = "ladybugdb"
    env["CGC_CONTEXT_MODE"] = "global"
    env["CGC_EMBEDDING_MODEL"] = "openai"
    env.pop("OPENAI_API_KEY", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return env


def _run(cmd: str, home: Path):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=_env(home))
    return result.stdout + result.stderr


CGC = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


def test_config_set_warns_immediately(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    out = _run(f"{CGC} config set ENABLE_VECTOR_RESOLVE true", home)
    assert "cannot run yet" in out, out


def test_index_summary_shows_embeddings_not_generated(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")

    _run(f"{CGC} config set ENABLE_VECTOR_RESOLVE true", home)
    out = _run(f"{CGC} index {shlex.quote(str(repo))}", home)
    assert "NOT generated" in out, out
    # The run itself must still succeed — the feature is optional.
    assert "Successfully finished indexing" in out, out
