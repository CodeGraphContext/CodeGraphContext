from pathlib import Path

from codegraphcontext.utils.path_sandbox import (
    clamp_discovery_depth,
    is_safe_download_url,
    sanitize_bundle_filename,
)


def test_sanitize_bundle_filename_rejects_traversal():
    assert sanitize_bundle_filename("../../etc/passwd.cgc") == "bundle.cgc"
    assert sanitize_bundle_filename("numpy.cgc") == "numpy.cgc"


def test_is_safe_download_url_allows_registry_hosts():
    assert is_safe_download_url("https://huggingface.co/datasets/codegraphcontext/registry/resolve/main/foo.cgc")
    assert not is_safe_download_url("http://evil.com/bundle.cgc")
    assert not is_safe_download_url("https://169.254.169.254/latest/meta-data")


def test_is_safe_download_url_allows_gitlab_hosted_bundles():
    """GitLab serves raw files from gitlab.com itself, and the suffix match
    covers its subdomains too."""
    assert is_safe_download_url("https://gitlab.com/group/project/-/raw/main/foo.cgc")
    assert is_safe_download_url("https://raw.gitlab.com/group/project/foo.cgc")
    # Suffix matching must not turn into a substring match.
    assert not is_safe_download_url("https://gitlab.com.evil.net/foo.cgc")
    assert not is_safe_download_url("https://notgitlab.com/foo.cgc")
    assert not is_safe_download_url("http://gitlab.com/group/project/-/raw/main/foo.cgc")


def test_clamp_discovery_depth():
    assert clamp_discovery_depth(1000) == 10
    assert clamp_discovery_depth(-3) == 0
    assert clamp_discovery_depth("2") == 2
