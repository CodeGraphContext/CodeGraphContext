import pytest
from unittest.mock import patch

from codegraphcontext.tools.indexing.sanitize import (
    MAX_STR_LEN,
    sanitize_props,
    sanitize_props_with_secrets,
    reset_secret_cache,
)


class TestSanitizeProps:
    def setup_method(self):
        reset_secret_cache()

    def test_basic_types_preserved(self):
        props = {"name": "foo", "line": 42, "ratio": 3.14, "flag": True, "empty": None}
        result = sanitize_props(props)
        assert result == props

    def test_long_string_truncated(self):
        long = "x" * (MAX_STR_LEN + 100)
        result = sanitize_props({"name": long})
        assert len(result["name"]) == MAX_STR_LEN

    def test_complex_value_serialized(self):
        props = {"meta": {"key": "value"}}
        result = sanitize_props(props)
        assert isinstance(result["meta"], str)
        assert "key" in result["meta"]

    def test_flat_list_preserved(self):
        props = {"args": ["a", "b", "c"]}
        result = sanitize_props(props)
        assert result["args"] == ["a", "b", "c"]

    def test_redact_disabled_by_default(self):
        props = {"value": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"}
        result = sanitize_props(props)
        assert result["value"] == "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"

    def test_redact_via_param(self):
        props = {"value": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"}
        result = sanitize_props(props, _redact=True)
        assert result["value"] == "[REDACTED]"

    def test_redact_via_config(self):
        with patch("codegraphcontext.tools.indexing.sanitize._redact_enabled", return_value=True):
            reset_secret_cache()
            props = {"value": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"}
            result = sanitize_props(props)
            assert result["value"] == "[REDACTED]"

    def test_no_redact_via_param_override(self):
        props = {"value": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"}
        result = sanitize_props(props, _redact=False)
        assert result["value"] == "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"


class TestSanitizePropsWithSecrets:
    def setup_method(self):
        reset_secret_cache()

    def test_returns_findings(self):
        props = {"value": "sk-proj-abc123def456ghi789jkl012mno345pq", "name": "key"}
        result, findings = sanitize_props_with_secrets(props, redact=False)
        assert result["value"] == "sk-proj-abc123def456ghi789jkl012mno345pq"
        assert len(findings) == 1
        assert findings[0][0] == "value"

    def test_redacts_when_enabled(self):
        props = {"value": "sk-proj-abc123def456ghi789jkl012mno345pq", "name": "key"}
        result, findings = sanitize_props_with_secrets(props, redact=True)
        assert result["value"] == "[REDACTED]"
        assert len(findings) == 1

    def test_no_secrets_no_findings(self):
        props = {"name": "my_func", "line_number": 42}
        result, findings = sanitize_props_with_secrets(props, redact=True)
        assert result == props
        assert findings == []
