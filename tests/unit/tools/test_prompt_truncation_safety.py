"""
Unit tests for prompt/response truncation safety (issue #1102).

Covers:
- _effective_char_limit: picking the stricter of token vs char knobs
- _limit_source_label: correct human-readable label for each case
- _apply_response_token_limit: full end-to-end truncation behaviour
    * MAX_PROMPT_CHARS only
    * MAX_TOOL_RESPONSE_TOKENS only
    * both set (stricter wins)
    * both zero (unlimited — no truncation)
    * payload just at or below the limit (no truncation)
    * non-JSON payload
    * stdout warning emitted on truncation
    * config validation for MAX_PROMPT_CHARS
"""

import json
import sys
from unittest.mock import patch

import pytest

from codegraphcontext.server import (
    _apply_response_token_limit,
    _effective_char_limit,
    _limit_source_label,
)
from codegraphcontext.cli.config_manager import validate_config_value


# ---------------------------------------------------------------------------
# _effective_char_limit
# ---------------------------------------------------------------------------

class TestEffectiveCharLimit:
    def test_both_zero_returns_zero(self):
        assert _effective_char_limit(0, 0) == 0

    def test_only_token_limit(self):
        # 50 tokens × 4 chars/token = 200
        assert _effective_char_limit(50, 0) == 200

    def test_only_char_limit(self):
        assert _effective_char_limit(0, 500) == 500

    def test_token_limit_stricter(self):
        # 50 tokens → 200 chars vs 500 chars direct → 200 wins
        assert _effective_char_limit(50, 500) == 200

    def test_char_limit_stricter(self):
        # 200 tokens → 800 chars vs 300 chars direct → 300 wins
        assert _effective_char_limit(200, 300) == 300

    def test_equal_limits_returns_that_value(self):
        # 100 tokens → 400 chars, direct also 400 → 400
        assert _effective_char_limit(100, 400) == 400


# ---------------------------------------------------------------------------
# _limit_source_label
# ---------------------------------------------------------------------------

class TestLimitSourceLabel:
    def test_only_token_limit(self):
        label = _limit_source_label(50, 0, 200)
        assert "MAX_TOOL_RESPONSE_TOKENS" in label
        assert "50" in label
        assert "200" in label

    def test_only_char_limit(self):
        label = _limit_source_label(0, 500, 500)
        assert "MAX_PROMPT_CHARS" in label
        assert "500" in label

    def test_both_token_stricter(self):
        label = _limit_source_label(50, 500, 200)
        assert "MAX_TOOL_RESPONSE_TOKENS" in label

    def test_both_char_stricter(self):
        label = _limit_source_label(200, 100, 100)
        assert "MAX_PROMPT_CHARS" in label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_map(tokens="0", chars="0"):
    """Return a get_config_value side_effect that serves fixed values."""
    mapping = {
        "MAX_TOOL_RESPONSE_TOKENS": tokens,
        "MAX_PROMPT_CHARS": chars,
    }
    return lambda key: mapping.get(key, "0")


def _big_json(size: int = 2000) -> str:
    """Return a JSON string of at least *size* characters."""
    payload = {"results": ["x" * 50] * (size // 52 + 1)}
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# _apply_response_token_limit — no truncation cases
# ---------------------------------------------------------------------------

class TestNoTruncation:
    def test_both_zero_returns_text_unchanged(self):
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map()):
            result = _apply_response_token_limit("find_code", text)
        assert result == text

    def test_text_exactly_at_limit_not_truncated(self):
        limit = 500
        text = "x" * limit
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars=str(limit))):
            result = _apply_response_token_limit("find_code", text)
        assert result == text

    def test_text_one_char_below_limit_not_truncated(self):
        limit = 500
        text = "x" * (limit - 1)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars=str(limit))):
            result = _apply_response_token_limit("find_code", text)
        assert result == text


# ---------------------------------------------------------------------------
# _apply_response_token_limit — MAX_PROMPT_CHARS only
# ---------------------------------------------------------------------------

class TestMaxPromptChars:
    def test_truncates_oversized_json(self, capsys):
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars="300")):
            result = _apply_response_token_limit("find_code", text)

        parsed = json.loads(result)
        assert parsed["truncated"] is True
        assert "[CGC] Response truncated" in parsed["notice"]
        assert "MAX_PROMPT_CHARS" in parsed["notice"]

    def test_truncates_non_json_text(self):
        text = "plain text " * 200
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars="200")):
            result = _apply_response_token_limit("find_code", text)

        parsed = json.loads(result)
        assert parsed["truncated"] is True
        assert len(parsed["preview"]) <= 200

    def test_warning_emitted_to_stderr(self, capsys):
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars="300")):
            _apply_response_token_limit("find_code", text)

        captured = capsys.readouterr()
        assert "[CGC WARNING] Truncation fired" in captured.err
        assert "find_code" in captured.err
        assert "original_chars=" in captured.err
        assert "truncated_chars=300" in captured.err

    def test_tool_name_in_notice(self):
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(chars="300")):
            result = _apply_response_token_limit("analyze_code_relationships", text)

        parsed = json.loads(result)
        assert "analyze_code_relationships" in parsed["notice"]


# ---------------------------------------------------------------------------
# _apply_response_token_limit — MAX_TOOL_RESPONSE_TOKENS only
# ---------------------------------------------------------------------------

class TestMaxToolResponseTokens:
    def test_truncates_by_token_budget(self, capsys):
        # 50 tokens × 4 = 200 chars; use a 2000-char payload
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(tokens="50")):
            result = _apply_response_token_limit("find_code", text)

        parsed = json.loads(result)
        assert parsed["truncated"] is True
        assert "MAX_TOOL_RESPONSE_TOKENS" in parsed["notice"]

    def test_warning_mentions_tokens(self, capsys):
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(tokens="50")):
            _apply_response_token_limit("find_code", text)

        captured = capsys.readouterr()
        assert "MAX_TOOL_RESPONSE_TOKENS" in captured.err


# ---------------------------------------------------------------------------
# _apply_response_token_limit — both limits set, stricter wins
# ---------------------------------------------------------------------------

class TestBothLimitsSet:
    def test_token_limit_stricter(self, capsys):
        # 50 tokens → 200 chars; direct limit 500 → token wins
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(tokens="50", chars="500")):
            result = _apply_response_token_limit("find_code", text)

        parsed = json.loads(result)
        assert parsed["truncated"] is True
        # effective limit is 200 chars
        captured = capsys.readouterr()
        assert "truncated_chars=200" in captured.err
        assert "MAX_TOOL_RESPONSE_TOKENS" in captured.err

    def test_char_limit_stricter(self, capsys):
        # 200 tokens → 800 chars; direct limit 300 → char wins
        text = _big_json(2000)
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(tokens="200", chars="300")):
            result = _apply_response_token_limit("find_code", text)

        parsed = json.loads(result)
        assert parsed["truncated"] is True
        captured = capsys.readouterr()
        assert "truncated_chars=300" in captured.err
        assert "MAX_PROMPT_CHARS" in captured.err

    def test_no_warning_when_text_fits_stricter_limit(self, capsys):
        # Both limits larger than the text → no truncation, no warning
        text = "small text"
        with patch("codegraphcontext.cli.config_manager.get_config_value", side_effect=_config_map(tokens="1000", chars="1000")):
            result = _apply_response_token_limit("find_code", text)

        assert result == text
        captured = capsys.readouterr()
        assert "[CGC WARNING]" not in captured.err


# ---------------------------------------------------------------------------
# Config validation — MAX_PROMPT_CHARS
# ---------------------------------------------------------------------------

class TestMaxPromptCharsValidation:
    def test_zero_is_valid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "0")
        assert ok is True
        assert msg is None

    def test_positive_integer_is_valid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "500")
        assert ok is True

    def test_large_value_is_valid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "1000000")
        assert ok is True

    def test_negative_is_invalid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "-1")
        assert ok is False
        assert "MAX_PROMPT_CHARS" in msg

    def test_string_is_invalid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "abc")
        assert ok is False
        assert "integer" in msg.lower()

    def test_float_string_is_invalid(self):
        ok, msg = validate_config_value("MAX_PROMPT_CHARS", "3.14")
        assert ok is False
