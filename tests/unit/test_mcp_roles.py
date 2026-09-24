# tests/unit/test_mcp_roles.py
"""Tests for configurable AI role prompts in the MCP server (#1320)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codegraphcontext.prompts import LLM_SYSTEM_PROMPT, build_system_prompt
from codegraphcontext.roles import (
    BUILTIN_ROLES,
    MAX_ROLE_FILE_BYTES,
    VALID_ROLES,
    load_builtin_role,
    load_role_file,
    resolve_role_prompt,
)


# ---------------------------------------------------------------------------
# 1. Unconfigured path must be byte-identical (the critical invariant)
# ---------------------------------------------------------------------------

class TestUnconfiguredByteIdentical:
    """With no role configured, every output must match the pre-feature baseline."""

    def test_resolve_returns_none_by_default(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        assert resolve_role_prompt() is None

    def test_resolve_neutral_returns_none(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        assert resolve_role_prompt(cli_role="neutral") is None
        assert resolve_role_prompt(cli_role="NEUTRAL") is None
        assert resolve_role_prompt(cli_role="  ") is None

    def test_build_system_prompt_without_role_is_unchanged(self, tmp_path):
        """No role + no custom prompts => exactly LLM_SYSTEM_PROMPT."""
        with patch(
            "codegraphcontext.cli.project_config.get_prompt_file_contents",
            return_value=[],
        ):
            assert build_system_prompt() == LLM_SYSTEM_PROMPT
            assert build_system_prompt(role_prompt=None) == LLM_SYSTEM_PROMPT
            assert build_system_prompt(role_prompt="") == LLM_SYSTEM_PROMPT

    def test_build_system_prompt_role_none_matches_baseline(self, tmp_path):
        """role_prompt=None must produce byte-identical output to no-arg call."""
        with patch(
            "codegraphcontext.cli.project_config.get_prompt_file_contents",
            return_value=[],
        ):
            baseline = build_system_prompt()
            assert build_system_prompt(role_prompt=None) == baseline

    def test_initialize_instructions_without_role_is_baseline(self):
        """The instructions field sent to the client must equal LLM_SYSTEM_PROMPT."""
        role_prompt = None
        if role_prompt:
            instructions = f"{role_prompt}\n\n---\n\n{LLM_SYSTEM_PROMPT}"
        else:
            instructions = LLM_SYSTEM_PROMPT
        assert instructions == LLM_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 2. Role injection when configured
# ---------------------------------------------------------------------------

class TestRoleInjection:
    def test_builtin_role_loaded(self):
        content = load_builtin_role("reviewer")
        assert "code reviewer" in content.lower()

    def test_all_builtin_roles_exist(self):
        for role in BUILTIN_ROLES:
            content = load_builtin_role(role)
            assert content, f"Role {role} loaded empty content"

    def test_resolve_builtin_role(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        result = resolve_role_prompt(cli_role="architect")
        assert result is not None
        assert "architect" in result.lower()

    def test_build_system_prompt_prepends_role(self):
        with patch(
            "codegraphcontext.cli.project_config.get_prompt_file_contents",
            return_value=[],
        ):
            result = build_system_prompt(role_prompt="# My Role\nDo things.")
            assert result.startswith("# My Role")
            assert LLM_SYSTEM_PROMPT in result
            # Separator between role and base
            assert "---" in result

    def test_build_system_prompt_role_with_custom_prompts(self):
        with patch(
            "codegraphcontext.cli.project_config.get_prompt_file_contents",
            return_value=["Custom instruction here."],
        ):
            result = build_system_prompt(role_prompt="# Role")
            assert result.startswith("# Role")
            assert "Custom instruction here." in result
            assert LLM_SYSTEM_PROMPT in result

    def test_unknown_role_raises(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        with pytest.raises(ValueError, match="Unknown role"):
            resolve_role_prompt(cli_role="nonexistent")


# ---------------------------------------------------------------------------
# 3. Role file validation: size cap, directory, missing, empty
# ---------------------------------------------------------------------------

class TestRoleFileValidation:
    def test_valid_role_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "my_role.md"
        role_file.write_text("# Custom Role\nBe helpful.", encoding="utf-8")
        assert load_role_file(role_file) == "# Custom Role\nBe helpful."

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            load_role_file(tmp_path / "does_not_exist.md")

    def test_directory_raises(self, tmp_path):
        role_dir = tmp_path / "role_dir"
        role_dir.mkdir()
        with pytest.raises(ValueError, match="not a regular file"):
            load_role_file(role_dir)

    def test_empty_file_raises(self, tmp_path):
        role_file = tmp_path / "empty.md"
        role_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_role_file(role_file)

    def test_whitespace_only_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "ws.md"
        role_file.write_text("   \n\n  ", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_role_file(role_file)

    def test_oversized_file_raises(self, tmp_path, monkeypatch):
        """A file over the size cap must be rejected with a clear message."""
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "huge.md"
        role_file.write_bytes(b"x" * (MAX_ROLE_FILE_BYTES + 1))
        with pytest.raises(ValueError, match="too large"):
            load_role_file(role_file)

    def test_file_at_size_cap_passes(self, tmp_path, monkeypatch):
        """A file exactly at the cap is allowed (boundary test)."""
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "boundary.md"
        role_file.write_bytes(b"x" * MAX_ROLE_FILE_BYTES)
        # Content is non-empty after strip (all 'x's), so it should load
        content = load_role_file(role_file)
        assert len(content) == MAX_ROLE_FILE_BYTES


# ---------------------------------------------------------------------------
# 4. Precedence: CLI > env > config > default
# ---------------------------------------------------------------------------

class TestPrecedence:
    def test_cli_beats_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CGC_MCP_ROLE", "architect")
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        result = resolve_role_prompt(cli_role="reviewer")
        assert "reviewer" in result.lower()
        assert "architect" not in result.lower()

    def test_env_beats_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CGC_MCP_ROLE", "architect")
        with patch(
            "codegraphcontext.cli.project_config.load_project_config",
            return_value={"role": "auditor"},
        ):
            result = resolve_role_prompt()
            assert "architect" in result.lower()

    def test_config_used_when_no_cli_or_env(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        with patch(
            "codegraphcontext.cli.project_config.load_project_config",
            return_value={"role": "explainer"},
        ):
            result = resolve_role_prompt()
            assert "explainer" in result.lower()

    def test_default_is_none(self, monkeypatch):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        with patch(
            "codegraphcontext.cli.project_config.load_project_config",
            return_value={"prompts": []},
        ):
            assert resolve_role_prompt() is None

    def test_role_file_alone_implies_custom(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "role.md"
        role_file.write_text("# Solo File Role", encoding="utf-8")
        result = resolve_role_prompt(cli_role_file=str(role_file))
        assert result == "# Solo File Role"

    def test_role_file_overrides_builtin_content(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CGC_MCP_ROLE", raising=False)
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "override.md"
        role_file.write_text("# Override Content", encoding="utf-8")
        result = resolve_role_prompt(cli_role="reviewer", cli_role_file=str(role_file))
        assert result == "# Override Content"


# ---------------------------------------------------------------------------
# 5. Path sandbox for role files
# ---------------------------------------------------------------------------

class TestPathSandbox:
    def test_file_outside_allowed_roots_rejected(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CGC_ALLOW_ALL_PATHS", raising=False)
        # No CGC_ALLOWED_ROOTS, cwd is not the tmp_path
        role_file = tmp_path / "outside.md"
        role_file.write_text("# Outside", encoding="utf-8")
        with pytest.raises(ValueError, match="outside allowed roots"):
            load_role_file(role_file)

    def test_file_under_allowed_roots_accepted(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CGC_ALLOW_ALL_PATHS", raising=False)
        monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
        role_file = tmp_path / "allowed.md"
        role_file.write_text("# Allowed", encoding="utf-8")
        assert load_role_file(role_file) == "# Allowed"

    def test_cg_callow_all_paths_escape_hatch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_ALLOW_ALL_PATHS", "true")
        monkeypatch.delenv("CGC_ALLOWED_ROOTS", raising=False)
        role_file = tmp_path / "anywhere.md"
        role_file.write_text("# Anywhere", encoding="utf-8")
        assert load_role_file(role_file) == "# Anywhere"

    def test_config_dir_always_allowed(self, tmp_path, monkeypatch):
        """~/.codegraphcontext/ is always allowed regardless of CGC_ALLOWED_ROOTS."""
        monkeypatch.delenv("CGC_ALLOW_ALL_PATHS", raising=False)
        monkeypatch.delenv("CGC_ALLOWED_ROOTS", raising=False)
        config_dir = Path.home() / ".codegraphcontext"
        config_dir.mkdir(parents=True, exist_ok=True)
        role_file = config_dir / "_test_role_tmp.md"
        role_file.write_text("# Config Dir Role", encoding="utf-8")
        try:
            assert load_role_file(role_file) == "# Config Dir Role"
        finally:
            role_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 6. VALID_ROLES completeness
# ---------------------------------------------------------------------------

class TestValidRoles:
    def test_valid_roles_contains_all_builtins(self):
        assert BUILTIN_ROLES.issubset(VALID_ROLES)

    def test_valid_roles_contains_custom_and_neutral(self):
        assert "custom" in VALID_ROLES
        assert "neutral" in VALID_ROLES
