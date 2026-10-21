from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.watcher import RepositoryEventHandler
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing.discovery import discover_files_to_index


@pytest.fixture
def links(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def outside_marker(): pass\n")
    inside = repo / "inside.py"
    inside.write_text("def inside_marker(): pass\n")
    link = repo / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("CGC_ALLOW_ALL_PATHS", raising=False)
    monkeypatch.delenv("CGC_ALLOWED_ROOTS", raising=False)
    return repo, inside, outside, link


def test_directory_discovery_excludes_external_file_target(links):
    repo, inside, outside, _ = links
    files, _ = discover_files_to_index(repo, supported_extensions={".py"})
    assert files == [inside]
    assert outside not in files


def test_in_root_link_is_canonical_and_deduplicated(links):
    repo, inside, _, link = links
    link.unlink()
    link.symlink_to(inside)
    files, _ = discover_files_to_index(repo, supported_extensions={".py"})
    assert files == [inside]


@pytest.mark.parametrize("override", ["CGC_ALLOW_ALL_PATHS", "CGC_ALLOWED_ROOTS"])
def test_explicit_override_allows_external_link(links, monkeypatch, override):
    repo, _, outside, _ = links
    monkeypatch.setenv(override, "true" if override == "CGC_ALLOW_ALL_PATHS" else "*")
    files, _ = discover_files_to_index(repo, supported_extensions={".py"})
    assert outside in files


def test_explicit_extra_root_allows_external_link(links, monkeypatch):
    repo, _, outside, _ = links
    monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(outside.parent))
    files, _ = discover_files_to_index(repo, supported_extensions={".py"})
    assert outside in files


def test_parse_rechecks_retargeted_file_before_parser_access(links):
    repo, inside, outside, _ = links
    inside.unlink()
    inside.symlink_to(outside)
    builder = GraphBuilder.__new__(GraphBuilder)
    builder.get_parser = MagicMock()
    result = builder.parse_file(repo, inside)
    assert result["parse_failed"] is True
    builder.get_parser.assert_not_called()


def test_watch_events_do_not_follow_external_link(links):
    repo, _, _, link = links
    handler = RepositoryEventHandler.__new__(RepositoryEventHandler)
    handler.repo_path = repo
    assert handler._should_ignore(link)
