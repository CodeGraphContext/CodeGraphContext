import json
import sys
import zipfile
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest

neo4j = ModuleType("neo4j")
neo4j.Driver = object
neo4j.GraphDatabase = SimpleNamespace(driver=lambda *args, **kwargs: None)
sys.modules.setdefault("neo4j", neo4j)

import codegraphcontext.core as core  # noqa: E402
from codegraphcontext.core import (  # noqa: E402
    legacy_kuzu_migration as migration,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self, count=None, raises=False):
        self.count = count
        self.raises = raises

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, query):
        if self.raises:
            raise RuntimeError("graph unavailable")
        return SimpleNamespace(
            single=lambda: (
                None if self.count is None else {"count": self.count}
            )
        )


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


class FakeNode:
    def __init__(self, element_id, properties):
        self.element_id = element_id
        self.properties = properties


class FakeRel:
    def __init__(self, properties):
        self._properties = properties


class FakeConnection:
    def __init__(self, db):
        self.db = db

    def execute(self, query):
        source = FakeNode(
            "src",
            {
                "_id": "src",
                "name": "source",
                "optional": None,
                "_label": "Old",
            },
        )
        target = SimpleNamespace(id=42, _properties={"name": "target"})
        if "labels(n)" in query:
            return FakeResult(
                [
                    {"n": source, "labels": "CodeObject"},
                    [target, ["File", "Legacy"]],
                ]
            )
        return FakeResult(
            [
                {
                    "n": source,
                    "r": FakeRel(
                        {
                            "_src": "src",
                            "_dst": "target",
                            "_id": "rel-1",
                            "_label": "CALLS",
                            "weight": 3,
                            "drop": None,
                        }
                    ),
                    "m": target,
                    "rel_type": "CALLS",
                }
            ]
        )


def _non_empty_legacy_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "graph.data").write_text("legacy", encoding="utf-8")
    return path


def test_find_legacy_kuzudb_source_prefers_sibling_directory(
    tmp_path,
    monkeypatch,
):
    """Find the old default layout when users never configured Kuzu."""
    target = tmp_path / "db" / "falkordb"
    source = _non_empty_legacy_dir(tmp_path / "db" / "kuzudb")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("KUZUDB_PATH", raising=False)
    monkeypatch.setattr(migration, "_get_config_value", lambda key: None)

    assert migration.find_legacy_kuzudb_source(str(target)) == source


def test_find_legacy_kuzudb_source_prefers_env_over_config_and_sibling(
    tmp_path,
    monkeypatch,
):
    """Honor the most explicit legacy path first."""
    env_source = _non_empty_legacy_dir(tmp_path / "env" / "kuzudb")
    config_source = _non_empty_legacy_dir(tmp_path / "config" / "kuzudb")
    target = tmp_path / "db" / "falkordb"
    _non_empty_legacy_dir(tmp_path / "db" / "kuzudb")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KUZUDB_PATH", str(env_source))
    monkeypatch.setattr(
        migration,
        "_get_config_value",
        lambda key: str(config_source),
    )

    assert migration.find_legacy_kuzudb_source(str(target)) == env_source


def test_find_legacy_kuzudb_source_ignores_empty_and_target_paths(
    tmp_path,
    monkeypatch,
):
    """Avoid empty directories and migration pointed at itself."""
    target = tmp_path / "db" / "falkordb"
    empty_env_source = tmp_path / "empty" / "kuzudb"
    empty_env_source.mkdir(parents=True)
    config_source = _non_empty_legacy_dir(tmp_path / "config" / "kuzudb")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KUZUDB_PATH", str(empty_env_source))
    monkeypatch.setattr(
        migration,
        "_get_config_value",
        lambda key: str(config_source),
    )

    assert migration.find_legacy_kuzudb_source(str(target)) == config_source

    monkeypatch.setenv("KUZUDB_PATH", str(target))
    monkeypatch.setattr(migration, "_get_config_value", lambda key: None)

    assert migration.find_legacy_kuzudb_source(str(target)) is None


def test_migrate_legacy_kuzudb_to_manager_uses_target_backend(
    monkeypatch,
    tmp_path,
):
    """Import through the resolved manager so configured targets win."""
    source = tmp_path / "kuzudb"
    source.mkdir()

    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda target_db_path=None: source,
    )
    monkeypatch.setattr(
        migration,
        "_has_graph_data",
        lambda target_manager: False,
    )
    monkeypatch.setattr(
        migration,
        "_export_legacy_kuzu_bundle",
        lambda *args, **kwargs: (2, 3),
    )
    monkeypatch.setattr(
        migration,
        "_write_migration_bundle",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "kuzu",
        SimpleNamespace(Database=object, Connection=object),
    )

    fake_bundle_module = SimpleNamespace(
        CGCBundle=lambda target_manager: SimpleNamespace(
            import_from_bundle=lambda bundle_path, clear_existing=False: (
                True,
                "imported",
            )
        )
    )
    monkeypatch.setitem(
        sys.modules,
        "codegraphcontext.core.cgc_bundle",
        fake_bundle_module,
    )

    target_manager = SimpleNamespace(get_backend_type=lambda: "falkordb")
    success, message = migration.migrate_legacy_kuzudb_to_manager(
        target_manager,
        target_db_path=str(tmp_path / "db" / "falkordb"),
    )

    assert success is True
    assert "falkordb" in message


def test_migrate_legacy_kuzudb_to_manager_reports_missing_kuzu(
    monkeypatch,
    tmp_path,
):
    """Tell users why Kuzu needs temporary old Python."""
    source = _non_empty_legacy_dir(tmp_path / "kuzudb")

    def fake_import(name, *args, **kwargs):
        if name == "kuzu":
            raise ImportError("no kuzu")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda target_db_path=None: source,
    )
    monkeypatch.setattr(
        migration,
        "_has_graph_data",
        lambda target_manager: False,
    )
    monkeypatch.setattr("builtins.__import__", fake_import)

    success, message = migration.migrate_legacy_kuzudb_to_manager(
        SimpleNamespace()
    )

    assert success is False
    assert "kuzu' package is not installed" in message
    assert "archived upstream" in message
    assert "Python 3.14+" in message
    assert "Failed building wheel for kuzu" in message
    assert str(source) in message


def test_migrate_legacy_kuzudb_to_manager_reports_missing_bundle_importer(
    monkeypatch,
    tmp_path,
):
    """Fail before export if the shared bundle importer is unavailable."""
    source = _non_empty_legacy_dir(tmp_path / "kuzudb")

    def fake_import(name, *args, **kwargs):
        if name == "codegraphcontext.core.cgc_bundle":
            raise RuntimeError("bundle unavailable")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda target_db_path=None: source,
    )
    monkeypatch.setattr(
        migration,
        "_has_graph_data",
        lambda target_manager: False,
    )
    monkeypatch.setitem(
        sys.modules,
        "kuzu",
        SimpleNamespace(Database=object, Connection=object),
    )
    monkeypatch.setattr("builtins.__import__", fake_import)

    success, message = migration.migrate_legacy_kuzudb_to_manager(
        SimpleNamespace()
    )

    assert success is False
    assert "Could not load bundle importer" in message
    assert "bundle unavailable" in message


def test_migrate_legacy_kuzudb_to_manager_returns_import_failure(
    monkeypatch,
    tmp_path,
):
    """Preserve target-backend import errors."""
    source = _non_empty_legacy_dir(tmp_path / "kuzudb")

    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda target_db_path=None: source,
    )
    monkeypatch.setattr(
        migration,
        "_has_graph_data",
        lambda target_manager: False,
    )
    monkeypatch.setattr(
        migration,
        "_export_legacy_kuzu_bundle",
        lambda *args, **kwargs: (1, 0),
    )
    monkeypatch.setattr(
        migration,
        "_write_migration_bundle",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "kuzu",
        SimpleNamespace(Database=object, Connection=object),
    )
    monkeypatch.setitem(
        sys.modules,
        "codegraphcontext.core.cgc_bundle",
        SimpleNamespace(
            CGCBundle=lambda target_manager: SimpleNamespace(
                import_from_bundle=lambda bundle_path, clear_existing=False: (
                    False,
                    "target refused import",
                )
            )
        ),
    )

    success, message = migration.migrate_legacy_kuzudb_to_manager(
        SimpleNamespace()
    )

    assert success is False
    assert message == "target refused import"


def test_migrate_legacy_kuzudb_to_manager_skips_if_target_has_data(
    monkeypatch,
):
    """Do not merge legacy data into a populated target."""
    monkeypatch.setattr(
        migration,
        "find_legacy_kuzudb_source",
        lambda target_db_path=None: Path("/tmp/kuzudb"),
    )
    monkeypatch.setattr(
        migration,
        "_has_graph_data",
        lambda target_manager: True,
    )

    target_manager = SimpleNamespace(get_backend_type=lambda: "ladybugdb")
    success, message = migration.migrate_legacy_kuzudb_to_manager(
        target_manager
    )

    assert success is False
    assert "already contains data" in message


def test_maybe_migrate_legacy_kuzudb_uses_manager_db_path(monkeypatch):
    """Use the manager path so sibling legacy stores can be discovered."""
    calls = []

    def fake_migrate(target_manager, target_db_path=None):
        calls.append((target_manager, target_db_path))
        return False, "No legacy KuzuDB store found; skipping migration."

    target_manager = SimpleNamespace(db_path="/resolved/default/falkordb")
    monkeypatch.setattr(
        migration,
        "migrate_legacy_kuzudb_to_manager",
        fake_migrate,
    )

    core._maybe_migrate_legacy_kuzudb(target_manager, db_path=None)

    assert calls == [(target_manager, "/resolved/default/falkordb")]


def test_maybe_migrate_legacy_kuzudb_prefers_explicit_db_path(monkeypatch):
    """Keep explicit db_path authoritative."""
    calls = []

    def fake_migrate(target_manager, target_db_path=None):
        calls.append((target_manager, target_db_path))
        return False, "No legacy KuzuDB store found; skipping migration."

    target_manager = SimpleNamespace(db_path="/resolved/default/falkordb")
    monkeypatch.setattr(
        migration,
        "migrate_legacy_kuzudb_to_manager",
        fake_migrate,
    )

    core._maybe_migrate_legacy_kuzudb(
        target_manager,
        db_path="/configured/falkordb",
    )

    assert calls == [(target_manager, "/configured/falkordb")]


def _install_backend_module(monkeypatch, module_name, class_name):
    created = []
    module = ModuleType(module_name)

    class FakeManager:
        def __init__(self, db_path=None):
            self.db_path = db_path
            self.backend_module = module_name
            created.append(self)

        def get_driver(self):
            return object()

    setattr(module, class_name, FakeManager)
    monkeypatch.setitem(sys.modules, module_name, module)
    return created


@pytest.mark.parametrize(
    (
        "db_type",
        "module_name",
        "class_name",
        "env",
    ),
    [
        (
            "ladybugdb",
            "codegraphcontext.core.database_ladybug",
            "LadybugDBManager",
            {},
        ),
        (
            "falkordb-remote",
            "codegraphcontext.core.database_falkordb_remote",
            "FalkorDBRemoteManager",
            {"FALKORDB_HOST": "localhost"},
        ),
        (
            "neo4j",
            "codegraphcontext.core.database",
            "DatabaseManager",
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USERNAME": "neo4j",
                "NEO4J_PASSWORD": "pw",
            },
        ),
        (
            "nornic",
            "codegraphcontext.core.database_nornic",
            "NornicDBManager",
            {
                "NORNIC_URI": "nornic://localhost",
                "NORNIC_USERNAME": "nornic",
                "NORNIC_PASSWORD": "pw",
            },
        ),
    ],
)
def test_get_database_manager_runs_kuzu_migration_for_explicit_backends(
    monkeypatch,
    tmp_path,
    db_type,
    module_name,
    class_name,
    env,
):
    """Run migration against the backend the user explicitly selected."""
    calls = []
    created = _install_backend_module(monkeypatch, module_name, class_name)
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", db_type)
    monkeypatch.delenv("DEFAULT_DATABASE", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(core, "_is_ladybugdb_available", lambda: True)
    monkeypatch.setattr(
        core,
        "_maybe_migrate_legacy_kuzudb",
        lambda manager, db_path: calls.append((manager, db_path)),
    )

    manager = core.get_database_manager(db_path=str(tmp_path / db_type))

    assert manager is created[0]
    assert calls == [(manager, str(tmp_path / db_type))]


def test_get_database_manager_runs_kuzu_migration_for_explicit_falkordb(
    monkeypatch,
    tmp_path,
):
    """Keep FalkorDB Lite as the migration target when it is selected."""
    calls = []
    created = _install_backend_module(
        monkeypatch,
        "codegraphcontext.core.database_falkordb",
        "FalkorDBManager",
    )
    sys.modules[
        "codegraphcontext.core.database_falkordb"
    ].FalkorDBUnavailableError = RuntimeError
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "falkordb")
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: True)
    monkeypatch.setattr(
        core,
        "_maybe_migrate_legacy_kuzudb",
        lambda manager, db_path: calls.append((manager, db_path)),
    )

    manager = core.get_database_manager(db_path=str(tmp_path / "falkordb"))

    assert manager is created[0]
    assert calls == [(manager, str(tmp_path / "falkordb"))]


def test_get_database_manager_migrates_to_ladybug_fallback_path(
    monkeypatch,
    tmp_path,
):
    """When FalkorDB is unavailable, migrate into the Ladybug fallback store."""
    calls = []
    created = _install_backend_module(
        monkeypatch,
        "codegraphcontext.core.database_ladybug",
        "LadybugDBManager",
    )
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "falkordb")
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    monkeypatch.setattr(core, "_is_ladybugdb_available", lambda: True)
    monkeypatch.setattr(core, "_is_neo4j_configured", lambda: False)
    monkeypatch.setattr(core, "_is_nornic_configured", lambda: False)
    monkeypatch.setattr(
        core,
        "_maybe_migrate_legacy_kuzudb",
        lambda manager, db_path: calls.append((manager, db_path)),
    )

    manager = core.get_database_manager(db_path=str(tmp_path / "db" / "falkordb"))

    assert manager is created[0]
    assert manager.db_path == str(tmp_path / "db" / "ladybugdb")
    assert calls == [(manager, str(tmp_path / "db" / "ladybugdb"))]


def test_get_database_manager_migrates_to_default_ladybug_backend(
    monkeypatch,
    tmp_path,
):
    """Cover the zero-config replacement path after KuzuDB removal."""
    calls = []
    created = _install_backend_module(
        monkeypatch,
        "codegraphcontext.core.database_ladybug",
        "LadybugDBManager",
    )
    monkeypatch.delenv("CGC_RUNTIME_DB_TYPE", raising=False)
    monkeypatch.delenv("DEFAULT_DATABASE", raising=False)
    monkeypatch.delenv("FALKORDB_HOST", raising=False)
    monkeypatch.setattr(core, "is_falkordb_usable", lambda: False)
    monkeypatch.setattr(core, "_is_ladybugdb_available", lambda: True)
    monkeypatch.setattr(
        core,
        "_maybe_migrate_legacy_kuzudb",
        lambda manager, db_path: calls.append((manager, db_path)),
    )

    manager = core.get_database_manager(db_path=str(tmp_path / "db" / "kuzudb"))

    assert manager is created[0]
    assert manager.db_path == str(tmp_path / "db" / "kuzudb")
    assert calls == [(manager, str(tmp_path / "db" / "kuzudb"))]


@pytest.mark.parametrize(
    ("record_count", "expected"),
    [
        (None, False),
        (0, False),
        ("0", False),
        (1, True),
        ("2", True),
        ("unknown", True),
    ],
)
def test_has_graph_data_interprets_count_results(record_count, expected):
    """Treat only non-zero target graphs as occupied."""
    target_manager = SimpleNamespace(
        get_driver=lambda: FakeDriver(FakeSession(count=record_count))
    )

    assert migration._has_graph_data(target_manager) is expected


def test_has_graph_data_treats_preflight_errors_as_empty():
    """Keep startup usable if a backend cannot answer preflight."""
    target_manager = SimpleNamespace(
        get_driver=lambda: FakeDriver(FakeSession(raises=True))
    )

    assert migration._has_graph_data(target_manager) is False


def test_write_migration_bundle_creates_importable_archive(tmp_path):
    """Write the bundle shape the normal importer expects."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "nodes.jsonl").write_text(
        '{"_id":"n1"}\n',
        encoding="utf-8",
    )
    (bundle_dir / "edges.jsonl").write_text(
        '{"from":"n1","to":"n2","type":"LINKS"}\n',
        encoding="utf-8",
    )
    bundle_path = tmp_path / "legacy-kuzudb.cgc"

    migration._write_migration_bundle(
        bundle_dir,
        bundle_path,
        tmp_path / "kuzudb",
        node_count=1,
        edge_count=1,
    )

    with zipfile.ZipFile(bundle_path) as zipf:
        assert sorted(zipf.namelist()) == [
            "edges.jsonl",
            "metadata.json",
            "nodes.jsonl",
            "schema.json",
        ]
        metadata = json.loads(zipf.read("metadata.json").decode("utf-8"))
        schema = json.loads(zipf.read("schema.json").decode("utf-8"))

    assert metadata["graph_metrics"] == {"total_nodes": 1, "total_edges": 1}
    assert metadata["repo"].startswith("legacy-kuzudb:")
    assert schema["constraints"] == []


def test_export_legacy_kuzu_bundle_normalizes_rows_and_properties(tmp_path):
    """Normalize Kuzu row variants into backend-neutral records."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    kuzu_module = SimpleNamespace(
        Database=lambda path: {"path": path},
        Connection=FakeConnection,
    )

    node_count, edge_count = migration._export_legacy_kuzu_bundle(
        tmp_path / "kuzudb",
        bundle_dir,
        kuzu_module,
    )

    nodes = [
        json.loads(line)
        for line in (bundle_dir / "nodes.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    edges = [
        json.loads(line)
        for line in (bundle_dir / "edges.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert node_count == 2
    assert edge_count == 1
    assert nodes[0] == {
        "_id": "src",
        "name": "source",
        "_labels": ["CodeObject"],
    }
    assert nodes[1]["_id"] == "42"
    assert nodes[1]["_labels"] == ["File", "Legacy"]
    assert edges == [
        {
            "from": "src",
            "to": "target",
            "type": "CALLS",
            "properties": {"weight": 3},
        }
    ]
