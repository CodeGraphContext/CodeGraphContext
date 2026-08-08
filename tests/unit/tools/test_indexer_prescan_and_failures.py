"""Regression tests for pre-scan merging, generic dotfiles and parse-failure reporting."""
from pathlib import Path

from codegraphcontext.tools.indexing import pre_scan
from codegraphcontext.tools.indexing.discovery import (
    _GENERIC_EXTENSIONS,
    _GENERIC_FILENAMES,
)
from codegraphcontext.tools.indexing.pipeline import build_index_summary


def test_prescan_merges_symbols_across_languages(monkeypatch):
    """dict.update() replaced the path list, so a symbol defined in two
    languages kept only the last-scanned language's paths."""

    def java_scanner(files, get_parser):
        return {"Widget": ["/repo/Widget.java"], "render": ["/repo/Widget.java"]}

    def python_scanner(files, get_parser):
        return {"Widget": ["/repo/helper.py"], "render": ["/repo/helper.py"]}

    monkeypatch.setattr(
        pre_scan, "_get_registry", lambda: {".java": java_scanner, ".py": python_scanner}
    )

    result = pre_scan.pre_scan_for_imports(
        [Path("/repo/Widget.java"), Path("/repo/helper.py")],
        {".java": "java", ".py": "python"},
        lambda ext: None,
    )

    assert sorted(result["Widget"]) == ["/repo/Widget.java", "/repo/helper.py"]
    assert sorted(result["render"]) == ["/repo/Widget.java", "/repo/helper.py"]


def test_prescan_does_not_duplicate_repeated_paths(monkeypatch):
    def scanner_a(files, get_parser):
        return {"Shared": ["/repo/a.py"]}

    def scanner_b(files, get_parser):
        return {"Shared": ["/repo/a.py", "/repo/b.rb"]}

    monkeypatch.setattr(
        pre_scan, "_get_registry", lambda: {".py": scanner_a, ".rb": scanner_b}
    )

    result = pre_scan.pre_scan_for_imports(
        [Path("/repo/a.py"), Path("/repo/b.rb")],
        {".py": "python", ".rb": "ruby"},
        lambda ext: None,
    )

    assert result["Shared"] == ["/repo/a.py", "/repo/b.rb"]


def test_dotfiles_are_matched_by_name_not_extension():
    """Path('.gitignore').suffix == '', so listing dotfiles among the
    extensions meant they never matched and never got a File node."""
    assert Path(".gitignore").suffix == ""

    for dotfile in (".gitignore", ".dockerignore"):
        assert dotfile in _GENERIC_FILENAMES
        # ...and no longer in the (unreachable) extension set.
        assert dotfile not in _GENERIC_EXTENSIONS


def test_index_summary_reports_parse_failures():
    """A run where files failed to parse was indistinguishable from a clean
    one: the summary had no failure row at all."""
    failures = [{"path": "/repo/latin.py", "error": "'utf-8' codec can't decode byte"}]

    summary = build_index_summary(
        files=[Path("/repo/latin.py"), Path("/repo/ok.py")],
        parsers={".py": "python"},
        all_file_data=[{"path": "/repo/ok.py", "functions": [{}]}],
        resolved_call_groups=(),
        serialization_seconds=0.0,
        parse_failures=failures,
    )

    assert summary["failed_files"] == 1
    assert summary["failed_file_details"] == failures


def test_index_summary_reports_zero_failures_for_a_clean_run():
    summary = build_index_summary(
        files=[Path("/repo/ok.py")],
        parsers={".py": "python"},
        all_file_data=[{"path": "/repo/ok.py", "functions": [{}]}],
        resolved_call_groups=(),
        serialization_seconds=0.0,
    )

    assert summary["failed_files"] == 0
    assert summary["failed_file_details"] == []
