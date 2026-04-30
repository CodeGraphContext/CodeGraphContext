from pathlib import Path

from codegraphcontext.cli.setup_wizard import _build_mcp_env


def test_build_mcp_env_only_keeps_allowlisted_keys():
    config = {
        "DEFAULT_DATABASE": "neo4j",
        "FALKORDB_PATH": "./.codegraphcontext/db",
        "GITHUB_TOKEN": "secret-token",
        "UNRELATED_SETTING": "should-not-pass",
    }

    env = _build_mcp_env(config)

    assert env["DEFAULT_DATABASE"] == "neo4j"
    assert Path(env["FALKORDB_PATH"]).is_absolute()
    assert "GITHUB_TOKEN" not in env
    assert "UNRELATED_SETTING" not in env
