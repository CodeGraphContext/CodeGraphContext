"""Missing containment edges must fail the real parity comparison."""

import importlib.util
from pathlib import Path

import pytest

import codegraphcontext.core as core


@pytest.mark.asyncio
@pytest.mark.parametrize('deficit', [0, 1, 51, 64])
async def test_contains_deficit_is_not_accepted(monkeypatch, tmp_path, deficit):
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
    indexed_backends = []

    async def indexed_stats(db_type, project_path, temp_test_dir):
        indexed_backends.append(db_type)
        return 0.0, {'NODE_File': 292, 'REL_CONTAINS': 4727 - (deficit if db_type == 'ladybugdb' else 0)}, []

    monkeypatch.setattr(parity, 'run_indexing_in_process', indexed_stats)
    if deficit:
        with pytest.raises(AssertionError, match='Database statistics do not match'):
            await parity._run_database_parity_e2e(tmp_path)
    else:
        await parity._run_database_parity_e2e(tmp_path)
    assert set(indexed_backends) == {'kuzudb', 'ladybugdb', 'falkordb', 'neo4j'}
