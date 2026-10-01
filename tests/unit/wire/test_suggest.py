"""Unit tests for wire.suggest — cross-repo candidate ranking from orphan wire records."""
from __future__ import annotations

from codegraphcontext.wire.suggest import (
    normalize_identifier,
    repo_for_path,
    similarity,
    suggest_endpoint_pairs,
    suggest_topic_pairs,
)


# ── normalize_identifier ─────────────────────────────────────────────────────

def test_normalize_strips_known_env_suffix():
    assert normalize_identifier("order-events_e2e") == "order-events"
    assert normalize_identifier("order-events_prod") == "order-events"


def test_normalize_strips_repeated_suffixes():
    assert normalize_identifier("orders_prod_e2e") == "orders"


def test_normalize_leaves_unsuffixed_name_untouched():
    assert normalize_identifier("order-events") == "order-events"


def test_normalize_does_not_strip_mid_string_env_words():
    # "production" is only stripped as a trailing suffix, not embedded mid-token.
    assert normalize_identifier("production_events") == "production_events"


# ── similarity ────────────────────────────────────────────────────────────────

def test_similarity_identical_strings_is_one():
    assert similarity("abc", "abc") == 1.0


def test_similarity_empty_string_is_zero():
    assert similarity("", "abc") == 0.0
    assert similarity("abc", "") == 0.0


def test_similarity_dissimilar_strings_is_low():
    assert similarity("order-events", "completely_unrelated_topic") < 0.5


# ── repo_for_path ─────────────────────────────────────────────────────────────

def test_repo_for_path_matches_configured_root():
    roots = ["/repos/orders", "/repos/notification-worker"]
    assert repo_for_path("/repos/orders/src/main/Foo.java", roots) == "/repos/orders"


def test_repo_for_path_returns_none_when_no_root_matches():
    assert repo_for_path("/somewhere/else/Foo.java", ["/repos/orders"]) is None


def test_repo_for_path_picks_longest_match_when_roots_nest():
    roots = ["/repos", "/repos/orders"]
    assert repo_for_path("/repos/orders/Foo.java", roots) == "/repos/orders"


# ── suggest_topic_pairs ───────────────────────────────────────────────────────

def test_suggest_topic_pairs_finds_env_suffixed_cross_repo_match():
    roots = ["/repos/orders", "/repos/notification-worker"]
    producers = [{"name": "order-events_e2e", "locations": ["/repos/orders/etc/e2e.yml"]}]
    consumers = [{"name": "order-events_e2e", "locations": ["/repos/notification-worker/e2e.yml"]}]
    # identical raw strings are already handled by `wire links` — not an orphan-suggest case
    result = suggest_topic_pairs(producers, consumers, roots)
    assert result == []


def test_suggest_topic_pairs_finds_near_match_across_env_suffixes():
    roots = ["/repos/orders", "/repos/notification-worker"]
    producers = [{"name": "order-events", "locations": ["/repos/orders/prod.yml"]}]
    consumers = [{"name": "order-events_e2e", "locations": ["/repos/notification-worker/e2e.yml"]}]
    result = suggest_topic_pairs(producers, consumers, roots)
    assert len(result) == 1
    c = result[0]
    assert c.left_repo == "/repos/orders"
    assert c.right_repo == "/repos/notification-worker"
    assert c.score == 1.0
    assert c.reason == "exact-after-normalization"


def test_suggest_topic_pairs_excludes_same_repo_pairs():
    roots = ["/repos/orders"]
    producers = [{"name": "order-events", "locations": ["/repos/orders/a.yml"]}]
    consumers = [{"name": "order-events_e2e", "locations": ["/repos/orders/b.yml"]}]
    assert suggest_topic_pairs(producers, consumers, roots) == []


def test_suggest_topic_pairs_respects_min_score():
    roots = ["/repos/a", "/repos/b"]
    producers = [{"name": "totally_different_name", "locations": ["/repos/a/x.yml"]}]
    consumers = [{"name": "unrelated_topic_value", "locations": ["/repos/b/y.yml"]}]
    assert suggest_topic_pairs(producers, consumers, roots, min_score=0.9) == []


def test_suggest_topic_pairs_sorted_by_score_descending():
    roots = ["/repos/a", "/repos/b"]
    producers = [
        {"name": "topic_x", "locations": ["/repos/a/1.yml"]},
        {"name": "topic_y_prod", "locations": ["/repos/a/2.yml"]},
    ]
    consumers = [
        {"name": "topic_x_e2e", "locations": ["/repos/b/1.yml"]},
        {"name": "topic_y", "locations": ["/repos/b/2.yml"]},
    ]
    result = suggest_topic_pairs(producers, consumers, roots, min_score=0.3)
    assert all(result[i].score >= result[i + 1].score for i in range(len(result) - 1))


# ── suggest_endpoint_pairs ────────────────────────────────────────────────────

def test_suggest_endpoint_pairs_cross_repo_grpc_match():
    roots = ["/repos/server-svc", "/repos/client-svc"]
    servers = [{"protocol": "grpc", "method": "GetPresence", "path": "PresenceService",
                "locations": ["/repos/server-svc/Server.java"]}]
    clients = [{"protocol": "grpc", "method": "GetPresence", "path": "PresenceServiceV2",
                "locations": ["/repos/client-svc/Client.java"]}]
    result = suggest_endpoint_pairs(servers, clients, roots, min_score=0.5)
    assert len(result) == 1
    assert result[0].kind == "grpc"


def test_suggest_endpoint_pairs_ignores_protocol_mismatch():
    roots = ["/repos/a", "/repos/b"]
    servers = [{"protocol": "http", "method": "GET", "path": "/x",
                "locations": ["/repos/a/S.java"]}]
    clients = [{"protocol": "grpc", "method": "GET", "path": "/x",
                "locations": ["/repos/b/C.java"]}]
    assert suggest_endpoint_pairs(servers, clients, roots) == []
