import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import codegraphcontext.core as core
from codegraphcontext.core import legacy_kuzu_migration as migration


@pytest.fixture(autouse=True)
def isolate_migration_state(monkeypatch, tmp_path):
    """Never let migration tests inspect the developer's actual home."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(core, "_KUZU_MIGRATION_PROBED_PATHS", set())
    monkeypatch.setattr(migration, "_get_config_value", lambda _key: None)


def _non_empty_store(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "graph.data").write_text("legacy", encoding="utf-8")
    return path


def test_source_discovery_prefers_explicit_then_environment(monkeypatch, tmp_path):
    explicit = _non_empty_store(tmp_path / "explicit")
    environment = _non_empty_store(tmp_path / "environment")
    monkeypatch.setenv("KUZUDB_PATH", str(environment))

    assert migration.find_legacy_kuzudb_source(explicit_source_path=str(explicit)) == explicit
    assert migration.find_legacy_kuzudb_source() == environment


def test_source_discovery_finds_sibling_without_reading_real_home(monkeypatch, tmp_path):
    target = tmp_path / "db" / "ladybugdb"
    source = _non_empty_store(tmp_path / "db" / "kuzudb")
    monkeypatch.delenv("KUZUDB_PATH", raising=False)

    assert migration.find_legacy_kuzudb_source(str(target)) == source


def test_source_discovery_honors_a_custom_config_path(monkeypatch, tmp_path):
    configured_source = _non_empty_store(tmp_path / "configured-kuzudb")
    monkeypatch.delenv("KUZUDB_PATH", raising=False)
    monkeypatch.setattr(migration, "_get_config_value", lambda _key: str(configured_source))

    assert migration.find_legacy_kuzudb_source(str(tmp_path / "other" / "ladybugdb")) == configured_source


def test_resolved_target_does_not_probe_an_unrelated_global_store(monkeypatch, tmp_path):
    global_source = _non_empty_store(tmp_path / "home" / ".codegraphcontext" / "global" / "db" / "kuzudb")
    monkeypatch.delenv("KUZUDB_PATH", raising=False)
    monkeypatch.setattr(migration, "_get_config_value", lambda _key: str(global_source))

    assert migration.find_legacy_kuzudb_source(str(tmp_path / "other" / "ladybugdb")) is None
    assert migration.find_legacy_kuzudb_source() == global_source


class _CountSession:
    def __init__(self, count=None, error=None):
        self.count = count
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, _query):
        if self.error:
            raise self.error
        record = None if self.count is None else {"count": self.count}
        return SimpleNamespace(single=lambda: record)


def _manager_with_session(session, backend="ladybugdb"):
    driver = SimpleNamespace(session=lambda: session)
    return SimpleNamespace(
        get_driver=lambda: driver,
        get_backend_type=lambda: backend,
    )


@pytest.mark.parametrize(("count", "expected"), [(None, False), (0, False), ("0", False), (1, True)])
def test_target_preflight_interprets_count(count, expected):
    assert migration._has_graph_data(_manager_with_session(_CountSession(count=count))) is expected


def test_target_preflight_fails_closed():
    manager = _manager_with_session(_CountSession(error=RuntimeError("unavailable")))

    assert migration._has_graph_data(manager) is True


def test_migration_exports_then_imports_through_selected_manager(monkeypatch, tmp_path):
    source = _non_empty_store(tmp_path / "kuzudb")
    target_manager = _manager_with_session(_CountSession(count=0), backend="falkordb")
    imported = []

    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda **_kwargs: source,
    )
    monkeypatch.setattr(
        migration,
        "_export_legacy_kuzu_bundle_in_subprocess",
        lambda _source, bundle: imported.append(("export", _source, bundle)) or (2, 1),
    )
    fake_bundle_module = ModuleType("codegraphcontext.core.cgc_bundle")

    class FakeBundle:
        def __init__(self, manager):
            assert manager is target_manager

        def import_from_bundle(self, bundle_path, clear_existing=False):
            imported.append(("import", bundle_path, clear_existing))
            return True, "imported"

    fake_bundle_module.CGCBundle = FakeBundle
    monkeypatch.setitem(sys.modules, "codegraphcontext.core.cgc_bundle", fake_bundle_module)

    success, message = migration.migrate_legacy_kuzudb_to_manager(target_manager)

    assert success is True
    assert "into falkordb" in message
    assert [operation[0] for operation in imported] == ["export", "import"]


def test_migration_reports_an_actionable_missing_driver(monkeypatch, tmp_path):
    source = _non_empty_store(tmp_path / "kuzudb")
    monkeypatch.setattr(migration, "find_legacy_kuzudb_source", lambda **_kwargs: source)
    monkeypatch.setattr(migration, "_has_graph_data", lambda _manager: False)
    monkeypatch.setattr(
        migration,
        "_export_legacy_kuzu_bundle_in_subprocess",
        lambda *_args: (_ for _ in ()).throw(migration.LegacyKuzuUnavailableError("missing")),
    )

    success, message = migration.migrate_legacy_kuzudb_to_manager(SimpleNamespace())

    assert success is False
    assert "archived upstream" in message
    assert "CGC_KUZU_MIGRATION_PYTHON" in message
    assert "Docker" in message
    assert "Failed building wheel for kuzu" in message


def test_export_uses_only_the_configured_migration_interpreter(monkeypatch, tmp_path):
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='CGC_KUZU_EXPORT_RESULT:{"node_count": 2, "edge_count": 3}\n',
        stderr="",
    )
    calls = []
    monkeypatch.setenv("CGC_KUZU_MIGRATION_PYTHON", "/opt/kuzu-python")
    monkeypatch.setattr(
        migration.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or completed,
    )

    counts = migration._export_legacy_kuzu_bundle_in_subprocess(
        tmp_path / "kuzudb",
        tmp_path / "legacy.cgc",
    )

    assert counts == (2, 3)
    assert calls[0][0][0] == "/opt/kuzu-python"
    assert calls[0][0][1] == str(Path(migration.__file__).resolve())


def test_export_worker_does_not_import_the_target_driver(monkeypatch, tmp_path):
    driver_dir = tmp_path / "driver"
    driver_dir.mkdir()
    (driver_dir / "kuzu.py").write_text(
        """
class Database:
    def __init__(self, path):
        self.path = path

class Connection:
    def __init__(self, database):
        self.database = database

    def execute(self, query):
        source = {"_id": "source", "name": "source"}
        target = {"_id": "target", "name": "target"}
        if "labels(n)" in query:
            return [[source, ["Function"]], [target, ["Function"]]]
        assert "type(" not in query
        relationship = {"_src": "source", "_dst": "target", "_label": "CALLS", "line_number": 4}
        return [[source, relationship, target]]
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(driver_dir))
    monkeypatch.setenv("CGC_KUZU_MIGRATION_PYTHON", sys.executable)
    bundle_path = tmp_path / "legacy.cgc"

    assert migration._export_legacy_kuzu_bundle_in_subprocess(tmp_path / "kuzudb", bundle_path) == (2, 1)
    with zipfile.ZipFile(bundle_path) as bundle:
        assert len(bundle.read("nodes.jsonl").splitlines()) == 2
        assert len(bundle.read("edges.jsonl").splitlines()) == 1


def test_probe_runs_once_per_normalized_backend_path(monkeypatch):
    calls = []
    manager = SimpleNamespace(
        db_path="/target/ladybugdb",
        get_backend_type=lambda: "ladybugdb",
    )
    monkeypatch.setattr(
        migration,
        "migrate_legacy_kuzudb_to_manager",
        lambda _manager, **kwargs: calls.append(kwargs) or (False, "No legacy KuzuDB store found; skipping migration."),
    )

    core._maybe_migrate_legacy_kuzudb(manager, "/target/ladybugdb")
    core._maybe_migrate_legacy_kuzudb(manager, "/target/./ladybugdb")
    core._maybe_migrate_legacy_kuzudb(manager, "/another/ladybugdb")

    assert [call["target_db_path"] for call in calls] == ["/target/ladybugdb", "/another/ladybugdb"]


def _install_fake_ladybug(monkeypatch):
    created = []
    module = ModuleType("codegraphcontext.core.database_ladybug")

    class FakeLadybugManager:
        def __init__(self, db_path=None):
            self.db_path = db_path
            created.append(self)

        def get_backend_type(self):
            return "ladybugdb"

    module.LadybugDBManager = FakeLadybugManager
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return created


def test_explicit_missing_kuzu_uses_distinct_ladybug_path_and_source(monkeypatch, tmp_path):
    created = _install_fake_ladybug(monkeypatch)
    calls = []
    source = str(tmp_path / "custom-store")
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "kuzudb")
    monkeypatch.setattr(core, "_is_kuzudb_available", lambda: False)
    monkeypatch.setattr(core, "_is_ladybugdb_available", lambda: True)
    monkeypatch.setattr(
        core,
        "_maybe_migrate_legacy_kuzudb",
        lambda manager, path, **kwargs: calls.append((manager, path, kwargs)),
    )

    manager = core.get_database_manager(source)

    assert manager is created[0]
    assert manager.db_path == f"{source}.ladybugdb"
    assert calls == [(manager, f"{source}.ladybugdb", {"source_db_path": source})]


def test_implicit_selection_never_chooses_installed_kuzu(monkeypatch, tmp_path):
    created = _install_fake_ladybug(monkeypatch)
    monkeypatch.delenv("CGC_RUNTIME_DB_TYPE", raising=False)
    monkeypatch.delenv("DEFAULT_DATABASE", raising=False)
    monkeypatch.delenv("FALKORDB_HOST", raising=False)
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    monkeypatch.setattr(core, "_is_kuzudb_available", lambda: True)
    monkeypatch.setattr(core, "_is_ladybugdb_available", lambda: True)
    monkeypatch.setattr(core, "_maybe_migrate_legacy_kuzudb", lambda *_args, **_kwargs: None)

    manager = core.get_database_manager(str(tmp_path / "db" / "kuzudb"))

    assert manager is created[0]
    assert manager.db_path == str(tmp_path / "db" / "ladybugdb")


def test_write_migration_bundle_matches_bundle_contract(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "nodes.jsonl").write_text('{"_id":"n1","_labels":["File"]}\n', encoding="utf-8")
    (bundle_dir / "edges.jsonl").write_text("", encoding="utf-8")
    bundle_path = tmp_path / "legacy.cgc"

    migration._write_migration_bundle(bundle_dir, bundle_path, tmp_path / "kuzudb", 1, 0)

    with zipfile.ZipFile(bundle_path) as bundle:
        assert sorted(bundle.namelist()) == ["edges.jsonl", "metadata.json", "nodes.jsonl", "schema.json"]
        metadata = json.loads(bundle.read("metadata.json"))
    assert metadata["graph_metrics"] == {"total_nodes": 1, "total_edges": 0}
