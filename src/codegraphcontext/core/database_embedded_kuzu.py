# src/codegraphcontext/core/database_embedded_kuzu.py
"""
Shared embedded graph-database layer for Kùzu-dialect engines (KùzuDB, LadybugDB).

Backend-specific modules (``database_kuzu``, ``database_ladybug``) supply an
``EmbeddedBackendSpec`` and thin manager subclass; all Cypher translation,
connection pooling, and schema logic lives here.
"""
import gc
import importlib
import os
import queue
import time
import threading
import re
import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, ClassVar

from codegraphcontext.core.graph_query import GraphQueryInterface
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger


@dataclass(frozen=True)
class EmbeddedBackendSpec:
    """Configuration for a Kùzu-dialect embedded graph backend."""

    backend_id: str
    python_module: str
    display_name: str
    path_env_var: str
    config_key: str
    default_dir: str
    install_hint: str


class EmbeddedCompatState:
    """
    Shared fail-fast state for unsupported query types (fulltext/module_deps).
    Lives on the manager (long-lived) so that disabling a query type sticks
    across sessions instead of resetting with every new session wrapper.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.disabled_query_types = set()
        self.logged_disabled_query_types = set()


class EmbeddedGraphManager(GraphQueryInterface):
    """
    Manages an embedded Kùzu-dialect database connection as a per-subclass singleton.
    """

    BACKEND_SPEC: ClassVar[EmbeddedBackendSpec]

    _instance = None
    _db = None
    _pool = None
    _lock = threading.Lock()         # Guards singleton initialisation only.
    _write_lock = threading.RLock()  # Serialises every write query (reentrant for fallback).
    _query_lock = threading.RLock()  # Kept for backward compat / legacy wrappers if any.
    _compat_state = EmbeddedCompatState()  # Shared across all sessions of this process.

    def __new__(cls, *args, **kwargs):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmbeddedGraphManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes the manager with default database path or explicit overrides.
        """
        spec = self.BACKEND_SPEC
        try:
            from codegraphcontext.cli.config_manager import get_config_value
            config_db_path = get_config_value(spec.config_key)
        except Exception:
            config_db_path = None

        new_db_path = db_path or os.getenv(
            spec.path_env_var,
            config_db_path or str(Path.home() / '.codegraphcontext' / 'global' / spec.default_dir)
        )

        if hasattr(self, '_initialized') and getattr(self, 'db_path', None) == new_db_path:
            return

        if hasattr(self, '_initialized') and getattr(self, 'db_path', None) != new_db_path:
            self.close_driver()

        self._initialized = False
        self.name = spec.backend_id
        self.db_path = new_db_path
        os.makedirs(Path(self.db_path).parent, exist_ok=True)
        self._initialized = True

    def get_driver(self):
        """
        Gets the embedded driver. Initialises the database and connection pool.
        """
        spec = self.BACKEND_SPEC
        if self._db is None:
            with self._lock:
                if self._db is None:
                    backend = importlib.import_module(spec.python_module)
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            info_logger(f"Initializing {spec.display_name} at {self.db_path}")
                            self._db = backend.Database(self.db_path)

                            # Initialise connection pool
                            self._pool = queue.Queue()
                            # Start with 10 connections in the pool
                            for _ in range(10):
                                self._pool.put(backend.Connection(self._db))
                            
                            # Use one connection from the pool to initialise schema
                            temp_conn = self._pool.get()
                            try:
                                self._conn = temp_conn # Temporary assignment for _initialize_schema
                                self._initialize_schema()
                                self._conn = None
                            finally:
                                self._pool.put(temp_conn)

                            info_logger(f"{spec.display_name} connection established and schema verified")
                            break
                        except ImportError:
                            error_logger(f"{spec.display_name} is not installed. {spec.install_hint}")
                            raise ValueError(f"{spec.display_name} core missing.")
                        except Exception as e:
                            if "lock" in str(e).lower() and attempt < max_retries - 1:
                                wait = 0.5 * (2 ** attempt)
                                warning_logger(
                                    f"{spec.display_name} lock contention, retrying in {wait:.1f}s "
                                    f"({attempt+1}/{max_retries})..."
                                )
                                self._db = None
                                time.sleep(wait)
                            else:
                                error_logger(f"Failed to initialize {spec.display_name}: {e}")
                                raise

        return EmbeddedDriverWrapper(
            self._db,
            self._pool,
            self._write_lock,
            compat_state=type(self)._compat_state,
            display_name=spec.display_name,
            backend_id=spec.backend_id,
        )

    def _initialize_schema(self):
        """Creates Node and Rel tables if they don't exist."""
        # Using a set of helper methods to define tables
        # Kuzu's Cypher for checking tables can be limited, 
        # but we can wrap in try-except or check metadata.
        
        node_tables = [
            ("Repository", "path STRING, name STRING, is_dependency BOOLEAN, indexed_at STRING, commit_hash STRING, PRIMARY KEY (path)"),
            ("File", "path STRING, name STRING, relative_path STRING, package_name STRING, is_dependency BOOLEAN, PRIMARY KEY (path)"),
            ("Directory", "path STRING, name STRING, PRIMARY KEY (path)"),
            ("Module", "name STRING, lang STRING, full_import_name STRING, path STRING, line_number INT64, PRIMARY KEY (name)"),
            # For types with composite keys (name, path, line_number), we use a 'uid'
            ("Function", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, cyclomatic_complexity INT64, context STRING, context_type STRING, class_context STRING, class_context_line INT64, module_context STRING, is_dependency BOOLEAN, decorators STRING[], args STRING[], http_method STRING, http_path STRING, embedding DOUBLE[], PRIMARY KEY (uid)"),
            ("Class", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, node_type STRING, is_dependency BOOLEAN, decorators STRING[], PRIMARY KEY (uid)"),
            ("Variable", "uid STRING, name STRING, path STRING, line_number INT64, source STRING, docstring STRING, lang STRING, value STRING, context STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Trait", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Interface", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Macro", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Struct", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Enum", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("EnumMember", "uid STRING, name STRING, path STRING, line_number INT64, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Union", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Annotation", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Record", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Property", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Parameter", "uid STRING, name STRING, path STRING, function_line_number INT64, PRIMARY KEY (uid)"),
            ("Mixin", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Extension", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Object", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("DbTable", "name STRING, fqn STRING, datasource_name STRING, path STRING, PRIMARY KEY (name)"),
            ("Datasource", "name STRING, kind STRING, host STRING, env STRING, PRIMARY KEY (name)"),
            ("DbColumn", "name STRING, table_fqn STRING, type STRING, nullable BOOLEAN, datasource_name STRING, is_primary_key BOOLEAN, PRIMARY KEY (name, table_fqn)"),
            ("RedisKeyPattern", "pattern STRING, datasource_name STRING, key_type STRING, example_key STRING, count INT64, PRIMARY KEY (pattern, datasource_name)"),
            ("ExternalClass", "name STRING, path STRING, PRIMARY KEY (name)")
        ]
        
        # rel_tables: list of (table_name, schema, use_group)
        # use_group=True  -> CREATE REL TABLE GROUP (for multi FROM..TO bindings)
        # use_group=False -> CREATE REL TABLE          (single binding)
        rel_tables = [
            # Note: in KùzuDB, some labels (e.g. `Macro`, `Property`, `Union`) are treated as reserved
            # keywords in CREATE REL TABLE statements. We must escape them with backticks
            # or the rel table creation will fail silently, leading to runtime
            # "Binder exception: Table CONTAINS does not exist".
            ("CONTAINS", """
                FROM File TO Function, FROM File TO Class, FROM File TO Variable, FROM File TO Trait, FROM File TO Interface, 
                FROM File TO `Macro`, FROM File TO Struct, FROM File TO Enum, FROM File TO `Union`, FROM File TO Annotation, 
                FROM File TO Record, FROM File TO `Property`, FROM File TO Mixin, FROM File TO Extension, FROM File TO Module, 
                FROM File TO Object, FROM File TO EnumMember,
                FROM Repository TO Directory, FROM Directory TO Directory, FROM Directory TO File, FROM Repository TO File, 
                FROM Class TO Function, FROM Module TO Function, FROM Interface TO Function, FROM Struct TO Function, 
                FROM Record TO Function, FROM Trait TO Function, FROM Object TO Function, FROM Mixin TO Function,
                FROM Extension TO Function, FROM Class TO Class, FROM Class TO Interface, FROM Class TO Struct, 
                FROM Class TO Variable, FROM Class TO EnumMember,
                FROM Module TO Class, FROM Module TO Module, FROM `Macro` TO `Macro`, FROM Function TO Function
            """, True),
            ("CALLS", """
                FROM Function TO Function, FROM Function TO Class, FROM Function TO Interface, FROM Function TO Trait, 
                FROM Function TO Struct, FROM Function TO Enum, FROM Function TO Record, FROM Function TO `Union`,
                FROM Function TO Mixin, FROM Function TO Extension, FROM Function TO Object, FROM Function TO Parameter,
                FROM Class TO Function, FROM Class TO Class, FROM Class TO Interface, FROM Class TO Trait, 
                FROM Class TO Struct, FROM Class TO Enum, FROM Class TO Record, FROM Class TO `Union`,
                FROM Interface TO Function, FROM Interface TO Class, FROM Interface TO Interface,
                FROM Trait TO Function, FROM Trait TO Class, FROM Trait TO Interface,
                FROM Mixin TO Function, FROM Mixin TO Class, FROM Mixin TO Interface,
                FROM Extension TO Function, FROM Extension TO Class, FROM Extension TO Interface,
                FROM Object TO Function, FROM Object TO Class, FROM Object TO Interface,
                FROM `Union` TO Function, FROM `Union` TO Class, FROM `Union` TO Interface,
                FROM `Macro` TO Function, FROM `Macro` TO Class, FROM `Macro` TO Interface,
                FROM File TO Function, FROM File TO Class, FROM File TO Interface, FROM File TO Trait, 
                FROM File TO Struct, FROM File TO Enum, FROM File TO Record, FROM File TO `Union`,
                FROM Function TO File,
                FROM Variable TO Function, FROM Variable TO Class, FROM Variable TO Interface,
                line_number INT64, args STRING[], full_call_name STRING, args_key STRING, confidence DOUBLE, resolution_tier INT64, 
                confidence_label STRING, source STRING, resolution_method STRING, called_name STRING
            """, True),
            ("IMPORTS", "FROM File TO Module, alias STRING, full_import_name STRING, imported_name STRING, line_number INT64", False),
            ("INHERITS", """
                FROM Class TO Class, FROM Class TO Trait, FROM Class TO Interface, FROM Class TO Struct, FROM Class TO Enum, FROM Class TO `Union`, FROM Class TO Record, FROM Class TO Mixin, FROM Class TO Extension, FROM Class TO Module, FROM Class TO Object, FROM Class TO ExternalClass,
                FROM Trait TO Class, FROM Trait TO Trait, FROM Trait TO Interface, FROM Trait TO Struct, FROM Trait TO Enum, FROM Trait TO `Union`, FROM Trait TO Record, FROM Trait TO Mixin, FROM Trait TO Extension, FROM Trait TO Module, FROM Trait TO Object, FROM Trait TO ExternalClass,
                FROM Interface TO Class, FROM Interface TO Trait, FROM Interface TO Interface, FROM Interface TO Struct, FROM Interface TO Enum, FROM Interface TO `Union`, FROM Interface TO Record, FROM Interface TO Mixin, FROM Interface TO Extension, FROM Interface TO Module, FROM Interface TO Object, FROM Interface TO ExternalClass,
                FROM Struct TO Class, FROM Struct TO Trait, FROM Struct TO Interface, FROM Struct TO Struct, FROM Struct TO Enum, FROM Struct TO `Union`, FROM Struct TO Record, FROM Struct TO Mixin, FROM Struct TO Extension, FROM Struct TO Module, FROM Struct TO Object, FROM Struct TO ExternalClass,
                FROM Enum TO Class, FROM Enum TO Trait, FROM Enum TO Interface, FROM Enum TO Struct, FROM Enum TO Enum, FROM Enum TO `Union`, FROM Enum TO Record, FROM Enum TO Mixin, FROM Enum TO Extension, FROM Enum TO Module, FROM Enum TO Object, FROM Enum TO ExternalClass,
                FROM `Union` TO Class, FROM `Union` TO Trait, FROM `Union` TO Interface, FROM `Union` TO Struct, FROM `Union` TO Enum, FROM `Union` TO `Union`, FROM `Union` TO Record, FROM `Union` TO Mixin, FROM `Union` TO Extension, FROM `Union` TO Module, FROM `Union` TO Object, FROM `Union` TO ExternalClass,
                FROM Record TO Class, FROM Record TO Trait, FROM Record TO Interface, FROM Record TO Struct, FROM Record TO Enum, FROM Record TO `Union`, FROM Record TO Record, FROM Record TO Mixin, FROM Record TO Extension, FROM Record TO Module, FROM Record TO Object, FROM Record TO ExternalClass,
                FROM Mixin TO Class, FROM Mixin TO Trait, FROM Mixin TO Interface, FROM Mixin TO Struct, FROM Mixin TO Enum, FROM Mixin TO `Union`, FROM Mixin TO Record, FROM Mixin TO Mixin, FROM Mixin TO Extension, FROM Mixin TO Module, FROM Mixin TO Object, FROM Mixin TO ExternalClass,
                FROM Extension TO Class, FROM Extension TO Trait, FROM Extension TO Interface, FROM Extension TO Struct, FROM Extension TO Enum, FROM Extension TO `Union`, FROM Extension TO Record, FROM Extension TO Mixin, FROM Extension TO Extension, FROM Extension TO Module, FROM Extension TO Object, FROM Extension TO ExternalClass,
                FROM Module TO Class, FROM Module TO Trait, FROM Module TO Interface, FROM Module TO Struct, FROM Module TO Enum, FROM Module TO `Union`, FROM Module TO Record, FROM Module TO Mixin, FROM Module TO Extension, FROM Module TO Module, FROM Module TO Object, FROM Module TO ExternalClass,
                FROM Object TO Class, FROM Object TO Trait, FROM Object TO Interface, FROM Object TO Struct, FROM Object TO Enum, FROM Object TO `Union`, FROM Object TO Record, FROM Object TO Mixin, FROM Object TO Extension, FROM Object TO Module, FROM Object TO Object, FROM Object TO ExternalClass,
                FROM Variable TO Class, FROM Variable TO Trait, FROM Variable TO Interface, FROM Variable TO Struct, FROM Variable TO Enum, FROM Variable TO `Union`, FROM Variable TO Record, FROM Variable TO Mixin, FROM Variable TO Extension, FROM Variable TO Module, FROM Variable TO Object, FROM Variable TO Variable, FROM Variable TO ExternalClass,
                FROM Class TO Variable, FROM Trait TO Variable, FROM Interface TO Variable, FROM Struct TO Variable, FROM Enum TO Variable, FROM `Union` TO Variable, FROM Record TO Variable, FROM Mixin TO Variable, FROM Extension TO Variable, FROM Module TO Variable, FROM Object TO Variable,
                confidence_label STRING
            """, True),
            ("HAS_PARAMETER", "FROM Function TO Parameter", False),
            ("INCLUDES", "FROM Class TO Module", False),
            ("IMPLEMENTS", "FROM Class TO Interface, FROM Class TO Class, FROM Struct TO Interface, FROM Record TO Interface, FROM Mixin TO Interface, FROM Extension TO Interface, FROM Enum TO Interface, FROM Object TO Interface, FROM `Union` TO Interface, FROM Trait TO Interface, FROM Module TO Module, FROM Module TO Interface, confidence_label STRING", True),
            ("METACLASS", "FROM Class TO Class, line_number INT64, confidence_label STRING", False),
            ("DECORATED_BY", "FROM Function TO Function, FROM Class TO Function, line_number INT64", True),
            ("COMPANION_OF", "FROM Object TO Class", False),
            ("EMBEDS", "FROM Struct TO Struct, line_number INT64", False),
            ("PARTIAL_OF", "FROM Class TO Class, line_number INT64, confidence_label STRING", False),
            ("PART_OF", "FROM File TO File", False),
            ("INJECTS", "FROM Class TO Class, field_name STRING, inject_line INT64, confidence_label STRING", False),
            ("MAPS_TO", "FROM Class TO DbTable, datastore STRING, line_number INT64", False),
            ("READS", "FROM Function TO DbTable, line_number INT64", False),
            ("WRITES", "FROM Function TO DbTable, line_number INT64", False),
            ("STORED_IN", "FROM DbTable TO Datasource, FROM RedisKeyPattern TO Datasource", True),
            ("HAS_COLUMN", "FROM DbTable TO DbColumn", False),
        ]

        for table_name, schema in node_tables:
            try:
                self._conn.execute(f"CREATE NODE TABLE `{table_name}`({schema})")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    warning_logger(f"Kuzu Schema Node Error ({table_name}): {e}")
                    debug_log(f"Kuzu Schema Node Error ({table_name}): {e}")

        for table_name, schema, use_group in rel_tables:
            try:
                if use_group:
                    # KùzuDB requires CREATE REL TABLE GROUP for multi-binding relationships
                    self._conn.execute(f"CREATE REL TABLE GROUP `{table_name}`({schema})")
                else:
                    self._conn.execute(f"CREATE REL TABLE `{table_name}`({schema})")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    warning_logger(f"Kuzu Schema Rel Error ({table_name}): {e}")
                    debug_log(f"Kuzu Schema Rel Error ({table_name}): {e}")

        self._run_schema_migrations()

    def _run_schema_migrations(self):
        """Add columns introduced after older local Kùzu databases were created."""
        # Simple (non-group) table migrations
        simple_migrations = [
            ("File", "package_name", "STRING"),
            ("Module", "full_import_name", "STRING"),
            ("Module", "path", "STRING"),
            ("Module", "line_number", "INT64"),
            ("DbTable", "path", "STRING"),
            ("ExternalClass", "path", "STRING"),
            ("IMPORTS", "full_import_name", "STRING"),
            ("IMPORTS", "imported_name", "STRING"),
            ("Repository", "indexed_at", "STRING"),
            ("Repository", "commit_hash", "STRING"),
            # Spring endpoint properties on Function
            ("Function", "http_method", "STRING"),
            ("Function", "http_path", "STRING"),
            # Kotlin/JVM precision improvements
            ("Function", "class_context_line", "INT64"),
            ("Function", "module_context", "STRING"),
            ("Function", "embedding", "DOUBLE[]"),
            ("Class", "node_type", "STRING"),
        ]

        # REL TABLE GROUP migrations: KuzuDB creates sub-tables named
        # <group>_<FromLabel>_<ToLabel> for each binding.  ALTER TABLE must
        # target each sub-table individually; using the group name fails.
        _CALLS_SUBTABLES = [
            "CALLS_Function_Function", "CALLS_Function_Class",
            "CALLS_File_Function", "CALLS_File_Class",
            "CALLS_Class_Function", "CALLS_Class_Class",
        ]
        _INHERITS_SUBTABLES = [
            "INHERITS_Class_Class", "INHERITS_Record_Record",
            "INHERITS_Interface_Interface",
        ]

        group_migrations = []
        for col_name, col_type in [
            ("confidence", "DOUBLE"),
            ("resolution_tier", "INT64"),
            ("confidence_label", "STRING"),
            ("source", "STRING"),
            ("resolution_method", "STRING"),
            ("called_name", "STRING"),
            ("args_key", "STRING"),
        ]:
            for sub in _CALLS_SUBTABLES:
                group_migrations.append((sub, col_name, col_type))

        for sub in _INHERITS_SUBTABLES:
            group_migrations.append((sub, "confidence_label", "STRING"))

        _IMPLEMENTS_SUBTABLES = [
            "IMPLEMENTS_Class_Interface", "IMPLEMENTS_Class_Class",
            "IMPLEMENTS_Struct_Interface", "IMPLEMENTS_Module_Module",
            "IMPLEMENTS_Module_Interface",
        ]
        for sub in _IMPLEMENTS_SUBTABLES:
            group_migrations.append((sub, "confidence_label", "STRING"))

        all_migrations = simple_migrations + group_migrations

        # Relationship tables added after older databases were created.
        rel_table_migrations = [
            ("METACLASS", "FROM Class TO Class, line_number INT64, confidence_label STRING", False),
            ("DECORATED_BY", "FROM Function TO Function, FROM Class TO Function, line_number INT64", True),
            ("COMPANION_OF", "FROM Object TO Class", False),
            ("EMBEDS", "FROM Struct TO Struct, line_number INT64", False),
            ("PARTIAL_OF", "FROM Class TO Class, line_number INT64, confidence_label STRING", False),
            ("PART_OF", "FROM File TO File", False),
        ]
        for table_name, schema, use_group in rel_table_migrations:
            try:
                if use_group:
                    self._conn.execute(f"CREATE REL TABLE GROUP `{table_name}`({schema})")
                else:
                    self._conn.execute(f"CREATE REL TABLE `{table_name}`({schema})")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    debug_log(f"Kuzu Schema Rel Migration ({table_name}): {e}")

        try:
            self._conn.execute(
                "CREATE NODE TABLE `EnumMember`("
                "uid STRING, name STRING, path STRING, line_number INT64, "
                "lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid))"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                debug_log(f"Kuzu Schema Node Migration (EnumMember): {e}")

        for table_name, column_name, column_type in all_migrations:
            try:
                self._conn.execute(f"ALTER TABLE `{table_name}` ADD {column_name} {column_type}")
            except Exception as e:
                err = str(e).lower()
                if "already exists" in err or "duplicate" in err or "already has property" in err:
                    continue
                # Sub-table may not exist if the group was freshly created with
                # the correct schema; silently skip "does not exist" errors.
                if "does not exist" in err or "not found" in err:
                    continue
                warning_logger(f"Kuzu Schema Migration Error ({table_name}.{column_name}): {e}")
                debug_log(f"Kuzu Schema Migration Error ({table_name}.{column_name}): {e}")
                raise RuntimeError("Kuzu Schema Migration Failed") from e

    def close_driver(self):
        """Closes the connection pool and releases database resources."""
        if self._db is not None:
            with self._lock:
                if self._db is None:
                    return
                info_logger(f"Closing {self.BACKEND_SPEC.display_name} connection pool")
                # Clear and close all connections in the pool
                while self._pool is not None and not self._pool.empty():
                    try:
                        conn = self._pool.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._pool = None
                # Explicitly close the Database object — kuzu.Database has no
                # __del__, so Python GC alone cannot release the C++ resources.
                # Without this call the process hangs on exit because the
                # embedded Kùzu engine keeps background threads alive.
                try:
                    if not self._db.is_closed():
                        self._db.close()
                        info_logger(f"{self.BACKEND_SPEC.display_name} database closed successfully")
                except Exception as e:
                    warning_logger(f"Error closing {self.BACKEND_SPEC.display_name} database: {e}")
                self._db = None
                gc.collect()

    def is_connected(self) -> bool:
        """Checks if the database connection is currently active."""
        if self._db is None:
            return False
        try:
            # Borrow a connection to test
            conn = self._pool.get(timeout=1.0)
            try:
                conn.execute("RETURN 1")
                return True
            finally:
                self._pool.put(conn)
        except Exception:
            return False
    
    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return self.BACKEND_SPEC.backend_id

    @classmethod
    def validate_config(cls, db_path: str = None) -> Tuple[bool, Optional[str]]:
        if db_path:
            db_dir = Path(db_path).parent
            if not os.access(db_dir, os.W_OK) and db_dir.exists():
                return False, f"Cannot write to directory: {db_dir}"
        return True, None

    @classmethod
    def test_connection(cls, db_path: str = None) -> Tuple[bool, Optional[str]]:
        spec = cls.BACKEND_SPEC
        try:
            importlib.import_module(spec.python_module)
            return True, None
        except ImportError:
            return False, f"{spec.display_name} is not installed. {spec.install_hint}"


class EmbeddedDriverWrapper:
    def __init__(
        self,
        db,
        pool_or_lock,
        write_lock=None,
        compat_state=None,
        display_name: str = "Embedded",
        backend_id: str = "embedded",
    ):
        self.db = db
        self._compat_state = compat_state
        self._display_name = display_name
        self._backend_id = backend_id
        if hasattr(pool_or_lock, "acquire"):
            self._pool = None
            self._write_lock = pool_or_lock
            self._query_lock = pool_or_lock
        else:
            self._pool = pool_or_lock
            self._write_lock = write_lock or threading.Lock()
            self._query_lock = self._write_lock
    def session(self, **kwargs):
        """Accepts and ignores Neo4j-specific kwargs (e.g. default_access_mode)."""
        compat_state = getattr(self, "_compat_state", None)
        pool = getattr(self, "_pool", None)
        display_name = getattr(self, "_display_name", "Embedded")
        if pool is not None:
            return EmbeddedSessionWrapper(
                pool, getattr(self, "_write_lock", None),
                compat_state=compat_state, display_name=display_name,
            )
        else:
            db = getattr(self, "db", None) or getattr(self, "conn", None)
            write_lock = getattr(self, "_write_lock", None) or getattr(self, "_query_lock", None)
            return EmbeddedSessionWrapper(
                db, write_lock, compat_state=compat_state, display_name=display_name,
            )
    def close(self):
        pass

    def get_backend_type(self) -> str:
        return getattr(self, "_backend_id", "embedded")


class EmbeddedSessionWrapper:
    def __init__(self, pool_or_conn, write_lock=None, compat_state=None, display_name: str = "Embedded"):
        self._write_lock = write_lock or threading.Lock()
        self._query_lock = self._write_lock
        self._display_name = display_name
        # Disabled-query-type state is shared via the manager's compat_state so
        # fail-fast disabling persists across sessions. A standalone session
        # (tests / legacy callers) gets its own private state.
        state = compat_state or EmbeddedCompatState()
        self._compat_state = state
        self._disabled_query_types = state.disabled_query_types
        self._logged_disabled_query_types = state.logged_disabled_query_types
        self._state_lock = state.lock
        
        # Backward compatibility check: check if it's a pool or connection
        if hasattr(pool_or_conn, "get") and not hasattr(pool_or_conn, "execute"):
            self._pool = pool_or_conn
            self.conn = self._pool.get()
        else:
            self._pool = None
            self.conn = pool_or_conn


        self.uid_map = {
            'Function': ['name', 'path', 'line_number'],
            'Class': ['name', 'path', 'line_number'],
            'Variable': ['name', 'path', 'line_number'],
            'Trait': ['name', 'path', 'line_number'],
            'Interface': ['name', 'path', 'line_number'],
            'Macro': ['name', 'path', 'line_number'],
            'Struct': ['name', 'path', 'line_number'],
            'Enum': ['name', 'path', 'line_number'],
            'EnumMember': ['name', 'path', 'line_number'],
            'Union': ['name', 'path', 'line_number'],
            'Annotation': ['name', 'path', 'line_number'],
            'Record': ['name', 'path', 'line_number'],
            'Property': ['name', 'path', 'line_number'],
            'Parameter': ['name', 'path', 'function_line_number'],
            'Mixin': ['name', 'path', 'line_number'],
            'Extension': ['name', 'path', 'line_number'],
            'Object': ['name', 'path', 'line_number']
        }
    
    def __enter__(self):
        """Enter context manager - return self for 'with' statement."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - Return connection to the pool."""
        if self.conn and self._pool is not None:
            self._pool.put(self.conn)
        return False  # Don't suppress exceptions


    @staticmethod
    def _sanitize_value(v):
        """Recursively coerce Python types that KuzuDB cannot bind (tuples, sets, etc.)."""
        if isinstance(v, tuple):
            return [EmbeddedSessionWrapper._sanitize_value(i) for i in v]
        if isinstance(v, set):
            return [EmbeddedSessionWrapper._sanitize_value(i) for i in v]
        if isinstance(v, list):
            sanitized = [EmbeddedSessionWrapper._sanitize_value(i) for i in v]

            # Kuzu infers list-of-dict values as a struct vector. If rows in an
            # UNWIND batch have different keys, referencing a missing row.field
            # causes binder errors like "Invalid struct field name".
            if sanitized and all(isinstance(i, dict) for i in sanitized):
                all_keys = set()
                for item in sanitized:
                    all_keys.update(item.keys())
                if all_keys:
                    key_order = sorted(all_keys)
                    # Detect relationship batches — these should NOT be
                    # deduplicated because distinct relationship edges may
                    # serialize identically yet represent different graph edges
                    # (e.g. multiple CALLS from the same caller to the same
                    # target at different call sites).
                    _REL_BATCH_KEYS = {
                        "child_name", "parent_name", "resolved_parent_file_path",
                        "caller_name", "called_name", "caller_file_path",
                        "called_file_path", "caller_line_number",
                        "func_name", "arg_name",
                        "caller_symbol", "callee_name",
                        "injector_class", "injected_class",
                        "interface_name",
                    }
                    is_rel_batch = bool(all_keys & _REL_BATCH_KEYS)

                    normalized_rows = []
                    seen_rows = set() if not is_rel_batch else None
                    for item in sanitized:
                        row = {k: item.get(k) for k in key_order}
                        # NULL values in MERGE key fields (especially line_number)
                        # can cause repeated non-matching MERGEs. Normalize to a
                        # sentinel for stable identity in Kuzu.
                        for int_key in ("line_number", "function_line_number", "end_line"):
                            if int_key in row and row[int_key] is None:
                                row[int_key] = -1
                        if seen_rows is not None:
                            row_key = json.dumps(row, sort_keys=True, default=str)
                            if row_key in seen_rows:
                                continue
                            seen_rows.add(row_key)
                        normalized_rows.append(row)
                    return normalized_rows

            return sanitized
        if isinstance(v, dict):
            return {k: EmbeddedSessionWrapper._sanitize_value(val) for k, val in v.items()}
        return v

    def _classify_query_type(self, query: str) -> str:
        if "db.idx.fulltext.createNodeIndex" in query or "db.index.fulltext.queryNodes" in query:
            return "fulltext"
        if "MATCH (file:File)-[imp:IMPORTS]->(module:Module" in query:
            return "module_deps"
        if "INHERITS" in query or "IMPLEMENTS" in query:
            return "inheritance_resolution"
        if "CALLS" in query:
            return "calls_resolution"
            
        # Write query detection
        query_upper = query.upper()
        write_keywords = {"MERGE", "CREATE", "SET", "DELETE", "REMOVE", "DROP", "ALTER", "COPY"}
        if any(k in query_upper for k in write_keywords):
            return "write"
            
        return "generic"

    def _is_query_type_disabled(self, query_type: str) -> bool:
        if query_type == "generic":
            return False
        with self._state_lock:
            return query_type in self._disabled_query_types

    def _log_query_type_skip_once(self, query_type: str) -> None:
        if query_type == "generic":
            return
        with self._state_lock:
            if query_type in self._logged_disabled_query_types:
                return
            self._logged_disabled_query_types.add(query_type)
        warning_logger(
            f"{self._display_name} compatibility guard active: skipping "
            f"'{query_type}' queries after prior incompatibility."
        )

    def _should_fail_fast(self, query_type: str, error: Exception) -> bool:
        err = str(error).lower()
        if query_type == "fulltext":
            return "parser exception" in err or "invalid input <call db." in err
        if query_type == "module_deps":
            return "variable file is not in scope" in err or "binder exception" in err
        # Do NOT fail-fast for calls_resolution or inheritance_resolution.
        # The writer iterates over label pairs with its own try/except for
        # binder exceptions.  Disabling the entire query type here would
        # silently drop valid edges for label pairs that DO have schema
        # bindings, causing parity mismatches vs FalkorDB / Neo4j.
        return False

    def _disable_query_type(self, query_type: str, error: Exception) -> None:
        if query_type == "generic":
            return
        with self._state_lock:
            self._disabled_query_types.add(query_type)
            already_logged = query_type in self._logged_disabled_query_types
            if not already_logged:
                self._logged_disabled_query_types.add(query_type)
        if not already_logged:
            warning_logger(
                f"Kuzu compatibility guard: disabling '{query_type}' queries for this run after error: {error}"
            )

    def run(self, query, **parameters):
        query_type = self._classify_query_type(query)
        if self._is_query_type_disabled(query_type):
            self._log_query_type_skip_once(query_type)
            return EmbeddedResultWrapper(None)

        # 0. Sanitize parameters (convert tuples/sets → lists throughout)
        parameters = {k: self._sanitize_value(v) for k, v in parameters.items()}
        # 1. Translate Query
        debug_log(f"Original Query: {query[:200]}")
        translated_query, translated_params = self._translate_query(query, parameters)
        debug_log(f"Translated Query: {translated_query[:200]}")
        try:
            # Force loop fallback for relationship writes inside UNWIND to avoid Kuzu query planner bugs
            # which can incorrectly bind/corrupt relationship endpoints across rows in the batch.
            if "UNWIND" in query and ("-[" in query or "]->" in query) and not getattr(self, "_skip_unwind_fallback", False):
                raise Exception("unordered_map::at (forced fallback to avoid relationship UNWIND planner bugs)")

            # 2. Execute under the lock. _write_lock (name kept for backward
            # compat) now serializes ALL access, reads included: kuzu.Connection
            # is not thread-safe, and concurrent asyncio.to_thread tool calls can
            # otherwise race a read against a write on the same connection.
            with self._write_lock:
                result = self.conn.execute(translated_query, translated_params)

            return EmbeddedResultWrapper(result)
        except Exception as e:
            if self._should_fail_fast(query_type, e):
                self._disable_query_type(query_type, e)
                return EmbeddedResultWrapper(None)

            # Log non-fatal schema collisions at debug level instead of swallowing
            # them silently. This preserves the "idempotent CREATE" behaviour while
            # still emitting a traceable message for unexpected collisions.
            err_str = str(e).lower()
            if "already exists" in err_str:
                debug_log(f"Kuzu idempotent collision (already exists) — query: {query[:120]}")
                return EmbeddedResultWrapper(None)
            
            if "binder exception" in err_str:
                debug_log(f"Kuzu binder exception (expected during label matching check) — query: {query[:120]}... Error: {e}")
                raise e
            
            # Fallback for KuzuDB UNWIND bug (unordered_map::at)
            if "unordered_map::at" in err_str and "UNWIND" in query:
                unwind_m = re.search(r'UNWIND\s+\$(\w+)\s+AS\s+(\w+)', query)
                if unwind_m:
                    batch_param = unwind_m.group(1)
                    row_var = unwind_m.group(2)
                    batch_data = parameters.get(batch_param)
                    if isinstance(batch_data, list):
                        loop_query = re.sub(r'UNWIND\s+\$\w+\s+AS\s+\w+', '', query, count=1)
                        # Find all row.prop usages and replace with $row_prop
                        props_used = set(re.findall(rf'{row_var}\.(\w+)', loop_query))
                        for p in props_used:
                            loop_query = loop_query.replace(f"{row_var}.{p}", f"${row_var}_{p}")
                        
                        last_result = None
                        for item in batch_data:
                            loop_params = parameters.copy()
                            loop_params.pop(batch_param, None)
                            for p in props_used:
                                loop_params[f"{row_var}_{p}"] = item.get(p)
                            if "uid" in item:
                                loop_params[f"{row_var}_uid"] = item["uid"]
                            try:
                                last_result = self.run(loop_query, **loop_params)
                            except Exception as nested_e:
                                nested_err_str = str(nested_e).lower()
                                if "binder" in nested_err_str or "cannot find a valid label" in nested_err_str:
                                    continue
                                raise nested_e
                        return last_result or EmbeddedResultWrapper(None)


            error_logger(f"Kuzu Query failed: {query[:100]}... Error: {e}")
            debug_log(f"Kuzu Query failed: {query[:100]}... Error: {e}")
            raise e
    def _translate_query(self, query: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Translates Neo4j Cypher to Kuzu Cypher."""
        PK_MAP = {
            'Repository': 'path',
            'File': 'path',
            'Directory': 'path',
            'Module': 'name',
            'DbTable': 'name',
            'ExternalClass': 'name'
        }
        
        # 0. Define Schema Map (Strict property filtering)
        SCHEMA_MAP = {
            'Repository': {'path', 'name', 'is_dependency', 'indexed_at', 'commit_hash'},
            'File': {'path', 'name', 'relative_path', 'package_name', 'is_dependency'},
            'Directory': {'path', 'name'},
            'Module': {'name', 'lang', 'full_import_name', 'path', 'line_number'},
            'Function': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'cyclomatic_complexity', 'context', 'context_type', 'class_context', 'class_context_line', 'module_context', 'is_dependency', 'decorators', 'args', 'http_method', 'http_path'},
            'Class': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'node_type', 'is_dependency', 'decorators'},
            'Variable': {'uid', 'name', 'path', 'line_number', 'source', 'docstring', 'lang', 'value', 'context', 'is_dependency'},
            'Trait': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Interface': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Macro': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Struct': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Enum': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'EnumMember': {'uid', 'name', 'path', 'line_number', 'lang', 'is_dependency'},
            'Union': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Annotation': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Record': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Property': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Parameter': {'uid', 'name', 'path', 'function_line_number'},
            'Mixin': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Extension': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Object': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'}
        }

        # 1. Translate SET n += $props  and  SET n = $props  (map merge/assign)
        if "SET" in query and "= $" in query:
            match = re.search(r'SET\s+(\w+)\s*\+?=\s*\$(\w+)', query)
            if match:
                node_var = match.group(1)
                param_name = match.group(2)
                
                # Determine label used for node_var to filter properties
                def_match = re.search(rf'\({node_var}:(\w+)', query)
                label = def_match.group(1) if def_match else None
                
                props_dict = parameters.get(param_name, {})
                if isinstance(props_dict, dict):
                    set_clauses = []
                    new_params = parameters.copy()
                    
                    allowed_props = SCHEMA_MAP.get(label, set()) if label else None
                    pk_field = PK_MAP.get(label, 'uid')

                    for k, v in props_dict.items():
                        if isinstance(v, (dict, list)) and k != 'args' and k != 'decorators':
                            continue
                        
                        if allowed_props and k not in allowed_props:
                           continue
                           
                        if k == pk_field or k == 'uid':
                            continue
                            
                        clean_k = f"{param_name}_{k}"
                        set_clauses.append(f"{node_var}.{k} = ${clean_k}")
                        new_params[clean_k] = v
                        
                    if set_clauses:
                        query = query.replace(match.group(0), "SET " + ", ".join(set_clauses))
                        new_params.pop(param_name, None)
                        parameters = new_params
                    else:
                        query = query.replace(match.group(0), "")

        # 1.5: Handle UNWIND-specific patterns before standard UID injection.
        # When queries use UNWIND $batch AS row, two things need translation:
        #   a) SET n += row  (map merge unsupported in KuzuDB) → explicit property SETs
        #   b) MERGE uid injection from row fields (row.name, row.line_number, …)
        unwind_m = re.search(r'UNWIND\s+\$(\w+)\s+AS\s+(\w+)', query)
        if unwind_m:
            batch_param = unwind_m.group(1)
            row_var = unwind_m.group(2)
            batch_data = parameters.get(batch_param)

            if isinstance(batch_data, list) and batch_data:
                # 1.5a: Expand  SET node_var += row_var  →  SET node_var.p1 = row_var.p1, …
                set_plus_re = re.compile(
                    rf'SET\s+(\w+)\s*\+=\s*{re.escape(row_var)}\b'
                )
                set_m = set_plus_re.search(query)
                if set_m:
                    node_var = set_m.group(1)
                    label_m = re.search(rf'\({re.escape(node_var)}:(\w+)', query)
                    label = label_m.group(1).strip('`') if label_m else None
                    allowed = SCHEMA_MAP.get(label, set()) if label else None

                    sample = batch_data[0]
                    parts = []
                    pk_field = PK_MAP.get(label, 'uid')
                    for k in sample:
                        if k == 'uid' or k == pk_field:
                            continue
                        if allowed and k not in allowed:
                            continue
                        parts.append(f"{node_var}.{k} = {row_var}.{k}")

                    replacement = ("SET " + ", ".join(parts)) if parts else ""
                    query = set_plus_re.sub(replacement, query, count=1)

                # 1.5b: Inject uid into MERGE clauses that reference UNWIND row fields
                merge_re = re.compile(
                    r'MERGE\s+\((\w+):([^\s\{]+)\s*\{([^}]+)\}\)'
                )
                for m in list(merge_re.finditer(query)):
                     var_name, label_raw, props_str = m.groups()
                     label = label_raw.strip('`')
                     if label not in self.uid_map:
                         continue

                     pk_parts = self.uid_map[label]
                     all_ok = True

                     for item in batch_data:
                         uid_components = []
                         for part in pk_parts:
                             row_ref = re.search(
                                 rf'\b{part}\s*:\s*{re.escape(row_var)}\.(\w+)',
                                 props_str,
                             )
                             param_ref = re.search(
                                 rf'\b{part}\s*:\s*\$(\w+)', props_str
                             )
                             if row_ref:
                                 val = item.get(row_ref.group(1))
                                 # Consider -1 as missing for line numbers to force fallback,
                                 # ensuring uniqueness when the primary key is incomplete
                                 if val is not None and not (part in ("line_number", "function_line_number", "end_line") and val == -1):
                                     uid_components.append(str(val))
                                 else:
                                     # Missing values are common in parser output for some
                                     # languages. Use a deterministic placeholder component
                                     # to keep UID generation stable and unique enough.
                                     row_hash = hashlib.md5(str(sorted([(k, v) for k, v in item.items() if k != 'uid'])).encode()).hexdigest()[:8]
                                     uid_components.append(f"__fallback_{row_hash}")
                             elif param_ref:
                                 val = parameters.get(param_ref.group(1))
                                 if val is not None:
                                     uid_components.append(str(val))
                                 else:
                                     uid_components.append(f"__missing_{part}")
                             else:
                                 all_ok = False
                                 break

                         if all_ok:
                             raw_uid = ''.join(uid_components)
                             item['uid'] = raw_uid
                         else:
                             all_ok = False
                             break

                     if all_ok:
                         old_block = '{' + props_str + '}'
                         new_block = (
                             '{' + props_str + f', uid: {row_var}.uid' + '}'
                         )
                         query = query.replace(old_block, new_block, 1)

                         # Kuzu node tables are keyed by uid for these labels, so MERGE
                         # should match on the primary key only. Matching on additional
                         # non-PK fields can still lead to duplicate PK insert attempts.
                         query = re.sub(
                             rf"MERGE\s+\({re.escape(var_name)}:{re.escape(label_raw)}\s*\{{[^}}]*uid:\s*{re.escape(row_var)}\.uid[^}}]*\}}\)",
                             f"MERGE ({var_name}:{label_raw} {{uid: {row_var}.uid}})",
                             query,
                             count=1,
                         )

                # 1.5c: Strip explicit SET clauses for properties not in the schema
                # (e.g. SET m.alias = row.alias when Module has no 'alias' column)
                def _filter_set_clause(m_set):
                    full = m_set.group(0)
                    assignments = re.split(r',\s*(?=\w+\.\w+\s*=)', full[4:])  # skip "SET "
                    kept = []
                    for a in assignments:
                        a = a.strip()
                        prop_m = re.match(r'(\w+)\.(\w+)\s*=', a)
                        if prop_m:
                            nvar = prop_m.group(1)
                            prop_name = prop_m.group(2)
                            lbl_m = re.search(rf'\({re.escape(nvar)}:(\w+)', query)
                            if lbl_m:
                                lbl = lbl_m.group(1).strip('`')
                                allowed_s = SCHEMA_MAP.get(lbl)
                                if allowed_s and prop_name not in allowed_s:
                                    continue
                                if prop_name == PK_MAP.get(lbl, 'uid') or prop_name == 'uid':
                                    continue
                        kept.append(a)
                    if kept:
                        return "SET " + ", ".join(kept)
                    return ""

                # Only apply to explicit SET lines (not SET +=, already handled)
                if '+=' not in query:
                    query = re.sub(
                        r'SET\s+\w+\.\w+\s*=\s*[^,\n]+(?:\s*,\s*\w+\.\w+\s*=\s*[^,\n]+)*',
                        _filter_set_clause,
                        query,
                    )

                # 1.5d: Translate ON CREATE SET / ON MATCH SET → plain SET (KuzuDB compat)
                query = re.sub(r'\bON\s+CREATE\s+SET\b', 'SET', query, flags=re.IGNORECASE)
                query = re.sub(r'\bON\s+MATCH\s+SET\b', 'SET', query, flags=re.IGNORECASE)

        # 2. Handle UID injection for MERGE (non-UNWIND queries)
        # We look for MERGE (v:Label {props})
        merge_pattern = r'MERGE\s+\((\w+):([^\s\{]+)\s*\{([^}]+)\}\)'
        matches = list(re.finditer(merge_pattern, query))
        for m in matches:
            var_name, label_raw, props_str = m.groups()
            label = label_raw.strip('`').strip(':')
            if label in self.uid_map:
                # Skip if uid already injected (by UNWIND handler above)
                if 'uid:' in props_str:
                    continue
                pk_parts = self.uid_map[label]
                can_build_uid = True
                uid_val = ""
                for part in pk_parts:
                    p_match = re.search(rf'{part}:\s*\$(\w+)', props_str)
                    if p_match:
                        p_val = parameters.get(p_match.group(1))
                        if p_val is not None:
                            uid_val += str(p_val)
                        else: can_build_uid = False; break
                    else: can_build_uid = False; break
                
                if can_build_uid:
                    uid_param = f"__uid_{var_name}"
                    old_block = f"{{{props_str}}}"
                    new_block = f"{{{props_str}, uid: ${uid_param}}}"
                    if old_block in query:
                         query = query.replace(old_block, new_block)
                    else:
                         warning_logger(f"Kuzu UID injection: could not find props block in query for label '{label}'")
                    
                    parameters[uid_param] = uid_val

        query, parameters = self._rewrite_kuzu_compat_patterns(query, parameters)

        # 3. Escape keywords as labels
        labels_to_escape = ['Macro', 'Union', 'Property', 'CONTAINS', 'CALLS'] # Only critical keywords
        for label in labels_to_escape:
            query = re.sub(rf':{label}\b', f':`{label}`', query)

        # Translate (n:Label1 OR n:Label2 ...) to label(n) IN ['Label1', 'Label2', ...]
        def poly_replacer(match):
            full_match = match.group(0)
            var_name = match.group(1)
            # Find all labels associated with this variable in the OR chain
            labels = re.findall(rf'{var_name}:([a-zA-Z0-9_`]+)', full_match)
            # Strip backticks from labels
            labels = [l.strip('`') for l in labels]
            return f"label({var_name}) IN {json.dumps(labels)}"
        
        # Regex to match (n:Label1 OR n:Label2 OR n:Label3)
        query = re.sub(r'\((\w+):[a-zA-Z0-9_`]+(?:\s+OR\s+\1:[a-zA-Z0-9_`]+)+\)', poly_replacer, query)
        
        # Translate single WHERE n:Label to label(n) = 'Label'
        # This is more complex because we don't want to match MATCH/MERGE
        # For now, we only target where it appears after WHERE or AND/OR
        def single_label_replacer(match):
            prefix = match.group(1)
            var_name = match.group(2)
            label = match.group(3).strip('`')
            return f"{prefix}label({var_name}) = '{label}'"
            
        query = re.sub(r'(WHERE\s+|AND\s+|OR\s+|WHEN\s+)(\w+):([a-zA-Z0-9_`]+)', single_label_replacer, query, flags=re.IGNORECASE)

        # Handle NOT n:Label → NOT label(n) = 'Label'
        def not_label_replacer(match):
            prefix = match.group(1)
            var_name = match.group(2)
            label_name = match.group(3).strip('`')
            return f"{prefix}NOT label({var_name}) = '{label_name}'"
        query = re.sub(r'(WHERE\s+|AND\s+|OR\s+)NOT\s+(\w+):([a-zA-Z0-9_`]+)', not_label_replacer, query, flags=re.IGNORECASE)

        # 4. Polymorphic matches and label access
        query = query.replace("labels(n)[0]", "label(n)")

        query = query.replace("coalesce(", "COALESCE(")
        query = re.sub(r'\btype\(', 'label(', query)

        # General ON CREATE/MATCH SET → SET (also covers non-UNWIND queries)
        query = re.sub(r'\bON\s+CREATE\s+SET\b', 'SET', query, flags=re.IGNORECASE)
        query = re.sub(r'\bON\s+MATCH\s+SET\b', 'SET', query, flags=re.IGNORECASE)

        if any(x in query.upper() for x in ["CREATE CONSTRAINT", "CREATE INDEX"]):
            return "RETURN 1", {}

        # 5. Cleanup unused parameters (Kuzu is strict)
        used_params = set(re.findall(r'\$(\w+)', query))
        parameters = {k: v for k, v in parameters.items() if k in used_params}

        return query, parameters

    def _rewrite_kuzu_compat_patterns(self, query: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Rewrite known Neo4j-only query patterns to Kuzu-compatible variants."""

        # Kuzu does not support Falkor fulltext procedures.
        if "CALL db.idx.fulltext.createNodeIndex" in query:
            return "RETURN 1", {}

        # Kuzu does not support Neo4j fulltext procedures. Rewrite to substring search.
        if "CALL db.index.fulltext.queryNodes" in query:
            plain_term = parameters.get("search_term", "")
            if isinstance(plain_term, str) and plain_term.lower().startswith("name:"):
                plain_term = plain_term[5:]
            parameters = {**parameters, "search_term_plain": plain_term}
            repo_filter = "AND node.path STARTS WITH $repo_path" if "$repo_path" in query else ""

            if "MATCH (node)<-[:CONTAINS]-(f:File)" in query or "MATCH (node)<-[:`CONTAINS`]-(f:File)" in query:
                rewritten = f"""
                MATCH (node)
                WHERE label(node) IN ['Function', 'Class', 'Variable'] {repo_filter}
                  AND (
                    (node.name IS NOT NULL AND toLower(node.name) CONTAINS toLower($search_term_plain)) OR
                    (node.source IS NOT NULL AND toLower(node.source) CONTAINS toLower($search_term_plain)) OR
                    (node.docstring IS NOT NULL AND toLower(node.docstring) CONTAINS toLower($search_term_plain))
                  )
                OPTIONAL MATCH (node)<-[:CONTAINS]-(f:File)
                RETURN
                    CASE
                        WHEN label(node) = 'Function' THEN 'function'
                        WHEN label(node) = 'Class' THEN 'class'
                        ELSE 'variable'
                    END as type,
                    node.name as name,
                    COALESCE(f.path, node.path) as path,
                    node.line_number as line_number,
                    node.source as source,
                    node.docstring as docstring,
                    node.is_dependency as is_dependency
                ORDER BY node.is_dependency ASC, node.name
                LIMIT 20
                """
                return rewritten, parameters

            label = "Function" if "node:Function" in query else "Class" if "node:Class" in query else None
            if label:
                rewritten = f"""
                MATCH (node:{label})
                WHERE toLower(node.name) CONTAINS toLower($search_term_plain) {repo_filter}
                RETURN node.name as name, node.path as path, node.line_number as line_number,
                    node.source as source, node.docstring as docstring, node.is_dependency as is_dependency
                ORDER BY node.is_dependency ASC, node.name
                LIMIT 20
                """
                return rewritten, parameters

        # Kuzu requires explicit carrying of bindings into OPTIONAL MATCH and
        # alias-based ORDER BY after RETURN DISTINCT.
        if (
            "MATCH (file:File)-[imp:IMPORTS]->(module:Module" in query
            and (
                "OPTIONAL MATCH (repo:Repository)-[:CONTAINS]->(file)" in query
                or "OPTIONAL MATCH (repo:Repository)-[:`CONTAINS`]->(file)" in query
            )
        ):
            query = query.replace(
                "OPTIONAL MATCH (repo:Repository)-[:CONTAINS]->(file)",
                "WITH file, imp, module\n                OPTIONAL MATCH (repo:Repository)-[:CONTAINS]->(file)",
            )
            query = query.replace(
                "OPTIONAL MATCH (repo:Repository)-[:`CONTAINS`]->(file)",
                "WITH file, imp, module\n                OPTIONAL MATCH (repo:Repository)-[:`CONTAINS`]->(file)",
            )
            query = query.replace(
                "ORDER BY file.is_dependency ASC, file.path",
                "ORDER BY file_is_dependency ASC, importer_file_path",
            )

        if "ORDER BY other_module.name" in query and "other_module.name as imported_module" in query:
            query = query.replace("ORDER BY other_module.name", "ORDER BY imported_module")

        # Import-batch compatibility: ensure optional fields exist on all UNWIND
        # rows and avoid writing unsupported Module.alias on Kuzu schema.
        if (
            "UNWIND $batch AS row" in query
            and "MERGE (m:Module {name: row.name})" in query
            and "row.full_import_name" in query
        ):
            batch = parameters.get("batch")
            if isinstance(batch, list):
                normalized_batch = []
                for item in batch:
                    if isinstance(item, dict):
                        normalized = dict(item)
                        normalized.setdefault("full_import_name", normalized.get("name"))
                        normalized.setdefault("alias", "")
                        normalized.setdefault("line_number", None)
                        normalized_batch.append(normalized)
                    else:
                        normalized_batch.append(item)
                parameters = {**parameters, "batch": normalized_batch}

            query = query.replace("SET m.alias = row.alias,", "SET")

        return query, parameters


class EmbeddedRecord:
    def __init__(self, data_dict):
        self._data = data_dict
        self._keys = list(data_dict.keys())
    
    def data(self):
        return self._data
    
    def keys(self):
        return self._keys
    
    def items(self):
        return self._data.items()
    
    def values(self):
        return list(self._data.values())
    
    def __len__(self):
        return len(self._data)
    
    def __getitem__(self, key):
        # Support both dict-style (by name) and list-style (by index) access
        if isinstance(key, int):
            # Integer index - get by position
            if 0 <= key < len(self._keys):
                return self._data[self._keys[key]]
            raise IndexError(f"Index {key} out of range")
        else:
            # String key - get by column name
            return self._data[key]
    
    def get(self, key, default=None):
        return self._data.get(key, default)

class EmbeddedResultWrapper:
    def __init__(self, result):
        self.result = result
        self._consumed = False
    def consume(self):
        self._consumed = True
        return self
    def single(self):
        records = self.data_raw()
        return EmbeddedRecord(records[0]) if records else None
    def data_raw(self) -> List[Dict[str, Any]]:
        if not self.result: return []
        records = []
        cols = self.result.get_column_names()
        while self.result.has_next():
            row = self.result.get_next()
            record = {}
            for i, val in enumerate(row):
                # Handle Kuzu Node/Rel objects for visualization compatibility
                processed_val = val
                try:
                    # Kuzu 0.11+ objects often have a specific structure
                    if hasattr(val, '__class__') and 'Node' in str(val.__class__):
                        processed_val = val
                        if not hasattr(processed_val, 'labels'):
                            processed_val.labels = [val.get_label_name()]
                        if not hasattr(processed_val, 'id'):
                           props = val.get_properties()
                           processed_val.id = props.get('uid', props.get('path', str(id(val))))
                        if not hasattr(processed_val, 'properties'):
                            processed_val.properties = val.get_properties()
                    
                    elif hasattr(val, '__class__') and 'Rel' in str(val.__class__):
                        processed_val = val
                        if not hasattr(processed_val, 'type'):
                            processed_val.type = val.get_label_name()
                        if not hasattr(processed_val, 'src_node'):
                            processed_val.src_node = val.get_src_id()['offset']
                        if not hasattr(processed_val, 'dest_node'):
                            processed_val.dest_node = val.get_dst_id()['offset']
                        if not hasattr(processed_val, 'properties'):
                            processed_val.properties = val.get_properties()
                except Exception:
                    pass
                
                record[cols[i]] = processed_val
            records.append(record)
        return records

    def data(self) -> List[Dict[str, Any]]:
        # Return raw dict data, not EmbeddedRecord.data()
        return self.data_raw()

    def __iter__(self):
        return iter([EmbeddedRecord(r) for r in self.data_raw()])
