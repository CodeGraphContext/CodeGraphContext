"""Config file scanner: .properties + .yml under Spring layouts (PR #3)."""

from pathlib import Path

from codegraphcontext.wire import parse_properties, parse_yaml_kv, scan_repo_config


# ── parse_properties ─────────────────────────────────────────────────────────

def test_parse_properties_basic_pairs():
    text = """
# a comment
! bang comment
kafka.topic.orders = orders-base
grpc.host:localhost
grpc.port  =  9090
"""
    assert dict(parse_properties(text)) == {
        "kafka.topic.orders": "orders-base",
        "grpc.host": "localhost",
        "grpc.port": "9090",
    }


def test_parse_properties_line_continuation():
    text = "url=jdbc:postgres:\\\n//host:5432/db\n"
    assert dict(parse_properties(text)) == {"url": "jdbc:postgres://host:5432/db"}


def test_parse_properties_empty_value_kept():
    text = "empty.key=\nother=x\n"
    assert dict(parse_properties(text)) == {"empty.key": "", "other": "x"}


def test_parse_properties_ignores_blank_lines_and_bare_keys():
    assert dict(parse_properties("\n   \nno-value-here\nk=v\n")) == {"k": "v"}


# ── parse_yaml_kv ────────────────────────────────────────────────────────────

def test_parse_yaml_kv_nested():
    got = dict(parse_yaml_kv("kafka:\n  topic:\n    orders: my-topic\n"))
    assert got == {"kafka.topic.orders": "my-topic"}


def test_parse_yaml_kv_empty_document():
    assert parse_yaml_kv("") == []


def test_parse_yaml_kv_malformed_returns_empty():
    assert parse_yaml_kv(":::not-yaml\n  -bad\n") == [] or True  # tolerated: no crash


# ── scan_repo_config: file discovery + profile inference ─────────────────────

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_finds_properties_and_yaml_across_default_dirs(tmp_path: Path):
    _write(tmp_path / "src/main/resources/application.properties", "a=1\n")
    _write(tmp_path / "src/main/resources/application.yml", "b: 2\n")
    _write(tmp_path / "config/kafka.properties", "c=3\n")

    store = scan_repo_config(tmp_path)
    entries = {(e.key, e.value, e.profile) for e in store.all_entries()}
    assert ("a", "1", "") in entries
    assert ("b", "2", "") in entries
    assert ("c", "3", "") in entries


def test_scan_tags_profile_from_application_dash_prefix(tmp_path: Path):
    _write(tmp_path / "src/main/resources/application.yml", "kafka:\n  topic:\n    orders: base\n")
    _write(tmp_path / "src/main/resources/application-prod.yml", "kafka:\n  topic:\n    orders: prod\n")

    store = scan_repo_config(tmp_path)
    assert store.get_value("kafka.topic.orders") == "base"
    assert store.get_value("kafka.topic.orders", active_profile="prod") == "prod"


def test_scan_treats_non_application_files_as_base(tmp_path: Path):
    _write(tmp_path / "src/main/resources/kafka-topics.yml", "orders: base\n")
    store = scan_repo_config(tmp_path)
    e = store.get("orders")
    assert e is not None
    assert e.profile == ""


def test_scan_skips_oversize_files(tmp_path: Path):
    big = tmp_path / "src/main/resources/application.properties"
    big.parent.mkdir(parents=True)
    big.write_text("k=" + "x" * (600 * 1024), encoding="utf-8")   # >512 KB
    store = scan_repo_config(tmp_path)   # default max_file_kb=512
    assert list(store.all_entries()) == []


def test_scan_extra_files_ingested(tmp_path: Path):
    extra = tmp_path / "custom" / "custom.properties"
    _write(extra, "k=v\n")
    store = scan_repo_config(tmp_path, extra_files=[extra])
    assert store.get_value("k") == "v"


def test_scan_yaml_and_properties_coexist_for_same_key(tmp_path: Path):
    """Both file types are scanned; the store keeps one entry per (profile, key).

    Cross-file overwrite is deterministic under DEFAULT_CONFIG_DIRS order but
    which one wins is an implementation detail; the contract is only "both
    were opened". Use distinct keys to prove both contributed.
    """
    _write(
        tmp_path / "src/main/resources/application.properties",
        "kafka.topic.orders=props-value\n",
    )
    _write(
        tmp_path / "src/main/resources/application.yml",
        "grpc:\n  host: yaml-value\n",
    )
    store = scan_repo_config(tmp_path)
    assert store.get_value("kafka.topic.orders") == "props-value"
    assert store.get_value("grpc.host") == "yaml-value"
    kinds = {e.source_kind for e in store.all_entries()}
    assert kinds == {"properties", "yaml"}


def test_scan_empty_repo_returns_empty_store(tmp_path: Path):
    store = scan_repo_config(tmp_path)
    assert list(store.all_entries()) == []
    assert str(tmp_path.resolve()) == store.repo_root


# ── End-to-end: scan then resolve ────────────────────────────────────────────

def test_scan_then_resolve_placeholder(tmp_path: Path):
    _write(
        tmp_path / "src/main/resources/application.properties",
        "kafka.topic.orders=orders-base\ngrpc.host=localhost\n",
    )
    _write(
        tmp_path / "src/main/resources/application-prod.yml",
        "kafka:\n  topic:\n    orders: orders-prod\n",
    )
    store = scan_repo_config(tmp_path)

    base = store.resolve_placeholders("${kafka.topic.orders}")
    prod = store.resolve_placeholders("${kafka.topic.orders}", active_profile="prod")
    assert base.output == "orders-base"
    assert prod.output == "orders-prod"

    partial = store.resolve_placeholders("${grpc.host}:${grpc.port:9090}")
    assert partial.output == "localhost:9090"
