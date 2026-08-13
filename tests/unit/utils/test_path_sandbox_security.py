import pytest

from codegraphcontext.utils.path_sandbox import (
    clamp_discovery_depth,
    is_safe_download_url,
    sanitize_bundle_filename,
)


def test_sanitize_bundle_filename_rejects_traversal():
    # Path traversal sequences must always fall back to the default name.
    assert sanitize_bundle_filename("../../etc/passwd.cgc") == "bundle.cgc"
    assert sanitize_bundle_filename("numpy.cgc") == "numpy.cgc"


# Parametrized cases from the original issue report.
# Previously the second case was a bug: a .cgc-suffixed name with unsafe
# characters would skip sanitization entirely and be returned unchanged.
@pytest.mark.parametrize(
    "input_name, expected",
    [
        # Clean name - must pass through unchanged.
        ("ok.cgc", "ok.cgc"),
        # Unsafe chars present, already ends with .cgc - must be sanitized (was the bug).
        ("we ird$.cgc", "we_ird_.cgc"),
        # Unsafe chars present, non-.cgc extension - must be sanitized and .cgc appended.
        ("we ird$.txt", "we_ird_.txt.cgc"),
        # Injection payload containing a forward slash - the early guard rejects it
        # before sanitization and returns the safe default name.
        ("<script>alert(1)</script>.cgc", "bundle.cgc"),
        # Injection payload without slashes - unsafe chars are removed by the regex.
        # Parentheses are not in [\w.\-] so they must be replaced with underscores.
        ("alert(1).cgc", "alert_1_.cgc"),
    ],
)
def test_sanitize_bundle_filename_unconditional(input_name, expected):
    # Sanitization must run regardless of whether the filename ends with .cgc.
    assert sanitize_bundle_filename(input_name) == expected


def test_is_safe_download_url_allows_registry_hosts():
    assert is_safe_download_url(
        "https://huggingface.co/datasets/codegraphcontext/registry/resolve/main/foo.cgc"
    )
    assert not is_safe_download_url("http://evil.com/bundle.cgc")
    assert not is_safe_download_url("https://169.254.169.254/latest/meta-data")


def test_clamp_discovery_depth():
    assert clamp_discovery_depth(1000) == 10
    assert clamp_discovery_depth(-3) == 0
    assert clamp_discovery_depth("2") == 2
