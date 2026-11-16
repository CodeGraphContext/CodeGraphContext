"""ConfigValueStore + placeholder resolver (PR #3)."""

from codegraphcontext.wire import BASE_PROFILE, ConfigValue, ConfigValueStore, flatten_yaml


def _mk(key: str, value: str, *, profile: str = BASE_PROFILE, repo: str = "/repo") -> ConfigValue:
    return ConfigValue(
        repo_root=repo, key=key, value=value,
        source_file=f"{repo}/src/main/resources/application{'-' + profile if profile else ''}.yml",
        source_kind="yaml", profile=profile,
    )


# ── Basic store behavior ─────────────────────────────────────────────────────

def test_store_get_falls_back_from_profile_to_base():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("kafka.topic.orders", "orders-base"))
    s.add(_mk("kafka.topic.orders", "orders-prod", profile="prod"))
    assert s.get_value("kafka.topic.orders") == "orders-base"
    assert s.get_value("kafka.topic.orders", active_profile="prod") == "orders-prod"
    # A profile with no override for the key falls back to base.
    assert s.get_value("kafka.topic.orders", active_profile="staging") == "orders-base"


def test_store_get_missing_key_is_none():
    s = ConfigValueStore(repo_root="/repo")
    assert s.get_value("nope") is None


def test_store_merge_key_matches_schema_contract():
    e = _mk("kafka.topic.orders", "orders-base")
    assert e.merge_key() == ("/repo", "kafka.topic.orders")


def test_store_rejects_foreign_repo_root():
    s = ConfigValueStore(repo_root="/repo")
    import pytest
    with pytest.raises(ValueError, match="repo_root"):
        s.add(_mk("k", "v", repo="/other-repo"))


# ── Placeholder resolution ───────────────────────────────────────────────────

def test_resolve_single_placeholder_base():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("kafka.topic.orders", "orders"))
    r = s.resolve_placeholders("${kafka.topic.orders}")
    assert r.output == "orders"
    assert r.fully_resolved()
    assert r.is_pure_placeholder()
    assert r.used == [("kafka.topic.orders", "base")]
    assert r.unresolved == []


def test_resolve_prefers_active_profile_over_base():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("k", "base"))
    s.add(_mk("k", "prod-value", profile="prod"))
    r = s.resolve_placeholders("${k}", active_profile="prod")
    assert r.output == "prod-value"
    assert r.used == [("k", "profile:prod")]


def test_resolve_uses_default_when_key_missing():
    s = ConfigValueStore(repo_root="/repo")
    r = s.resolve_placeholders("${grpc.port:9090}")
    assert r.output == "9090"
    assert r.fully_resolved()
    assert r.used == [("grpc.port", "default")]


def test_resolve_leaves_unresolved_placeholder_intact():
    s = ConfigValueStore(repo_root="/repo")
    r = s.resolve_placeholders("${no.such.key}")
    assert r.output == "${no.such.key}"
    assert not r.fully_resolved()
    assert r.unresolved == ["no.such.key"]


def test_resolve_mixes_literal_text_and_placeholders():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("host", "prod.internal"))
    r = s.resolve_placeholders("${host}:${port:5555}/api")
    assert r.output == "prod.internal:5555/api"
    assert r.used == [("host", "base"), ("port", "default")]


def test_resolve_not_pure_placeholder_when_surrounding_text():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("k", "v"))
    r = s.resolve_placeholders("prefix-${k}-suffix")
    assert not r.is_pure_placeholder()
    assert r.output == "prefix-v-suffix"


# ── flatten_yaml ─────────────────────────────────────────────────────────────

def test_flatten_yaml_nested_dict():
    doc = {"kafka": {"topic": {"orders": "my-topic", "refunds": "refund-topic"}}}
    got = dict(flatten_yaml(doc))
    assert got == {"kafka.topic.orders": "my-topic", "kafka.topic.refunds": "refund-topic"}


def test_flatten_yaml_stringifies_scalar_leaves():
    doc = {"port": 9090, "flag": True, "ratio": 1.5, "empty": None}
    got = dict(flatten_yaml(doc))
    assert got == {"port": "9090", "flag": "True", "ratio": "1.5", "empty": ""}


def test_flatten_yaml_lists_use_index_suffix():
    doc = {"brokers": ["a", "b"]}
    got = dict(flatten_yaml(doc))
    assert got == {"brokers[0]": "a", "brokers[1]": "b"}


# ── known_profiles + all_entries ─────────────────────────────────────────────

def test_store_known_profiles_and_all_entries():
    s = ConfigValueStore(repo_root="/repo")
    s.add(_mk("a", "1"))
    s.add(_mk("b", "2", profile="prod"))
    s.add(_mk("c", "3", profile="staging"))
    assert s.known_profiles() == ["", "prod", "staging"]
    assert {(e.key, e.profile) for e in s.all_entries()} == {
        ("a", ""), ("b", "prod"), ("c", "staging"),
    }
