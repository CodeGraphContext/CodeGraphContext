"""#1287: cgc diagram exports Mermaid/DOT on a clean stdout. Hermetic."""
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

CGC = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


@pytest.fixture()
def indexed(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "app.py").write_text(
        "import os\nfrom pathlib import Path\n\ndef top():\n    helper()\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"HOME": str(home), "DEFAULT_DATABASE": "kuzudb",
                "CGC_CONTEXT_MODE": "global",
                "PYTHONPATH": os.pathsep.join(sys.path)})
    subprocess.run(f"{CGC} index {shlex.quote(str(repo))}", shell=True,
                   capture_output=True, text=True, env=env)
    return env, repo


def _run(cmd, env):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)


def test_mermaid_file_level(indexed):
    env, repo = indexed
    r = _run(f"{CGC} diagram {shlex.quote(str(repo))}", env)
    assert r.stdout.startswith("graph LR"), r.stdout + r.stderr
    assert '--> ' in r.stdout and '"os"' in r.stdout and '"pathlib"' in r.stdout
    # stdout is pure diagram — no init chatter
    assert "Initializing" not in r.stdout


def test_dot_call_level_and_output_file(indexed, tmp_path):
    env, repo = indexed
    out = tmp_path / "g.dot"
    r = _run(f"{CGC} diagram {shlex.quote(str(repo))} --format dot --level call -o {shlex.quote(str(out))}", env)
    assert r.returncode == 0, r.stdout + r.stderr
    text = out.read_text()
    assert text.startswith("digraph cgc {") and text.rstrip().endswith("}")
    assert 'label="top"' in text and 'label="helper"' in text


def test_truncation_is_reported(indexed):
    env, repo = indexed
    r = _run(f"{CGC} diagram {shlex.quote(str(repo))} --limit 1", env)
    assert "truncated: showing 1 of" in r.stdout


def test_bad_format_rejected(indexed):
    env, repo = indexed
    r = _run(f"{CGC} diagram {shlex.quote(str(repo))} --format png", env)
    assert r.returncode == 2
