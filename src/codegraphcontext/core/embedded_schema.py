"""DDL and derived property contracts shared by embedded writers and bundles.

Importing this module never loads a native database engine.
"""

import re

NODE_TABLES = [
    ("Repository", "path STRING, name STRING, is_dependency BOOLEAN, indexed_at STRING, commit_hash STRING, PRIMARY KEY (path)"),
    ("File", "path STRING, name STRING, relative_path STRING, package_name STRING, language STRING, is_dependency BOOLEAN, PRIMARY KEY (path)"),
    ("Directory", "path STRING, name STRING, PRIMARY KEY (path)"),
    ("Module", "name STRING, lang STRING, full_import_name STRING, path STRING, line_number INT64, PRIMARY KEY (name)"),
    # For types with composite keys (name, path, line_number), we use a 'uid'
    ("Function", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, cyclomatic_complexity INT64, context STRING, context_type STRING, class_context STRING, class_context_line INT64, module_context STRING, is_dependency BOOLEAN, decorators STRING[], args STRING[], arg_types STRING[], http_method STRING, http_path STRING, embedding DOUBLE[], visibility STRING, modifiers STRING[], is_composable BOOLEAN, PRIMARY KEY (uid)"),
    ("Class", "uid STRING, spring_stereotype STRING, request_mapping_prefix STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, node_type STRING, is_dependency BOOLEAN, decorators STRING[], visibility STRING, modifiers STRING[], PRIMARY KEY (uid)"),
    ("Variable", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, source STRING, docstring STRING, lang STRING, value STRING, context STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Trait", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Interface", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, decorators STRING[], visibility STRING, modifiers STRING[], PRIMARY KEY (uid)"),
    ("Macro", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Struct", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Enum", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("EnumMember", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Union", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Annotation", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Record", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Property", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Parameter", "uid STRING, name STRING, path STRING, function_line_number INT64, PRIMARY KEY (uid)"),
    ("Mixin", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Extension", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
    ("Object", "uid STRING, name STRING, path STRING, line_number INT64, occurrence_index INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, decorators STRING[], visibility STRING, modifiers STRING[], PRIMARY KEY (uid)"),
    ("DbTable", "fqn STRING, name STRING, datasource_name STRING, table_type STRING, comment STRING, path STRING, PRIMARY KEY (fqn)"),
    ("Datasource", "name STRING, kind STRING, host STRING, env STRING, PRIMARY KEY (name)"),
    ("DbColumn", "uid STRING, name STRING, table_fqn STRING, type STRING, nullable BOOLEAN, datasource_name STRING, is_primary_key BOOLEAN, PRIMARY KEY (uid)"),
    ("RedisKeyPattern", "uid STRING, pattern STRING, datasource_name STRING, key_type STRING, example_key STRING, count INT64, PRIMARY KEY (uid)"),
    ("ExternalClass", "name STRING, path STRING, PRIMARY KEY (name)"),
    # Build-system entities (#1603): these were never declared, so the
    # whole Gradle/Maven build graph silently failed to write on the
    # embedded backends. Composite natural keys use a synthesized uid.
    ("GradleModule", "name STRING, build_file STRING, path STRING, repo_path STRING, PRIMARY KEY (name)"),
    ("MavenModule", "uid STRING, group_id STRING, artifact_id STRING, version STRING, packaging STRING, pom_path STRING, path STRING, repo_path STRING, PRIMARY KEY (uid)"),
    ("ExternalLibrary", "uid STRING, group_id STRING, artifact_id STRING, version STRING, PRIMARY KEY (uid)")
]

# rel_tables: list of (table_name, schema, use_group)
# use_group=True  -> CREATE REL TABLE GROUP (for multi FROM..TO bindings)
# use_group=False -> CREATE REL TABLE          (single binding)
REL_TABLES = [
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
        FROM Class TO Variable, FROM Class TO EnumMember, FROM Enum TO EnumMember,
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
        FROM File TO Struct, FROM File TO Enum, FROM File TO Record, FROM File TO `Union`, FROM File TO Object,
        FROM Function TO File,
        FROM Variable TO Function, FROM Variable TO Class, FROM Variable TO Interface,
        line_number INT64, args STRING[], full_call_name STRING, args_key STRING, confidence DOUBLE, resolution_tier INT64,
        confidence_label STRING, source STRING, resolution_method STRING, called_name STRING
    """, True),
    # Same bindings as CALLS. writer.py emits HEURISTIC_CALLS for
    # resolution tier >= 8, but the table was never declared here, so on
    # Kùzu those edges could not be written and every query matching
    # [:CALLS|HEURISTIC_CALLS] failed outright with
    # "Binder exception: Table HEURISTIC_CALLS does not exist" —
    # which broke `cgc analyze dead-code` completely on this backend.
    ("HEURISTIC_CALLS", """
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
        FROM File TO Struct, FROM File TO Enum, FROM File TO Record, FROM File TO `Union`, FROM File TO Object,
        FROM Function TO File,
        FROM Variable TO Function, FROM Variable TO Class, FROM Variable TO Interface,
        line_number INT64, args STRING[], full_call_name STRING, args_key STRING, confidence DOUBLE, resolution_tier INT64,
        confidence_label STRING, source STRING, resolution_method STRING, called_name STRING
    """, True),
    ("IMPORTS", "FROM File TO Module, alias STRING, full_import_name STRING, imported_name STRING, line_number INT64, lang STRING", False),
    ("PREVIEWS", "FROM Function TO Function, line_number INT64", False),
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
    ("BINDS", "FROM Interface TO Class, FROM Class TO Class, FROM Interface TO Interface, line_number INT64, provider STRING, confidence_label STRING", True),
    ("MAPS_TO", "FROM Class TO DbTable, datastore STRING, line_number INT64", False),
    ("READS", "FROM Function TO DbTable, line_number INT64", False),
    ("WRITES", "FROM Function TO DbTable, line_number INT64", False),
    ("STORED_IN", "FROM DbTable TO Datasource, FROM RedisKeyPattern TO Datasource", True),
    ("HAS_COLUMN", "FROM DbTable TO DbColumn", False),
]



def _properties(schema):
    return {parts[0]: parts[1] for column in schema.split(',')
            if len(parts := column.strip().split()) == 2 and parts[0] != 'PRIMARY'}


NODE_COLUMN_TYPES = {label: _properties(schema) for label, schema in NODE_TABLES}
NODE_PROPERTIES = {label: set(columns) for label, columns in NODE_COLUMN_TYPES.items()}
NODE_LIST_PROPERTIES = {label: {name for name, kind in columns.items() if kind.endswith('[]')}
                        for label, columns in NODE_COLUMN_TYPES.items()}
NODE_PRIMARY_KEYS = {label: re.search(r'PRIMARY KEY\s*\((\w+)\)', schema).group(1)
                     for label, schema in NODE_TABLES}
REL_LIST_PROPERTIES = {label: {name for name, kind in _properties(schema).items() if kind.endswith('[]')}
                       for label, schema, _ in REL_TABLES}
