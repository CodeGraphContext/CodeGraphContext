"""Text-mode `cgc analyze` must print its product on stdout.

The stderr console in `cli/main.py` is right for prompts and diagnostics, but it
also carried every `analyze` result table, so `cgc analyze callers f > out.txt`
captured only the init chatter. `cgc stats` (via the `cli_helpers` console) and
`cgc diagram` already put their product on stdout; this locks `analyze` to the
same contract, and keeps argument-validation errors off stdout.
"""
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

CGC = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


@pytest.fixture()
def indexed_repo(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def busy(x):\n"
        "    if x > 0:\n"
        "        if x > 1:\n"
        "            if x > 2:\n"
        "                return 3\n"
        "            return 2\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "def calm():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["DEFAULT_DATABASE"] = "kuzudb"
    env["CGC_CONTEXT_MODE"] = "global"
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    r = subprocess.run(f"{CGC} index {shlex.quote(str(repo))}", shell=True,
                       capture_output=True, text=True, env=env, check=False)
    assert "Successfully finished indexing" in (r.stdout + r.stderr), (
        f"fixture index failed (rc={r.returncode}):\n{r.stdout}\n{r.stderr}"
    )
    return env


def _run(args: str, env):
    return subprocess.run(f"{CGC} {args}", shell=True, capture_output=True,
                          text=True, env=env)


def test_complexity_table_lands_on_stdout(indexed_repo):
    r = _run("analyze complexity --threshold 2", indexed_repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "busy" in r.stdout, (
        f"result table missing from stdout:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )
    assert "exceed threshold" in r.stdout   # the footer is part of the product
    assert "Using database" in r.stderr


def test_empty_result_notice_is_on_stdout(indexed_repo):
    r = _run("analyze callers nothing_calls_this", indexed_repo)
    assert "No callers found" in r.stdout, (
        f"an empty result is still a result:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )


def test_machine_format_still_isolates_chatter(indexed_repo):
    # #1650/#1655: with --format json, stdout must be pure enough to parse.
    r = _run("analyze complexity --threshold 2 --format json", indexed_repo)
    assert r.stdout.lstrip().startswith("{"), (
        f"init chatter leaked into machine stdout:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )


def test_argument_error_stays_on_stderr(indexed_repo):
    r = _run("analyze complexity --format yaml", indexed_repo)
    assert r.returncode == 2
    assert "Unknown --format" in r.stderr
    assert "Unknown --format" not in r.stdout, (
        "validation errors must not pollute the product stream"
    )
