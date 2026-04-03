from pathlib import Path

from codegraphcontext.tools.graph_builder import GraphBuilder


class _FakeSession:
    def __init__(self, recorder):
        self.recorder = recorder

    def __enter__(self):
        self.recorder["entered_sessions"].append(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.recorder["exited_sessions"].append(self)
        return False


class _FakeDriver:
    def __init__(self, recorder):
        self.recorder = recorder

    def session(self):
        self.recorder["session_calls"] += 1
        return _FakeSession(self.recorder)


def test_update_files_in_graph_reuses_single_session_for_multiple_files(temp_test_dir):
    file_a = temp_test_dir / "a.ts"
    file_b = temp_test_dir / "b.ts"
    file_a.write_text("export const a = 1;\n", encoding="utf-8")
    file_b.write_text("export const b = 2;\n", encoding="utf-8")

    recorder = {
        "session_calls": 0,
        "entered_sessions": [],
        "exited_sessions": [],
        "deleted": [],
        "added": [],
    }

    builder = GraphBuilder.__new__(GraphBuilder)
    builder.driver = _FakeDriver(recorder)

    def fake_parse_file(repo_path, path):
        return {
            "path": str(Path(path).resolve()),
            "repo_path": str(Path(repo_path).resolve()),
            "functions": [],
            "classes": [],
            "variables": [],
            "interfaces": [],
            "macros": [],
            "structs": [],
            "enums": [],
            "unions": [],
            "records": [],
            "properties": [],
            "traits": [],
            "modules": [],
            "module_inclusions": [],
            "imports": [],
            "function_calls": [],
            "lang": "typescript",
            "is_dependency": False,
        }

    def fake_delete_file_from_graph(path, session=None):
        recorder["deleted"].append((str(Path(path).resolve()), session))

    def fake_add_file_to_graph(file_data, repo_name, imports_map, session=None):
        recorder["added"].append((file_data["path"], repo_name, session, imports_map))

    builder.parse_file = fake_parse_file
    builder.delete_file_from_graph = fake_delete_file_from_graph
    builder.add_file_to_graph = fake_add_file_to_graph

    results = builder.update_files_in_graph([file_a, file_b], temp_test_dir, {"Stable": ["x.ts"]})

    assert recorder["session_calls"] == 1
    assert len(recorder["entered_sessions"]) == 1
    assert recorder["entered_sessions"] == recorder["exited_sessions"]

    session = recorder["entered_sessions"][0]
    assert recorder["deleted"] == [
        (str(file_a.resolve()), session),
        (str(file_b.resolve()), session),
    ]
    assert recorder["added"] == [
        (str(file_a.resolve()), temp_test_dir.name, session, {"Stable": ["x.ts"]}),
        (str(file_b.resolve()), temp_test_dir.name, session, {"Stable": ["x.ts"]}),
    ]
    assert results[str(file_a.resolve())]["path"] == str(file_a.resolve())
    assert results[str(file_b.resolve())]["path"] == str(file_b.resolve())
