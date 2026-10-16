"""End-to-end `cgc snapshot save|list` and `cgc diff` (#1312).

Two contracts are under test here, not one: the diff has to be right, and it
has to arrive on the right stream. The product (diff rows, `--json` documents)
belongs on stdout so `cgc diff --json > changes.json` yields a parseable file;
the init chatter belongs on stderr; and the exit codes must tell "there are
differences" (1, only when `--fail-on-changes` was asked for) apart from "you
typed it wrong" (2).

Subprocesses are launched with an argument list — no shell — so this file runs
on Windows as well as POSIX.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

V1 = (
    "def process_payment(amount, card):\n"
    "    return validate_card(card) and amount > 0\n"
    "\n"
    "\n"
    "def validate_card(card):\n"
    "    return len(card) == 16\n"
    "\n"
    "\n"
    "def legacy_checkout(amount):\n"
    "    return amount > 0\n"
)

SUPPORT = (
    "def checksum(payload):\n"
    "    return sum(ord(c) for c in payload)\n"
)

# One import added, one function removed, one added, one body edited, and every
# surviving definition shifted down by the edits above them.
V2 = (
    "from support import checksum\n"
    "\n"
    "\n"
    "def process_payment(amount, card):\n"
    "    return validate_card(card) and amount > 0 and checksum(card) > 0\n"
    "\n"
    "\n"
    "def validate_card(card):\n"
    "    return len(card) == 16\n"
    "\n"
    "\n"
    "def refund(amount):\n"
    "    return amount > 0\n"
)


def _run(env, args):
    return subprocess.run(
        [sys.executable, "-m", "codegraphcontext.cli.main", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _assert_ok(result, args):
    assert result.returncode == 0, (
        f"cgc {' '.join(args)} failed (rc={result.returncode})\n"
        f"STDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    )


@pytest.fixture(scope="module")
def snapshot_env(tmp_path_factory):
    """A repository indexed, snapshotted, edited, re-indexed and snapshotted."""
    tmp = tmp_path_factory.mktemp("snapshot-diff")
    home = tmp / "home"
    home.mkdir()
    cache = tmp / "ts-cache"
    cache.mkdir()
    repo = tmp / "repo"
    repo.mkdir()
    (repo / "support.py").write_text(SUPPORT, encoding="utf-8")
    (repo / "checkout.py").write_text(V1, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "DEFAULT_DATABASE": "kuzudb",
            "CGC_CONTEXT_MODE": "global",
            "PYTHONUTF8": "1",
            "PYTHONPATH": os.pathsep.join(sys.path),
            # Without an explicit cache dir the tree-sitter language pack has
            # nowhere to download into once HOME is redirected, and indexing
            # silently falls back to a parser this tree-sitter cannot load.
            "TREE_SITTER_LANGUAGE_PACK_CACHE_DIR": str(cache),
        }
    )

    _assert_ok(_run(env, ["index", str(repo)]), ["index"])
    _assert_ok(_run(env, ["snapshot", "save", "--name", "base"]), ["snapshot", "save"])

    (repo / "checkout.py").write_text(V2, encoding="utf-8")
    _assert_ok(_run(env, ["index", str(repo), "--force"]), ["index", "--force"])
    # The state the working copy is in now, so one test can assert "no changes".
    _assert_ok(_run(env, ["snapshot", "save", "--name", "current"]), ["snapshot", "save"])
    return env


def test_diff_product_is_on_stdout_and_chatter_is_on_stderr(snapshot_env):
    args = ["diff", "--against", "base"]
    result = _run(snapshot_env, args)
    _assert_ok(result, args)

    assert "refund" in result.stdout and "(new)" in result.stdout
    assert "legacy_checkout" in result.stdout and "(removed)" in result.stdout
    assert result.stdout.isascii(), "non-ASCII output breaks on a cp1252 console"
    assert "Initializing services" in result.stderr
    assert "Initializing services" not in result.stdout


def test_line_shifts_do_not_read_as_churn(snapshot_env):
    """Every surviving definition moved down, but none of them was rewritten."""
    result = _run(snapshot_env, ["diff", "--against", "base", "--json"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.lstrip().startswith("{"), (
        f"init chatter leaked into machine stdout:\nSTDOUT:{result.stdout}"
    )

    document = json.loads(result.stdout)
    assert document["format"] == "cgc-diff"
    assert document["format_version"] == 1

    added = {node["display"] for node in document["nodes"]["added"]}
    removed = {node["display"] for node in document["nodes"]["removed"]}
    assert "refund" in added
    assert "legacy_checkout" in removed
    # validate_card only shifted by the import line added above it.
    assert "validate_card" not in added and "validate_card" not in removed
    moved = [entry for entry in document["nodes"]["changed"] if entry["reason"] == "moved"]
    assert moved, "a re-keyed node should be reported as a move, not as churn"


def test_diff_summary_and_exit_codes(snapshot_env):
    changed = _run(snapshot_env, ["diff", "--against", "base", "--fail-on-changes"])
    assert changed.returncode == 1, changed.stdout + changed.stderr

    identical = _run(snapshot_env, ["diff", "--against", "current", "--fail-on-changes"])
    assert identical.returncode == 0, identical.stdout + identical.stderr
    assert "no changes" in identical.stdout


def test_unknown_snapshot_fails_on_stderr_with_exit_1(snapshot_env):
    result = _run(snapshot_env, ["diff", "--against", "no-such-snapshot"])

    assert result.returncode == 1
    assert "no-such-snapshot" in result.stderr
    assert "no-such-snapshot" not in result.stdout, "errors must stay off the product stream"


def test_bad_snapshot_name_is_a_usage_error(snapshot_env):
    result = _run(snapshot_env, ["diff", "--against", "has spaces"])

    assert result.returncode == 2, result.stdout + result.stderr
    assert "Invalid snapshot name" in result.stderr
    assert "Invalid snapshot name" not in result.stdout


def test_snapshot_list_reports_both_snapshots(snapshot_env):
    result = _run(snapshot_env, ["snapshot", "list", "--json"])
    _assert_ok(result, ["snapshot", "list", "--json"])
    assert result.stdout.lstrip().startswith("{")

    names = {entry["name"] for entry in json.loads(result.stdout)["snapshots"]}
    assert {"base", "current"} <= names


def test_snapshot_save_json_receipt_is_machine_readable(snapshot_env):
    args = ["snapshot", "save", "--name", "receipt", "--json"]
    result = _run(snapshot_env, args)
    _assert_ok(result, args)

    receipt = json.loads(result.stdout)
    assert receipt["format"] == "cgc-snapshot-save"
    assert receipt["name"] == "receipt"
    assert receipt["counts"]["nodes"] > 0
    assert Path(receipt["path"]).name == "receipt.json"


def test_snapshot_save_refuses_to_overwrite_without_force(snapshot_env):
    again = _run(snapshot_env, ["snapshot", "save", "--name", "receipt"])
    assert again.returncode == 1
    assert "--force" in again.stderr
    assert "--force" not in again.stdout

    forced = _run(snapshot_env, ["snapshot", "save", "--name", "receipt", "--force"])
    _assert_ok(forced, ["snapshot", "save", "--force"])
