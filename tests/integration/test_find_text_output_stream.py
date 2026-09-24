"""Text-mode `cgc find` must print its product on stdout.

`analyze` was moved to a stdout console, but the seven `find` subcommands still
carry their result tables on the stderr console, so `cgc find name busy > out.txt`
captures the init chatter and loses the matches. This locks `find` to the same
contract as `analyze`, `stats` and `diagram`, and keeps environment diagnostics
and argument-validation errors off stdout.
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
        "MAX_LIMIT = 10\n"
        "\n"
        "def route(path):\n"
        "    return path\n"
        "\n"
        "@route\n"
        "def busy(x, limit=MAX_LIMIT):\n"
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


# Header fragments stay free of result counts so the assertions do not track
# how many rows the indexer happens to emit.
@pytest.mark.parametrize("cmd,header", [
    ("find name busy", "matches for 'busy':"),
    ("find pattern busy", "matches for pattern 'busy':"),
    ("find type function", "functions:"),
    ("find variable MAX_LIMIT", "variable(s) named 'MAX_LIMIT':"),
    ("find content busy", "content match(es) for 'busy':"),
    ("find argument x", "with argument 'x':"),
])
def test_result_table_is_on_stdout_and_not_on_stderr(indexed_repo, cmd, header):
    r = _run(cmd, indexed_repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert header in r.stdout, (
        f"result header missing from stdout:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )
    assert "Location" in r.stdout, f"table body missing from stdout:\nSTDOUT:{r.stdout}"
    assert header not in r.stderr, f"result header duplicated onto stderr:\n{r.stderr}"


@pytest.mark.parametrize("cmd,notice", [
    ("find name nothing_here", "No code elements found with name 'nothing_here'"),
    ("find decorator route", "No functions found with decorator '@route'"),
])
def test_empty_result_notice_is_on_stdout(indexed_repo, cmd, notice):
    r = _run(cmd, indexed_repo)
    assert notice in r.stdout, (
        f"an empty result is still a result:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )
    assert notice not in r.stderr


def test_argument_error_stays_on_stderr(indexed_repo):
    r = _run("find name busy --type bogus", indexed_repo)
    assert r.returncode == 1
    assert "Invalid --type 'bogus'" in r.stderr
    assert "Invalid --type" not in r.stdout, "an argument error is not a result"
