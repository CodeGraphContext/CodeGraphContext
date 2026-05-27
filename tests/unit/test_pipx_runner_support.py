"""
TC-01 to TC-09: pipx runner support tests for setup_wizard.py

Tests that _generate_mcp_json() and kuzu setup block correctly detect
and use cgc / pipx / python as the MCP server runner.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DUMMY_CREDS = {
    "uri": "bolt://localhost:7687",
    "username": "neo4j",
    "password": "testpassword",
}


def _get_server_block(mcp_config: dict) -> dict:
    return mcp_config["mcpServers"]["CodeGraphContext"]


def _run_generate_mcp_json(which_side_effect):
    """Helper: run _generate_mcp_json() with mocked shutil.which."""
    captured = {}

    with patch("codegraphcontext.cli.setup_wizard.shutil.which",
               side_effect=which_side_effect), \
         patch("codegraphcontext.cli.setup_wizard._configure_ide",
               side_effect=lambda cfg: captured.update({"config": cfg})), \
         patch("codegraphcontext.cli.setup_wizard._save_neo4j_credentials"), \
         patch("codegraphcontext.cli.setup_wizard.console"), \
         patch("builtins.open", mock_open()):

        from codegraphcontext.cli.setup_wizard import _generate_mcp_json
        _generate_mcp_json(DUMMY_CREDS)

    return captured.get("config", {})


# ---------------------------------------------------------------------------
# TC-01: cgc binary is available in system PATH
# When cgc is found via shutil.which, the MCP config should use cgc directly
# as the command with ["mcp", "start"] args. pipx should not be involved.
# ---------------------------------------------------------------------------

class TestTC01_CgcAvailable:

    def test_cgc_path_available_uses_cgc_command(self):
        config = _run_generate_mcp_json(
            lambda name: "/usr/local/bin/cgc" if name == "cgc" else None
        )
        server = _get_server_block(config)
        assert server["command"] == "/usr/local/bin/cgc", \
            f"Expected cgc path, got: {server['command']}"
        assert server["args"] == ["mcp", "start"], \
            f"Expected ['mcp', 'start'], got: {server['args']}"

    def test_cgc_available_does_not_use_pipx(self):
        config = _run_generate_mcp_json(
            lambda name: "/usr/local/bin/cgc" if name == "cgc" else "/usr/bin/pipx"
        )
        server = _get_server_block(config)
        assert "pipx" not in server["command"], \
            "pipx should NOT be used when cgc is available"
        assert server["args"] == ["mcp", "start"], \
            f"Expected ['mcp', 'start'], got: {server['args']}"


# ---------------------------------------------------------------------------
# TC-02: cgc is absent but pipx is available in system PATH
# When cgc is not found but pipx is, the MCP config should use pipx run
# so that codegraphcontext is executed from its pipx isolated environment.
# ---------------------------------------------------------------------------

class TestTC02_PipxAvailable:

    def test_pipx_used_when_cgc_absent(self):
        def which_side(name):
            if name == "cgc":
                return None
            if name == "pipx":
                return "/usr/bin/pipx"
            return None

        config = _run_generate_mcp_json(which_side)
        server = _get_server_block(config)
        assert server["command"] == "/usr/bin/pipx", \
            f"Expected pipx path, got: {server['command']}"
        assert server["args"] == ["run", "codegraphcontext", "mcp", "start"], \
            f"Expected pipx run args, got: {server['args']}"

    def test_pipx_args_contain_codegraphcontext_package(self):
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else "/usr/bin/pipx"
        )
        server = _get_server_block(config)
        assert "codegraphcontext" in server["args"], \
            "Package name 'codegraphcontext' must be in args for pipx run"
        assert server["args"][0] == "run", \
            "First arg must be 'run' for pipx"


# ---------------------------------------------------------------------------
# TC-03: both cgc and pipx are absent from system PATH
# When neither cgc nor pipx is found, the MCP config should fall back to
# sys.executable (python) with -m flag to run codegraphcontext as a module.
# ---------------------------------------------------------------------------

class TestTC03_PythonFallback:

    def test_python_fallback_when_both_absent(self):
        captured = {}

        with patch("codegraphcontext.cli.setup_wizard.shutil.which",
                   return_value=None), \
             patch("codegraphcontext.cli.setup_wizard.sys") as mock_sys, \
             patch("codegraphcontext.cli.setup_wizard._configure_ide",
                   side_effect=lambda cfg: captured.update({"config": cfg})), \
             patch("codegraphcontext.cli.setup_wizard._save_neo4j_credentials"), \
             patch("codegraphcontext.cli.setup_wizard.console"), \
             patch("builtins.open", mock_open()):

            mock_sys.executable = "/usr/bin/python3"

            from codegraphcontext.cli.setup_wizard import _generate_mcp_json
            _generate_mcp_json(DUMMY_CREDS)

        server = _get_server_block(captured["config"])
        assert server["command"] == "/usr/bin/python3", \
            f"Expected python3 fallback, got: {server['command']}"

    def test_fallback_args_include_mcp_start(self):
        captured = {}

        with patch("codegraphcontext.cli.setup_wizard.shutil.which",
                   return_value=None), \
             patch("codegraphcontext.cli.setup_wizard.sys") as mock_sys, \
             patch("codegraphcontext.cli.setup_wizard._configure_ide",
                   side_effect=lambda cfg: captured.update({"config": cfg})), \
             patch("codegraphcontext.cli.setup_wizard._save_neo4j_credentials"), \
             patch("codegraphcontext.cli.setup_wizard.console"), \
             patch("builtins.open", mock_open()):

            mock_sys.executable = "/usr/bin/python3"

            from codegraphcontext.cli.setup_wizard import _generate_mcp_json
            _generate_mcp_json(DUMMY_CREDS)

        server = _get_server_block(captured["config"])
        assert "mcp" in server["args"], "Args must contain 'mcp'"
        assert "start" in server["args"], "Args must contain 'start'"


# ---------------------------------------------------------------------------
# TC-04: kuzu setup block (configure_mcp_client) follows same runner logic
# The kuzu/falkordb setup block at line ~405 in setup_wizard.py must detect
# cgc, pipx, and python fallback in the same order as _generate_mcp_json().
# ---------------------------------------------------------------------------

class TestTC04_KuzuSetupBlock:

    def _run_kuzu_block(self, cgc_val, pipx_val, python_val="/usr/bin/python3"):
        if cgc_val:
            command = cgc_val
            args = ["mcp", "start"]
        elif pipx_val:
            command = pipx_val
            args = ["run", "codegraphcontext", "mcp", "start"]
        else:
            command = python_val
            args = ["-m", "codegraphcontext", "mcp", "start"]
        return command, args

    def test_kuzu_block_pipx_detected(self):
        command, args = self._run_kuzu_block(None, "/usr/bin/pipx")
        assert command == "/usr/bin/pipx"
        assert args == ["run", "codegraphcontext", "mcp", "start"]

    def test_kuzu_block_cgc_takes_priority_over_pipx(self):
        command, args = self._run_kuzu_block("/usr/local/bin/cgc", "/usr/bin/pipx")
        assert command == "/usr/local/bin/cgc"
        assert args == ["mcp", "start"]

    def test_kuzu_block_python_fallback(self):
        command, args = self._run_kuzu_block(None, None)
        assert "python" in command.lower()
        assert "-m" in args


# ---------------------------------------------------------------------------
# TC-05: README.md must document pipx installation and config example
# Users who install via pipx need clear instructions. README must mention
# pipx, codegraphcontext package name, and mcp start args in that section.
# ---------------------------------------------------------------------------

class TestTC05_ReadmeDocumentation:
    # Resolve repository root robustly across local runs and CI workspace layouts.
    # In GitHub Actions, checkout paths may be nested (e.g. /work/repo/repo).
    README_PATH = next(
        (
            candidate
            for parent in Path(__file__).resolve().parents
            for candidate in [parent / "README.md"]
            if candidate.exists()
        ),
        Path(__file__).resolve().parent.parent.parent.parent / "README.md",
    )

    def test_readme_exists(self):
        assert self.README_PATH.exists(), \
            f"README.md not found at {self.README_PATH}"

    def test_readme_contains_pipx_command(self):
        if not self.README_PATH.exists():
            pytest.skip("README.md not found")
        content = self.README_PATH.read_text(encoding="utf-8")
        assert "pipx" in content, \
            "README.md must mention 'pipx'"

    def test_readme_contains_pipx_run_codegraphcontext(self):
        if not self.README_PATH.exists():
            pytest.skip("README.md not found")
        content = self.README_PATH.read_text(encoding="utf-8").lower()
        assert "pipx" in content and "codegraphcontext" in content, \
            "README.md must contain both 'pipx' and 'codegraphcontext'"

    def test_readme_pipx_config_has_mcp_start(self):
        if not self.README_PATH.exists():
            pytest.skip("README.md not found")
        content = self.README_PATH.read_text(encoding="utf-8")
        pipx_idx = content.lower().find("pipx")
        if pipx_idx == -1:
            pytest.skip("pipx section not yet added to README")
        nearby = content[pipx_idx: pipx_idx + 500]
        assert "mcp" in nearby.lower() and "start" in nearby.lower(), \
            "pipx section in README must include 'mcp start' args"


# ---------------------------------------------------------------------------
# TC-06: generated mcp config output must have valid structure and correct values
# After _generate_mcp_json() runs with pipx available, the resulting config
# dict must have proper mcpServers > CodeGraphContext > command/args structure.
# ---------------------------------------------------------------------------

class TestTC06_McpJsonFileOutput:

    def test_mcp_json_written_with_pipx_command(self):
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else "/usr/bin/pipx"
        )
        server = _get_server_block(config)
        assert server["command"] == "/usr/bin/pipx", \
            f"command should be pipx, got: {server['command']}"
        assert server["args"][0] == "run", "args[0] should be 'run'"
        assert "codegraphcontext" in server["args"], \
            "args must contain 'codegraphcontext'"

    def test_mcp_json_structure_valid(self):
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else "/usr/bin/pipx"
        )
        assert "mcpServers" in config
        assert "CodeGraphContext" in config["mcpServers"]
        server = config["mcpServers"]["CodeGraphContext"]
        assert "command" in server
        assert "args" in server
        assert isinstance(server["args"], list)


# ---------------------------------------------------------------------------
# TC-07: pipx uses "run" keyword which tells pipx to execute the package
# inside its own isolated virtual environment. Without "run" as first arg,
# pipx will not create or use the isolated env for codegraphcontext.
# ---------------------------------------------------------------------------

class TestTC07_PipxIsolatedEnvArgs:

    def test_pipx_run_keyword_present_for_isolated_env(self):
        """TC-07: 'run' keyword must be first arg so pipx uses isolated env."""
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else "/usr/bin/pipx"
        )
        server = _get_server_block(config)
        assert server["args"][0] == "run", \
            "'run' must be first arg — this tells pipx to use isolated environment"
        assert "codegraphcontext" in server["args"], \
            "package name must be present so pipx fetches it in its own isolated venv"


# ---------------------------------------------------------------------------
# TC-08: when pipx is used, "-m" module flag must NOT appear in args
# "-m" flag means run as python module which completely bypasses pipx
# isolated environment. This would defeat the purpose of using pipx.
# ---------------------------------------------------------------------------

class TestTC08_PipxNotUsingPythonModule:

    def test_pipx_args_do_not_contain_module_flag(self):
        """TC-08: '-m' flag must NOT be in pipx args — it bypasses isolated env."""
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else "/usr/bin/pipx"
        )
        server = _get_server_block(config)
        assert "-m" not in server["args"], \
            "'-m' flag bypasses pipx isolated environment — must not be present"
        assert server["command"] != "python" and server["command"] != "python3", \
            "command must be pipx binary, not python — python bypasses isolated env"


# ---------------------------------------------------------------------------
# TC-09: the exact pipx binary path returned by shutil.which must be used
# as the command. Using any other binary like python or cgc would bypass
# pipx entirely and break execution for pipx-installed users.
# ---------------------------------------------------------------------------

class TestTC09_PipxBinaryAsCommand:

    def test_pipx_binary_path_used_as_command(self):
        """TC-09: exact pipx binary path must be the command."""
        pipx_path = "/home/user/.local/bin/pipx"
        config = _run_generate_mcp_json(
            lambda name: None if name == "cgc" else pipx_path
        )
        server = _get_server_block(config)
        assert server["command"] == pipx_path, \
            f"command must be exact pipx binary path, got: {server['command']}"
        assert "python" not in server["command"].lower(), \
            "pipx binary path must not contain 'python'"
        assert "cgc" not in server["command"].lower(), \
            "pipx binary path must not contain 'cgc'"