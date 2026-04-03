from pathlib import Path

from codegraphcontext.core.watcher import RepositoryEventHandler


class _FakeGraphBuilder:
    def __init__(self):
        self.parsers = {".ts": "typescript"}
        self._symbol_updates = {}
        self.pre_scan_calls = []

    def pre_scan_files_to_symbol_index(self, files):
        normalized = [str(Path(file).resolve()) for file in files]
        self.pre_scan_calls.append(normalized)
        return {
            path: set(self._symbol_updates.get(path, set()))
            for path in normalized
        }


def test_refresh_imports_cache_replaces_only_changed_file_symbols(temp_test_dir, monkeypatch):
    monkeypatch.setattr("codegraphcontext.core.watcher.get_config_value", lambda _key: "")

    provider = temp_test_dir / "provider.ts"
    consumer = temp_test_dir / "consumer.ts"
    provider.write_text("export const provider = 1;\n", encoding="utf-8")
    consumer.write_text("export const consumer = 2;\n", encoding="utf-8")

    graph_builder = _FakeGraphBuilder()
    handler = RepositoryEventHandler(graph_builder, temp_test_dir, perform_initial_scan=False)

    provider_path = str(provider.resolve())
    consumer_path = str(consumer.resolve())
    handler.imports_map = {
        "ProviderOld": [provider_path],
        "ConsumerStable": [consumer_path],
    }
    handler.file_symbol_index = {
        provider_path: {"ProviderOld"},
        consumer_path: {"ConsumerStable"},
    }
    graph_builder._symbol_updates = {
        provider_path: {"ProviderNew", "ProviderHelper"},
    }

    handler._refresh_imports_cache([provider_path])

    assert graph_builder.pre_scan_calls == [[provider_path]]
    assert handler.imports_map == {
        "ConsumerStable": [consumer_path],
        "ProviderHelper": [provider_path],
        "ProviderNew": [provider_path],
    }
    assert handler.file_symbol_index == {
        provider_path: {"ProviderNew", "ProviderHelper"},
        consumer_path: {"ConsumerStable"},
    }


def test_refresh_imports_cache_removes_deleted_file_symbols(temp_test_dir, monkeypatch):
    monkeypatch.setattr("codegraphcontext.core.watcher.get_config_value", lambda _key: "")

    provider = temp_test_dir / "provider.ts"
    provider.write_text("export const provider = 1;\n", encoding="utf-8")

    graph_builder = _FakeGraphBuilder()
    handler = RepositoryEventHandler(graph_builder, temp_test_dir, perform_initial_scan=False)

    provider_path = str(provider.resolve())
    handler.imports_map = {"ProviderOld": [provider_path]}
    handler.file_symbol_index = {provider_path: {"ProviderOld"}}

    provider.unlink()
    handler._refresh_imports_cache([provider_path])

    assert graph_builder.pre_scan_calls == []
    assert handler.imports_map == {}
    assert handler.file_symbol_index == {}
