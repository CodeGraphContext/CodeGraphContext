"""
TC-01 to TC-08: Unit tests for _apply_response_token_limit() in server.py

Covers the stricter-wins logic for MAX_TOOL_RESPONSE_TOKENS and
MAX_PROMPT_CHARS, the [CGC] notice appended on truncation, and the
stderr warning emitted when text is cut.
"""

from unittest.mock import patch

from codegraphcontext.server import _apply_response_token_limit, _CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL = "find_code"
LONG_TEXT = "x" * 2000  # 2 000 chars, safely above any limit used below

# get_config_value is imported inside the function body, so patch its source.
_PATCH_TARGET = "codegraphcontext.cli.config_manager.get_config_value"


def _config(tokens="0", chars="0"):
    """Return a side_effect callable for get_config_value."""
    mapping = {
        "MAX_TOOL_RESPONSE_TOKENS": tokens,
        "MAX_PROMPT_CHARS": chars,
    }
    return mapping.get


# ---------------------------------------------------------------------------
# TC-01: both limits disabled — text returned unchanged
# ---------------------------------------------------------------------------

def test_no_limits_returns_text_unchanged():
    with patch(_PATCH_TARGET, side_effect=_config("0", "0")):
        result = _apply_response_token_limit(TOOL, LONG_TEXT)
    assert result == LONG_TEXT


# ---------------------------------------------------------------------------
# TC-02: only MAX_TOOL_RESPONSE_TOKENS set — truncates at token boundary
# ---------------------------------------------------------------------------

def test_token_limit_only_truncates():
    max_tokens = 100  # → 400 chars
    with patch(_PATCH_TARGET, side_effect=_config(tokens=str(max_tokens), chars="0")):
        result = _apply_response_token_limit(TOOL, LONG_TEXT)

    assert len(result) <= max_tokens * _CHARS_PER_TOKEN
    assert "[CGC] Response truncated" in result


# ---------------------------------------------------------------------------
# TC-03: only MAX_PROMPT_CHARS set — truncates at char boundary
# ---------------------------------------------------------------------------

def test_char_limit_only_truncates():
    max_chars = 300
    with patch(_PATCH_TARGET, side_effect=_config(tokens="0", chars=str(max_chars))):
        result = _apply_response_token_limit(TOOL, LONG_TEXT)

    assert len(result) <= max_chars
    assert "[CGC] Response truncated" in result


# ---------------------------------------------------------------------------
# TC-04: both set — stricter (smaller) limit wins
# ---------------------------------------------------------------------------

def test_stricter_limit_wins():
    # char limit 200 is stricter than token limit 200*4=800
    with patch(_PATCH_TARGET, side_effect=_config(tokens="200", chars="200")):
        result_char_stricter = _apply_response_token_limit(TOOL, LONG_TEXT)

    # token limit 50*4=200 is stricter than char limit 800
    with patch(_PATCH_TARGET, side_effect=_config(tokens="50", chars="800")):
        result_token_stricter = _apply_response_token_limit(TOOL, LONG_TEXT)

    assert len(result_char_stricter) <= 200
    assert len(result_token_stricter) <= 50 * _CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# TC-05: text shorter than limit — returned unchanged
# ---------------------------------------------------------------------------

def test_short_text_not_truncated():
    short = "hello world"
    with patch(_PATCH_TARGET, side_effect=_config(tokens="500", chars="500")):
        result = _apply_response_token_limit(TOOL, short)
    assert result == short


# ---------------------------------------------------------------------------
# TC-06: notice mentions the active limit key(s)
# ---------------------------------------------------------------------------

def test_notice_mentions_active_limits():
    with patch(_PATCH_TARGET, side_effect=_config(tokens="100", chars="200")):
        result = _apply_response_token_limit(TOOL, LONG_TEXT)

    assert "MAX_PROMPT_CHARS" in result or "MAX_TOOL_RESPONSE_TOKENS" in result


# ---------------------------------------------------------------------------
# TC-07: stderr warning is printed on truncation
# ---------------------------------------------------------------------------

def test_stderr_warning_printed_on_truncation(capsys):
    with patch(_PATCH_TARGET, side_effect=_config(tokens="0", chars="100")):
        _apply_response_token_limit(TOOL, LONG_TEXT)

    captured = capsys.readouterr()
    assert "[CGC WARNING]" in captured.err
    assert TOOL in captured.err


# ---------------------------------------------------------------------------
# TC-08: stderr warning NOT printed when text fits within limits
# ---------------------------------------------------------------------------

def test_no_stderr_when_text_fits(capsys):
    short = "tiny"
    with patch(_PATCH_TARGET, side_effect=_config(tokens="0", chars="1000")):
        _apply_response_token_limit(TOOL, short)

    captured = capsys.readouterr()
    assert captured.err == ""
