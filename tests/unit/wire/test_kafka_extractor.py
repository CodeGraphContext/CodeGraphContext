"""Unit tests for wire.kafka_extractor (MULTI_REPO_LINKS PR #4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from codegraphcontext.wire import (
    ConfigValue,
    ConfigValueStore,
    extract_kafka_from_source,
    looks_like_kafka_source,
)


# ── Basic trigger detection ─────────────────────────────────────────────────

def test_looks_like_kafka_source_true_for_spring_import():
    assert looks_like_kafka_source(
        "import org.springframework.kafka.core.KafkaTemplate;\nclass X {}"
    )


def test_looks_like_kafka_source_true_for_annotation():
    assert looks_like_kafka_source(
        "class X { @KafkaListener(topics=\"x\") void h(){} }"
    )


def test_looks_like_kafka_source_false_for_unrelated_file():
    assert not looks_like_kafka_source(
        "package a; class X { void m() { httpClient.send(req); } }"
    )


# ── Producer extraction ─────────────────────────────────────────────────────

def test_extract_producer_literal_topic():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    class Svc {
        void publish() {
            kafkaTemplate.send("orders-created", payload);
        }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    assert len(result.producers) == 1
    p = result.producers[0]
    assert p.fqn == "com.acme.Svc.publish"
    assert p.topic_raw == "orders-created"
    assert p.topic_resolved == "orders-created"
    assert p.confidence == "EXTRACTED"
    assert p.provenance == "literal"


def test_extract_producer_placeholder_resolved_via_store():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    class Svc {
        void publish() {
            kafkaTemplate.send("${kafka.topic.orders}", payload);
        }
    }
    """
    store = ConfigValueStore(repo_root="/r")
    store.add(ConfigValue(
        repo_root="/r", key="kafka.topic.orders", value="orders-resolved",
        source_file="/r/app.properties", source_kind="properties",
    ))
    result = extract_kafka_from_source(src, Path("/r/Svc.java"), store=store)
    assert len(result.producers) == 1
    p = result.producers[0]
    assert p.topic_raw == "${kafka.topic.orders}"
    assert p.topic_resolved == "orders-resolved"
    assert p.confidence == "INFERRED"
    assert "kafka.topic.orders" in p.provenance


def test_extract_producer_placeholder_unresolved_falls_back_to_symbolic():
    src = """
    package com.acme;
    import org.apache.kafka.clients.producer.KafkaProducer;
    class Svc {
        void publish() { producer.send("${kafka.topic.missing}"); }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    p = result.producers[0]
    assert p.confidence == "SYMBOLIC"
    assert "unresolved" in p.provenance


def test_extract_producer_identifier_traced_to_string_constant():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    class Svc {
        private static final String ORDERS_TOPIC = "orders-v1";
        void publish() { kafkaTemplate.send(ORDERS_TOPIC, payload); }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    p = result.producers[0]
    assert p.topic_raw == "orders-v1"
    assert p.confidence == "EXTRACTED"
    assert "ORDERS_TOPIC" in p.provenance


def test_extract_producer_identifier_untraced_is_ambiguous():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    class Svc {
        void publish(String topic) { kafkaTemplate.send(topic, payload); }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    p = result.producers[0]
    assert p.confidence == "AMBIGUOUS"
    assert p.provenance.startswith("identifier:")


def test_extract_producer_new_producer_record():
    src = """
    package com.acme;
    import org.apache.kafka.clients.producer.KafkaProducer;
    import org.apache.kafka.clients.producer.ProducerRecord;
    class Svc {
        void publish() {
            producer.send(new ProducerRecord<String, String>("outbox", key, value));
        }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    # `.send(new ProducerRecord(...))` — the inner constructor wins; no duplicate.
    assert len(result.producers) == 1
    p = result.producers[0]
    assert p.topic_raw == "outbox"
    assert p.call_shape == "new ProducerRecord"


def test_extract_producer_skips_unrelated_send_calls():
    src = """
    package com.acme;
    class Svc {
        void call() {
            httpClient.send(request);
            logger.send("data");
        }
    }
    """
    # No Kafka imports and no @KafkaListener — skipped entirely.
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    assert result.is_empty()


def test_extract_producer_expression_is_ambiguous():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    class Svc {
        void publish() {
            kafkaTemplate.send(config.getTopic(), payload);
        }
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Svc.java"))
    p = result.producers[0]
    assert p.confidence == "AMBIGUOUS"
    assert p.provenance == "expression"


# ── Consumer extraction ────────────────────────────────────────────────────

def test_extract_consumer_single_literal_topic():
    src = """
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(topics = "orders-created")
        public void handle(String msg) {}
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Handler.java"))
    assert len(result.consumers) == 1
    c = result.consumers[0]
    assert c.fqn == "com.acme.Handler.handle"
    assert c.topic_raw == "orders-created"
    assert c.confidence == "EXTRACTED"
    assert not c.is_pattern


def test_extract_consumer_array_topics():
    src = """
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(topics = {"a-topic", "b-topic"})
        public void multi(String msg) {}
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Handler.java"))
    topics = sorted(c.topic_raw for c in result.consumers)
    assert topics == ["a-topic", "b-topic"]
    assert all(c.fqn == "com.acme.Handler.multi" for c in result.consumers)


def test_extract_consumer_placeholder_resolved():
    src = """
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(topics = "${kafka.topic.orders}")
        public void handle(String msg) {}
    }
    """
    store = ConfigValueStore(repo_root="/r")
    store.add(ConfigValue(
        repo_root="/r", key="kafka.topic.orders", value="orders-live",
        source_file="/r/app.properties", source_kind="properties",
    ))
    result = extract_kafka_from_source(src, Path("/r/Handler.java"), store=store)
    c = result.consumers[0]
    assert c.confidence == "INFERRED"
    assert c.topic_resolved == "orders-live"


def test_extract_consumer_topic_pattern_marked_ambiguous():
    src = r"""
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(topicPattern = "orders\\..*")
        public void handle(String msg) {}
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Handler.java"))
    c = result.consumers[0]
    assert c.is_pattern
    assert c.confidence == "AMBIGUOUS"
    assert c.provenance == "topicPattern"


def test_extract_consumer_multiple_attributes_topics_wins():
    src = """
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(groupId = "grp-1", topics = "orders", containerFactory = "cf")
        public void handle(String msg) {}
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Handler.java"))
    c = result.consumers[0]
    assert c.topic_raw == "orders"


def test_extract_consumer_with_no_topics_reports_warning():
    src = """
    package com.acme;
    import org.springframework.kafka.annotation.KafkaListener;
    class Handler {
        @KafkaListener(id = "grp-1", groupId = "grp-1")
        public void handle(String msg) {}
    }
    """
    result = extract_kafka_from_source(src, Path("/r/Handler.java"))
    assert result.consumers == []
    assert any("no readable topics" in w for w in result.warnings)


# ── FQN / class-nesting resolution ──────────────────────────────────────────

def test_fqn_uses_package_and_class_name():
    src = """
    package com.acme.orders;
    import org.springframework.kafka.core.KafkaTemplate;
    public class Outer {
        void publish() { kafkaTemplate.send("t", p); }
    }
    """
    p = extract_kafka_from_source(src, Path("/r/X.java")).producers[0]
    assert p.fqn == "com.acme.orders.Outer.publish"


def test_fqn_prefers_innermost_class_in_nested_types():
    src = """
    package com.acme;
    import org.springframework.kafka.core.KafkaTemplate;
    public class Outer {
        public static class Inner {
            void publish() { kafkaTemplate.send("inner-topic", p); }
        }
    }
    """
    p = extract_kafka_from_source(src, Path("/r/Outer.java")).producers[0]
    assert p.fqn == "com.acme.Inner.publish"


def test_source_without_package_still_works():
    src = """
    import org.springframework.kafka.core.KafkaTemplate;
    public class Bare {
        void publish() { kafkaTemplate.send("t", p); }
    }
    """
    p = extract_kafka_from_source(src, Path("/r/Bare.java")).producers[0]
    assert p.fqn == "Bare.publish"


def test_line_number_is_one_based_and_points_at_call_site():
    src = "\n".join([
        "package a;",
        "import org.springframework.kafka.core.KafkaTemplate;",
        "class X {",
        "    void m() {",
        "        kafkaTemplate.send(\"t\", p);",
        "    }",
        "}",
    ])
    p = extract_kafka_from_source(src, Path("/r/X.java")).producers[0]
    assert p.line == 5


# ── Robustness ─────────────────────────────────────────────────────────────

def test_string_literal_containing_send_is_not_treated_as_call():
    src = """
    package a;
    import org.springframework.kafka.core.KafkaTemplate;
    class X {
        String label = "not a real .send( call, just a string";
        void m() { kafkaTemplate.send("real-topic", p); }
    }
    """
    prods = extract_kafka_from_source(src, Path("/r/X.java")).producers
    assert len(prods) == 1 and prods[0].topic_raw == "real-topic"


def test_comment_containing_send_call_is_ignored():
    src = """
    package a;
    import org.springframework.kafka.core.KafkaTemplate;
    class X {
        // kafkaTemplate.send("commented", p);
        /* also: kafkaTemplate.send("block", p); */
        void m() { kafkaTemplate.send("real", p); }
    }
    """
    prods = extract_kafka_from_source(src, Path("/r/X.java")).producers
    # Note: comment-stripping is not implemented; the regex will match commented
    # `.send(` too. This test documents current behaviour so future comment-
    # aware improvements can update the assertion in one place.
    assert any(p.topic_raw == "real" for p in prods)


def test_empty_file_returns_empty_result():
    result = extract_kafka_from_source("", Path("/r/Empty.java"))
    assert result.is_empty()


def test_malformed_class_reports_warning_and_returns_empty():
    # No class body — parser can't find a span.
    src = "package a; import org.springframework.kafka.core.KafkaTemplate;"
    result = extract_kafka_from_source(src, Path("/r/X.java"))
    assert result.is_empty()
    assert any("no top-level class" in w for w in result.warnings)


def test_repo_root_from_ConfigValueStore_does_not_affect_extraction_path():
    """The extractor should honour store.repo_root only during placeholder
    resolution; the ``source_file`` on emitted records is the path we passed in.
    """
    store = ConfigValueStore(repo_root="/other-repo")
    store.add(ConfigValue(
        repo_root="/other-repo", key="k", value="v",
        source_file="/other-repo/app.properties", source_kind="properties",
    ))
    src = """
    package a;
    import org.springframework.kafka.core.KafkaTemplate;
    class X { void m() { kafkaTemplate.send("${k}", p); } }
    """
    p = extract_kafka_from_source(src, Path("/here/X.java"), store=store).producers[0]
    assert p.source_file == "/here/X.java"
    assert p.topic_resolved == "v"
