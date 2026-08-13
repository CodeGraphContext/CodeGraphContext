"""Tests for default LLM model fallbacks and resolve_model_name (issue #1103)

"""

from codegraphcontext.cli.config_manager import DEFAULT_CONFIG, resolve_model_name


class TestModelDefaults:
    def test_openai_model_key_exists_in_defaults(self):
        assert "OPENAI_MODEL" in DEFAULT_CONFIG

    def test_openai_model_default_value(self):
        assert DEFAULT_CONFIG["OPENAI_MODEL"] == "gpt-4o"

    def test_anthropic_model_key_exists_in_defaults(self):
        assert "ANTHROPIC_MODEL" in DEFAULT_CONFIG

    def test_anthropic_model_default_value(self):
        assert DEFAULT_CONFIG["ANTHROPIC_MODEL"] == "claude-3-5-sonnet-20241022"


class TestResolveModelName:
    def test_returns_configured_value_when_set(self):
        assert resolve_model_name("openai", "gpt-3.5-turbo") == "gpt-3.5-turbo"

    def test_falls_back_to_default_when_empty_string(self):
        assert resolve_model_name("openai", "") == "gpt-4o"

    def test_falls_back_to_default_when_none(self):
        assert resolve_model_name("openai", None) == "gpt-4o"

    def test_anthropic_falls_back_to_default(self):
        assert resolve_model_name("anthropic", "") == "claude-3-5-sonnet-20241022"

    def test_anthropic_returns_configured_value_when_set(self):
        assert resolve_model_name("anthropic", "claude-3-haiku-20240307") == "claude-3-haiku-20240307"

    def test_unknown_provider_returns_empty_string(self):
        assert resolve_model_name("mistral", "") == ""

    def test_strips_surrounding_whitespace(self):
        assert resolve_model_name("openai", "  gpt-4o  ") == "gpt-4o"

    def test_case_insensitive_provider_name(self):
        assert resolve_model_name("OpenAI", "") == "gpt-4o"
        assert resolve_model_name("ANTHROPIC", "") == "claude-3-5-sonnet-20241022"
