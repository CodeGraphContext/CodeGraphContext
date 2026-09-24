"""Regression tests for package_resolver — flat module bug (#1528)."""
from pathlib import Path

import pytest
from codegraphcontext.tools.package_resolver import get_local_package_path


def test_flat_module_returns_file_not_site_packages():
    """six.py / typing_extensions.py must resolve to the .py file, not site-packages."""
    for pkg in ("six", "typing_extensions"):
        result = get_local_package_path(pkg, "python")
        if result is None:
            pytest.skip(f"{pkg} not installed")
        assert not result.endswith("site-packages"), (
            f"{pkg} resolved to site-packages dir: {result!r}"
        )
        assert not result.endswith("dist-packages"), (
            f"{pkg} resolved to dist-packages dir: {result!r}"
        )
        assert result.endswith(".py"), (
            f"Expected a .py file for flat module {pkg}, got: {result!r}"
        )


def test_namespace_package_returns_directory():
    """A normal namespace package (e.g. 'packaging') should still return its directory."""
    result = get_local_package_path("packaging", "python")
    if result is None:
        pytest.skip("packaging not installed")
    assert not result.endswith(".py"), (
        f"packaging should return a directory, not a file: {result!r}"
    )
    assert Path(result).is_dir(), f"Expected a directory, got: {result!r}"
