"""Missing containment edges must fail the real parity comparison."""

import importlib.util
from pathlib import Path

import pytest

import codegraphcontext.core as core


@pytest.fixture
def parity(monkeypatch):
    source = Path(__file__).resolve().parents[2] / 'e2e' / 'test_verify_databases_parity.py'
    spec = importlib.util.spec_from_file_location('cgc_parity_guard_test', source)
    parity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    original_find_spec = importlib.util.find_spec
    drivers = {'kuzu', 'ladybug', 'falkordb', 'neo4j'}
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: object() if name in drivers else original_find_spec(name))
    monkeypatch.setattr(core, 'is_falkordb_usable', lambda: True)
    monkeypatch.setattr(core, 'ladybugdb_unavailable_reason', lambda: None, raising=False)
    monkeypatch.setattr(parity, '_probe_embedded_backend', lambda name: None)
    return parity


@pytest.mark.asyncio
@pytest.mark.parametrize('deficit', [0, 1, 51, 64])
async def test_contains_deficit_is_not_accepted(monkeypatch, tmp_path, deficit, parity):
    indexed_backends = []

    async def indexed_stats(db_type, project_path, temp_test_dir):
        indexed_backends.append(db_type)
        return 0.0, {'NODE_File': 292, 'REL_CONTAINS': 4727 - (deficit if db_type == 'ladybugdb' else 0)}, [], []

    monkeypatch.setattr(parity, 'run_indexing_in_process', indexed_stats)
    if deficit:
        with pytest.raises(AssertionError, match='Database statistics do not match'):
            await parity._run_database_parity_e2e(tmp_path)
    else:
        await parity._run_database_parity_e2e(tmp_path)
    assert set(indexed_backends) == {'kuzudb', 'ladybugdb', 'falkordb', 'neo4j'}


@pytest.mark.asyncio
async def test_equal_counts_with_different_edges_fail_and_save_diagnostics(monkeypatch, tmp_path, parity, capsys):
    source = ['File', 'example.py', 'example.py', None, None]
    right = [source, ['Function', 'example.py', 'work', 1, 0]]
    wrong = [source, ['Function', 'example.py', 'work', 1, 1]]

    async def indexed_stats(db_type, project_path, temp_test_dir):
        return 0.0, {'REL_CONTAINS': 1}, [], [wrong if db_type == 'ladybugdb' else right]

    monkeypatch.setattr(parity, 'run_indexing_in_process', indexed_stats)
    artifact_dir = tmp_path / 'diagnostics'
    monkeypatch.setenv('CGC_PARITY_DIAGNOSTICS_DIR', str(artifact_dir))
    with pytest.raises(AssertionError, match='CONTAINS edge identities do not match'):
        await parity._run_database_parity_e2e(tmp_path)
    import json
    report = json.loads((artifact_dir / 'containment-parity.json').read_text())
    assert report['ladybugdb']['contains_edges'] == [wrong]
    assert report['kuzudb']['contains_edges'] == [right]
    assert 'missing source File example.py: 1' in capsys.readouterr().out


def test_contains_samples_are_bounded_but_group_counts_include_every_edge(parity, capsys):
    edges = [[['File', 'example.py', 'example.py', None, None],
              ['Function', 'example.py', f'f{i}', i, 0]] for i in range(51)]
    results = {'kuzudb': {'contains_edges': edges}, 'ladybugdb': {'contains_edges': []}}
    assert not parity._report_contains_edge_diff(results, list(results))
    output = capsys.readouterr().out
    assert 'missing source File example.py: 51' in output
    assert output.count('    [["File"') == 40
    assert '11 more; see containment-parity.json' in output
