import pytest

from codegraphcontext.utils.secret_scanner import (
    REDACTED,
    is_likely_secret,
    scan_and_redact,
    scan_props_and_redact,
)


class TestIsLikelySecret:
    def test_empty_string(self):
        detected, pattern = is_likely_secret("")
        assert not detected
        assert pattern is None

    def test_none_value(self):
        detected, pattern = is_likely_secret(None)
        assert not detected

    def test_non_string(self):
        detected, pattern = is_likely_secret(42)
        assert not detected

    def test_plain_variable_name(self):
        detected, _ = is_likely_secret("my_variable")
        assert not detected

    def test_short_string(self):
        detected, _ = is_likely_secret("hello")
        assert not detected

    def test_url_not_flagged(self):
        detected, _ = is_likely_secret("https://example.com/api/v1/users")
        assert not detected

    def test_openai_api_key(self):
        detected, pattern = is_likely_secret("sk-proj-abc123def456ghi789jkl012mno345pq")
        assert detected
        assert pattern is not None

    def test_github_pat(self):
        detected, pattern = is_likely_secret("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh")
        assert detected

    def test_github_fine_grained_pat(self):
        detected, pattern = is_likely_secret("github_pat_22chars_here_abcdefghij")
        assert detected

    def test_aws_access_key(self):
        detected, pattern = is_likely_secret("AKIAIOSFODNN7EXAMPLE")
        assert detected

    def test_bearer_token(self):
        detected, pattern = is_likely_secret("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
        assert detected

    def test_jwt_token(self):
        detected, pattern = is_likely_secret("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
        assert detected

    def test_private_key(self):
        detected, pattern = is_likely_secret("-----BEGIN RSA PRIVATE KEY-----")
        assert detected

    def test_password_assignment(self):
        detected, pattern = is_likely_secret('password = "SuperSecret123!"')
        assert detected

    def test_api_key_assignment(self):
        detected, pattern = is_likely_secret("api_key = 'sk-1234567890abcdef1234567890abcdef'")
        assert detected

    def test_connection_string(self):
        detected, pattern = is_likely_secret("mongodb://admin:password123@db.example.com:27017/mydb")
        assert detected

    def test_postgres_connection_string(self):
        detected, pattern = is_likely_secret("postgres://user:pass@host:5432/dbname")
        assert detected

    def test_slack_token(self):
        detected, pattern = is_likely_secret("xoxb-" + "1234567890" + "-abcdefghijklmnop")
        assert detected

    def test_stripe_key(self):
        detected, pattern = is_likely_secret("sk_" + "live_" + "abcdefghijklmnopqrstuvwx")
        assert detected

    def test_sendgrid_key(self):
        detected, pattern = is_likely_secret("SG.abcdefghijklmnopqrstuv.wxyz0123456789abcdefghijklmnopqrstuvwxyz01234")
        assert detected

    def test_npm_token(self):
        detected, pattern = is_likely_secret("npm_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
        assert detected

    def test_normal_string_not_flagged(self):
        detected, _ = is_likely_secret("Hello, World!")
        assert not detected

    def test_normal_path_not_flagged(self):
        detected, _ = is_likely_secret("/usr/local/bin/python3")
        assert not detected

    def test_normal_import_not_flagged(self):
        detected, _ = is_likely_secret("from collections import OrderedDict")
        assert not detected

    def test_high_entropy_with_key_hint(self):
        detected, pattern = is_likely_secret("secret_a8f5f167f44f4964e6c998dee827110c3b2e3f7a9c4d6e8b")
        assert detected
        assert pattern == "entropy"

    def test_low_entropy_long_string_not_flagged(self):
        detected, _ = is_likely_secret("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert not detected


class TestScanAndRedact:
    def test_no_secret_unchanged(self):
        result, was_secret, pattern = scan_and_redact("hello world")
        assert result == "hello world"
        assert not was_secret

    def test_secret_not_redacted_by_default(self):
        result, was_secret, pattern = scan_and_redact("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh")
        assert result == "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
        assert was_secret

    def test_secret_redacted_when_enabled(self):
        result, was_secret, pattern = scan_and_redact(
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh", redact=True
        )
        assert result == REDACTED
        assert was_secret

    def test_non_secret_not_redacted(self):
        result, was_secret, pattern = scan_and_redact("my_function_name", redact=True)
        assert result == "my_function_name"
        assert not was_secret


class TestScanPropsAndRedact:
    def test_no_secrets(self):
        props = {"name": "my_func", "line_number": 42, "path": "/src/main.py"}
        result, findings = scan_props_and_redact(props, redact=True)
        assert result == props
        assert findings == []

    def test_secret_in_value_redacted(self):
        props = {"name": "API_KEY", "value": "sk-proj-abc123def456ghi789jkl012mno345pq", "line_number": 10}
        result, findings = scan_props_and_redact(props, redact=True)
        assert result["value"] == REDACTED
        assert result["name"] == "API_KEY"
        assert len(findings) == 1
        assert findings[0][0] == "value"

    def test_secret_in_value_not_redacted_by_default(self):
        props = {"name": "API_KEY", "value": "sk-proj-abc123def456ghi789jkl012mno345pq"}
        result, findings = scan_props_and_redact(props, redact=False)
        assert result["value"] == "sk-proj-abc123def456ghi789jkl012mno345pq"
        assert len(findings) == 1

    def test_multiple_secrets(self):
        props = {
            "name": "config",
            "api_key": "sk-proj-abc123def456ghi789jkl012mno345pq",
            "password": 'password = "SuperSecret123!"',
        }
        result, findings = scan_props_and_redact(props, redact=True)
        assert result["api_key"] == REDACTED
        assert result["password"] == REDACTED
        assert len(findings) == 2

    def test_non_string_values_untouched(self):
        props = {"name": "test", "line_number": 42, "is_dependency": False, "complexity": 3.5}
        result, findings = scan_props_and_redact(props, redact=True)
        assert result == props
        assert findings == []

    def test_list_with_secrets(self):
        props = {"name": "test", "values": ["normal", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"]}
        result, findings = scan_props_and_redact(props, redact=True)
        assert result["values"][0] == "normal"
        assert result["values"][1] == REDACTED
        assert len(findings) == 1

    def test_list_without_secrets(self):
        props = {"name": "test", "args": ["x", "y", "z"]}
        result, findings = scan_props_and_redact(props, redact=True)
        assert result["args"] == ["x", "y", "z"]
        assert findings == []

    def test_empty_props(self):
        result, findings = scan_props_and_redact({}, redact=True)
        assert result == {}
        assert findings == []
