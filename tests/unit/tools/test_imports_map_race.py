import pathlib
import threading

from codegraphcontext.tools.indexing.resolution import calls as calls_module


def test_language_import_filter_snapshots_imports_map_during_concurrent_update(
    monkeypatch,
):
    suffix_started = threading.Event()
    mutated = threading.Event()

    class SlowPath:
        def __init__(self, value):
            self._path = pathlib.Path(value)

        def resolve(self):
            return self

        def as_posix(self):
            return self._path.as_posix()

        @property
        def suffix(self):
            suffix_started.set()
            assert mutated.wait(2)
            return self._path.suffix

    monkeypatch.setattr(calls_module, "Path", SlowPath)

    imports_map = {
        "ExistingSymbol": ["/repo/deps/existing.py"],
    }
    all_file_data = [
        {
            "path": "/repo/caller.py",
            "lang": "python",
            "functions": [],
            "classes": [],
            "function_calls": [],
            "imports": [],
        }
    ]

    def mutate_imports_map():
        assert suffix_started.wait(2)
        imports_map["NewSymbol"] = ["/repo/deps/new_symbol.py"]
        mutated.set()

    mutator = threading.Thread(target=mutate_imports_map)
    mutator.start()
    try:
        calls_module.build_function_call_groups(all_file_data, imports_map)
    finally:
        mutator.join(timeout=2)

    assert mutated.is_set()
