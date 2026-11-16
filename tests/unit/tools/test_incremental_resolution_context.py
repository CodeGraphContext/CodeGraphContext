from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.watcher import RepositoryEventHandler
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups


@pytest.mark.parametrize('project', ['python', 'typescript', 'java', 'csharp', 'go', 'kotlin'])
def test_emitted_calls_equal_full_resolution_filtered_by_source(project):
    name = 'sample_project' if project == 'python' else f'sample_project_{project}'
    root = Path(__file__).resolve().parents[2] / 'fixtures' / 'sample_projects' / name
    if not root.exists():
        pytest.skip(f'no {project} fixture')
    builder = GraphBuilder(MagicMock(), MagicMock(), None)
    files = [path for path in sorted(root.rglob('*')) if path.is_file() and path.suffix in builder.parsers]
    imports = builder.pre_scan_imports(files)
    data = [builder.parse_file(root, path) for path in files]
    data = [record for record in data if isinstance(record, dict) and 'error' not in record]
    assert data
    full = build_function_call_groups(deepcopy(data), imports)
    assert any(full), project
    for record in data:
        source = Path(record['path']).resolve().as_posix()
        restricted = build_function_call_groups(deepcopy(data), imports, emit_paths={source})
        expected = tuple([row for row in group if row['caller_file_path'] == source] for group in full)
        assert restricted == expected, (project, source)
    assert not any(build_function_call_groups(deepcopy(data), imports, emit_paths=set()))

    builder._writer = MagicMock()
    builder.link_inheritance(deepcopy(data), imports)
    inheritance = builder._writer.method_calls[:]
    source_fields = {'write_companion_of_links': 'companion_path', 'write_part_of_links': 'child_path',
                     'write_decorated_by_links': 'decorated_path', 'write_binds_links': 'source_path',
                     'write_previews_links': 'preview_path'}
    for record in data:
        source = Path(record['path']).resolve().as_posix()
        builder._writer.reset_mock()
        builder.link_inheritance(deepcopy(data), imports, emit_paths={source})
        for full_call, restricted_call in zip(inheritance, builder._writer.method_calls, strict=True):
            method = full_call[0]
            assert restricted_call[0] == method
            key = source_fields.get(method, 'path')
            expected = [row for row in full_call.args[0] if Path(row[key]).resolve().as_posix() == source]
            assert restricted_call.args[0] == expected, (project, method, source)
            if method == 'write_inheritance_links':
                assert restricted_call.args[1] == [row for row in full_call.args[1]
                                                   if Path(row['path']).resolve().as_posix() == source]


def test_parse_cache_reuses_unmodified_files_prunes_deletions_and_isolates_annotations(tmp_path, monkeypatch):
    left, right = tmp_path / 'left.py', tmp_path / 'right.py'
    left.write_text('left')
    right.write_text('right')
    builder = MagicMock()
    builder.parse_file.side_effect = lambda root, path: {'path': str(path), 'functions': [{'name': path.read_text()}]}
    handler = RepositoryEventHandler(builder, tmp_path, perform_initial_scan=False)
    monkeypatch.setattr(handler, '_iter_supported_files', lambda: [path for path in (left, right) if path.exists()])
    first = handler._resolution_context(left)
    first[1]['functions'][0]['name'] = 'resolver annotation'
    builder.parse_file.reset_mock()
    second = handler._resolution_context(left)
    assert second[1]['functions'][0]['name'] == 'right'
    assert [call.args[1] for call in builder.parse_file.call_args_list] == [left]
    right.write_text('a changed dependency')
    third = handler._resolution_context(left)
    assert third[1]['functions'][0]['name'] == 'a changed dependency'
    right.unlink()
    assert len(handler._resolution_context(left)) == 1
    assert set(handler._resolution_cache) == {left.as_posix()}
    left.unlink()
    assert handler._resolution_context(left) == []
    assert handler._resolution_cache == {}
