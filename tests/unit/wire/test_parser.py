"""Wire hint parser: YAML files, CLI shorthand, env var (PR #2)."""

import pytest

from codegraphcontext.wire.hints import (
    SUPPORTED_HINT_VERSION,
    WireHintSource,
    WireHintValidationError,
)
from codegraphcontext.wire.parser import (
    parse_cli_shorthand,
    parse_env_hints,
    parse_wire_yaml,
)


# ── YAML: happy paths ────────────────────────────────────────────────────────

def test_yaml_empty_document_is_legal():
    parsed = parse_wire_yaml("")
    assert parsed.version == SUPPORTED_HINT_VERSION
    assert parsed.topics == []
    assert parsed.endpoints == []
    assert parsed.aliases == []


def test_yaml_minimal_topic():
    text = """
version: 1
topics:
  - system: kafka
    name: orders
    produced_by: [pkg.Publisher.publish]
    consumed_by: [pkg.Listener.consume]
"""
    parsed = parse_wire_yaml(text, source=WireHintSource.REPO, source_path="/repo/.cgc/wire.yml")
    assert len(parsed.topics) == 1
    t = parsed.topics[0]
    assert t.system == "kafka"
    assert t.name == "orders"
    assert t.produced_by == ["pkg.Publisher.publish"]
    assert t.consumed_by == ["pkg.Listener.consume"]
    assert t.merge_key() == ("kafka", "orders")
    assert t.provenance[0].source is WireHintSource.REPO
    assert t.provenance[0].path == "/repo/.cgc/wire.yml"


def test_yaml_endpoint_and_alias():
    text = """
version: 1
endpoints:
  - protocol: grpc
    method: GetStatus
    path: com.example.status.v1.StatusService/GetStatus
    served_by: [srv.Impl.get]
    invoked_by: [cli.Stub.get]
aliases:
  topics:
    - canonical: orders
      names: [orders-prod, orders-staging]
"""
    parsed = parse_wire_yaml(text)
    assert len(parsed.endpoints) == 1
    e = parsed.endpoints[0]
    assert e.merge_key() == ("grpc", "GetStatus", "com.example.status.v1.StatusService/GetStatus")
    assert e.served_by == ["srv.Impl.get"]
    assert e.invoked_by == ["cli.Stub.get"]

    assert len(parsed.aliases) == 1
    a = parsed.aliases[0]
    assert a.kind == "topics"
    assert a.canonical == "orders"
    assert a.aliases == ["orders-prod", "orders-staging"]


# ── YAML: hard errors ────────────────────────────────────────────────────────

def test_yaml_top_level_not_mapping_rejected():
    with pytest.raises(WireHintValidationError, match="mapping"):
        parse_wire_yaml("- just_a_list")


def test_yaml_unsupported_version_rejected():
    with pytest.raises(WireHintValidationError, match="version"):
        parse_wire_yaml("version: 999")


def test_yaml_topic_missing_name_rejected():
    with pytest.raises(WireHintValidationError, match="topics\\[0\\].name"):
        parse_wire_yaml("version: 1\ntopics:\n  - system: kafka\n")


def test_yaml_topic_produced_by_wrong_shape_rejected():
    with pytest.raises(WireHintValidationError, match="produced_by"):
        parse_wire_yaml(
            "version: 1\ntopics:\n  - {system: kafka, name: orders, produced_by: 'not-a-list'}\n"
        )


def test_yaml_endpoint_missing_path_rejected():
    with pytest.raises(WireHintValidationError, match="endpoints\\[0\\].path"):
        parse_wire_yaml(
            "version: 1\nendpoints:\n  - {protocol: http, method: GET}\n"
        )


# ── YAML: non-fatal warnings ─────────────────────────────────────────────────

def test_yaml_unknown_topic_system_warns_but_keeps_hint():
    parsed = parse_wire_yaml(
        "version: 1\ntopics:\n  - {system: brainwave, name: xyz}\n"
    )
    assert len(parsed.topics) == 1
    assert any("brainwave" in w for w in parsed.warnings)


def test_yaml_unknown_top_level_key_warns():
    parsed = parse_wire_yaml("version: 1\nunknown_key: foo\n")
    assert any("unknown top-level keys" in w for w in parsed.warnings)


# ── CLI shorthand ────────────────────────────────────────────────────────────

def test_cli_shorthand_topic_producer():
    f = parse_cli_shorthand("kafka:orders=produced_by:pkg.Pub.publish")
    assert len(f.topics) == 1
    t = f.topics[0]
    assert t.system == "kafka"
    assert t.name == "orders"
    assert t.produced_by == ["pkg.Pub.publish"]
    assert t.consumed_by == []
    assert t.provenance[0].source is WireHintSource.CLI


def test_cli_shorthand_topic_consumer():
    f = parse_cli_shorthand("kafka:orders=consumed_by:pkg.Sub.consume")
    assert f.topics[0].consumed_by == ["pkg.Sub.consume"]
    assert f.topics[0].produced_by == []


def test_cli_shorthand_endpoint_grpc():
    f = parse_cli_shorthand("grpc:GetPresence:svc.PresenceService/GetPresence=served_by:pkg.Impl.get")
    assert len(f.endpoints) == 1
    e = f.endpoints[0]
    assert e.protocol == "grpc"
    assert e.method == "GetPresence"
    assert e.path == "svc.PresenceService/GetPresence"
    assert e.served_by == ["pkg.Impl.get"]


def test_cli_shorthand_endpoint_http():
    f = parse_cli_shorthand("http:POST:/v1/x=invoked_by:pkg.Client.call")
    assert f.endpoints[0].method == "POST"
    assert f.endpoints[0].path == "/v1/x"
    assert f.endpoints[0].invoked_by == ["pkg.Client.call"]


def test_cli_shorthand_missing_equals_rejected():
    with pytest.raises(WireHintValidationError, match="expected"):
        parse_cli_shorthand("kafka:orders")


def test_cli_shorthand_unknown_scheme_rejected():
    with pytest.raises(WireHintValidationError, match="unknown scheme"):
        parse_cli_shorthand("mystery:orders=produced_by:pkg.X.y")


def test_cli_shorthand_wrong_role_for_topic_rejected():
    with pytest.raises(WireHintValidationError, match="invalid for topic"):
        parse_cli_shorthand("kafka:orders=served_by:pkg.X.y")


def test_cli_shorthand_wrong_role_for_endpoint_rejected():
    with pytest.raises(WireHintValidationError, match="invalid for endpoint"):
        parse_cli_shorthand("http:GET:/x=produced_by:pkg.X.y")


# ── Env var ──────────────────────────────────────────────────────────────────

def test_env_parses_multiline_and_ignores_comments_and_blanks():
    env = """
# comment
kafka:orders=produced_by:pkg.Pub.publish

grpc:GetPresence:svc/rpc=served_by:pkg.Srv.get
"""
    files = parse_env_hints(env)
    assert len(files) == 2
    assert files[0].topics and files[0].topics[0].name == "orders"
    assert files[1].endpoints and files[1].endpoints[0].method == "GetPresence"
    assert files[0].topics[0].provenance[0].source is WireHintSource.ENV


def test_env_empty_input_returns_empty_list():
    assert parse_env_hints(None) == []
    assert parse_env_hints("") == []
    assert parse_env_hints("# only a comment") == []
