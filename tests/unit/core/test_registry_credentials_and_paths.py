"""Regression tests for credential scoping and cross-platform path handling."""
from pathlib import Path

import pytest

from codegraphcontext.core import bundle_registry
from codegraphcontext.core.bundle_registry import (
    DEFAULT_HF_REGISTRY_REPO,
    _get_manifest_url,
    _github_headers,
    _huggingface_headers,
    _resolve_hf_registry_repo,
)


def test_github_token_is_not_sent_to_huggingface(monkeypatch):
    """A developer with GITHUB_TOKEN exported (routine in CI) leaked it to
    huggingface.co on every registry call."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_value")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)

    headers = _huggingface_headers()

    assert "Authorization" not in headers
    assert "ghp_secret_value" not in "".join(headers.values())


def test_huggingface_headers_use_hf_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_abc")

    assert _huggingface_headers()["Authorization"] == "Bearer hf_abc"


def test_github_headers_still_carry_the_github_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abc")
    assert _github_headers()["Authorization"] == "token ghp_abc"


@pytest.mark.parametrize(
    "value",
    [
        "evil.example.com/x/../../y",
        "/etc/passwd",
        "https://evil.example.com/repo",
        "owner/name/extra/../..",
        "..%2f..%2fetc",
        "",
    ],
)
def test_invalid_hf_registry_repo_falls_back_to_the_default(monkeypatch, value):
    """HF_REGISTRY_REPO was interpolated unvalidated, so a crafted value could
    steer the request — and any credential on it — off huggingface.co."""
    monkeypatch.setenv("HF_REGISTRY_REPO", value)

    assert _resolve_hf_registry_repo() == DEFAULT_HF_REGISTRY_REPO
    assert _get_manifest_url().startswith(
        f"https://huggingface.co/datasets/{DEFAULT_HF_REGISTRY_REPO}/"
    )


def test_valid_hf_registry_repo_is_honoured(monkeypatch):
    monkeypatch.setenv("HF_REGISTRY_REPO", "my-org/my_registry.v2")
    assert _resolve_hf_registry_repo() == "my-org/my_registry.v2"


def test_bundle_scoping_uses_posix_separators():
    """Graph paths are stored via Path.resolve().as_posix() (#1080), so the
    bundle's repo scoping must compare POSIX strings. Using os.sep produced a
    prefix that could never match on Windows, yielding an empty bundle."""
    import inspect

    from codegraphcontext.core import cgc_bundle

    source = inspect.getsource(cgc_bundle)
    assert "os.sep" not in source, "repo scoping must not use native separators"
    assert "str(repo_path.resolve())" not in source


def test_prescan_paths_are_posix():
    """The pre-scan imports_map fed substring heuristics that compare a
    '/'-joined import name against the stored path; native separators made
    those tiers unmatchable on Windows."""
    import inspect

    from codegraphcontext.tools.languages import go, python

    for module in (python, go):
        source = inspect.getsource(module)
        assert "str(path.resolve())" not in source
        assert "path.resolve().as_posix()" in source
