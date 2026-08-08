"""Tests for the GCF output encoding module."""

import json
import os
import pytest
from codegraphcontext.utils.gcf_encoder import encode_response, is_gcf_enabled, _load_gcf


@pytest.fixture(autouse=True)
def reset_gcf_state(monkeypatch):
    """Reset GCF module state between tests."""
    import codegraphcontext.utils.gcf_encoder as mod
    mod._gcf_checked = False
    mod._gcf_encode = None
    monkeypatch.delenv("CGC_OUTPUT_FORMAT", raising=False)
    yield


class TestIsGcfEnabled:
    def test_disabled_by_default(self):
        assert not is_gcf_enabled()

    def test_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "gcf")
        assert is_gcf_enabled()

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "GCF")
        assert is_gcf_enabled()

    def test_other_values_are_disabled(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "xml")
        assert not is_gcf_enabled()


class TestEncodeResponse:
    def test_json_by_default(self):
        result = {"success": True, "results": [{"name": "foo"}]}
        encoded = encode_response(result)
        assert json.loads(encoded) == result

    def test_json_is_indented(self):
        result = {"key": "value"}
        encoded = encode_response(result)
        assert "\n" in encoded  # indent=2 produces newlines

    def test_gcf_when_enabled_and_installed(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "gcf")
        encoder = _load_gcf()
        if encoder is None:
            pytest.skip("gcf-python not installed")
        encoded = encode_response({"success": True, "results": [{"name": "foo", "kind": "function"}]})
        # GCF output contains pipe delimiters
        assert "|" in encoded
        # Should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(encoded)

    def test_gcf_smaller_than_json(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "gcf")
        encoder = _load_gcf()
        if encoder is None:
            pytest.skip("gcf-python not installed")
        data = {
            "success": True,
            "results": [
                {"name": f"func_{i}", "path": f"src/mod_{i}.py", "line": i * 10, "kind": "function", "complexity": 5 + i}
                for i in range(10)
            ],
        }
        gcf_text = encode_response(data)
        monkeypatch.delenv("CGC_OUTPUT_FORMAT")
        import codegraphcontext.utils.gcf_encoder as mod
        mod._gcf_checked = False
        mod._gcf_encode = None
        json_text = encode_response(data)
        assert len(gcf_text) < len(json_text) * 0.7  # At least 30% smaller

    def test_falls_back_to_json_when_gcf_not_installed(self, monkeypatch):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "gcf")
        import codegraphcontext.utils.gcf_encoder as mod
        mod._gcf_checked = True
        mod._gcf_encode = None  # Simulate package not found
        result = {"success": True, "data": "test"}
        encoded = encode_response(result)
        assert json.loads(encoded) == result

    def test_falls_back_to_json_when_gcf_encoding_fails(self, monkeypatch, caplog):
        monkeypatch.setenv("CGC_OUTPUT_FORMAT", "gcf")
        import codegraphcontext.utils.gcf_encoder as mod

        def failing_encoder(_result):
            raise ValueError("unsupported result shape")

        mod._gcf_checked = True
        mod._gcf_encode = failing_encoder
        result = {"success": True, "data": "test"}

        with caplog.at_level("DEBUG", logger="codegraphcontext.utils.gcf_encoder"):
            encoded = encode_response(result)

        assert json.loads(encoded) == result
        assert "GCF encoding failed; falling back to JSON" in caplog.text
