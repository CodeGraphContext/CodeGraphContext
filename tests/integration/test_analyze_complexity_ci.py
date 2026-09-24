"""#1333: `cgc analyze complexity` as a CI quality gate.

Machine-readable output on a clean stdout, and an opt-in non-zero exit code.
Hermetic: per-test HOME, embedded backend.
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

CGC = f"{shlex.quote(sys.executable)} -m codegraphcontext.cli.main"


@pytest.fixture()
def indexed_repo(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    repo = tmp_path / "repo"; repo.mkdir()
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
    # Under runner load a failed index used to surface later as a cryptic
    # csv-shape assertion in whichever test ran first; fail HERE with the
    # index output so the cause is visible.
    assert "Successfully finished indexing" in (r.stdout + r.stderr), (
        f"fixture index failed (rc={r.returncode}):\n{r.stdout}\n{r.stderr}"
    )
    return env


def _run(cmd: str, env):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)


def test_json_output_is_pure_and_parseable(indexed_repo):
    r = _run(f"{CGC} analyze complexity --threshold 2 --format json", indexed_repo)
    doc = json.loads(r.stdout)  # would raise if init chatter leaked to stdout
    assert doc["threshold"] == 2
    assert doc["violations_count"] >= 1
    names = {v["function"] for v in doc["violations"]}
    assert "busy" in names and "calm" not in names and "<module>" not in names
    for v in doc["violations"]:
        assert v["exceeds_by"] == v["complexity"] - 2
    assert r.returncode == 0  # informational without the gate flag


def test_csv_output_has_header_and_rows(indexed_repo):
    r = _run(f"{CGC} analyze complexity --threshold 2 --format csv", indexed_repo)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert lines and lines[0] == "function,file,line,complexity,exceeds_by", (
        f"unexpected csv stdout (rc={r.returncode}):\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    )
    assert any(l.startswith("busy,") for l in lines[1:]), r.stdout


def test_fail_on_violations_gates_the_exit_code(indexed_repo):
    r = _run(f"{CGC} analyze complexity --threshold 2 --fail-on-violations --format json", indexed_repo)
    assert r.returncode == 1, r.stdout + r.stderr
    # A threshold nothing exceeds must pass the gate.
    r2 = _run(f"{CGC} analyze complexity --threshold 99 --fail-on-violations --format json", indexed_repo)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert json.loads(r2.stdout)["violations_count"] == 0


def test_unknown_format_is_rejected(indexed_repo):
    r = _run(f"{CGC} analyze complexity --format yaml", indexed_repo)
    assert r.returncode == 2
