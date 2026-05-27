import json
import os
from pathlib import Path

from codegraphcontext.cli import config_manager
from codegraphcontext.cli import setup_wizard


def test_normalize_config_path_expands_home_and_makes_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    normalized = config_manager.normalize_config_path("~/.codegraphcontext/global/db/falkordb", absolute=True)
    assert normalized == str((tmp_path / ".codegraphcontext" / "global" / "db" / "falkordb").resolve())


def test_validate_config_value_accepts_tilde_path_without_relative_tilde_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    ok, err = config_manager.validate_config_value("FALKORDB_PATH", "~/.codegraphcontext/global/db/falkordb")
    assert ok, err
    assert not (tmp_path / "~").exists()


def test_configure_mcp_client_writes_expanded_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    fake_config = {
        "FALKORDB_PATH": "~/.codegraphcontext/global/db/falkordb",
        "FALKORDB_SOCKET_PATH": "~/.codegraphcontext/global/db/falkordb.sock",
        "DEBUG_LOG_PATH": "~/mcp_debug.log",
        "LOG_FILE_PATH": "~/.codegraphcontext/logs/cgc.log",
    }

    monkeypatch.setattr(config_manager, "load_config", lambda: fake_config)
    monkeypatch.setattr(setup_wizard, "_configure_ide", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_wizard.shutil, "which", lambda name: "/usr/local/bin/cgc" if name == "cgc" else None)

    setup_wizard.configure_mcp_client()

    mcp_json = tmp_path / "mcp.json"
    assert mcp_json.exists()
    data = json.loads(mcp_json.read_text(encoding="utf-8"))
    env = data["mcpServers"]["CodeGraphContext"]["env"]

    assert env["FALKORDB_PATH"] == str((tmp_path / ".codegraphcontext" / "global" / "db" / "falkordb").resolve())
    assert env["FALKORDB_SOCKET_PATH"] == str((tmp_path / ".codegraphcontext" / "global" / "db" / "falkordb.sock").resolve())
    assert env["DEBUG_LOG_PATH"] == str((tmp_path / "mcp_debug.log").resolve())
    assert env["LOG_FILE_PATH"] == str((tmp_path / ".codegraphcontext" / "logs" / "cgc.log").resolve())
