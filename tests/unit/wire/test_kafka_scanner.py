"""Unit tests for wire.kafka_scanner (MULTI_REPO_LINKS PR #4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from codegraphcontext.wire import (
    ConfigValue,
    ConfigValueStore,
    KafkaScanResult,
    scan_repo_kafka,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_empty_repo_returns_empty_result(tmp_path: Path):
    result = scan_repo_kafka(tmp_path)
    assert result.producers == []
    assert result.consumers == []
    assert result.files_scanned == 0


def test_scan_finds_producer_in_src_main_java(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Svc.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Svc { void publish() { kafkaTemplate.send("orders", p); } }
    """)
    result = scan_repo_kafka(tmp_path)
    assert result.files_scanned == 1
    assert len(result.producers) == 1
    assert result.producers[0].topic_raw == "orders"


def test_scan_finds_consumer_and_producer_in_same_repo(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Prod.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Prod { void publish() { kafkaTemplate.send("t", p); } }
    """)
    _write(tmp_path / "src/main/java/com/acme/Cons.java", """
        package com.acme;
        import org.springframework.kafka.annotation.KafkaListener;
        class Cons {
            @KafkaListener(topics = "t")
            public void handle(String msg) {}
        }
    """)
    result = scan_repo_kafka(tmp_path)
    assert len(result.producers) == 1
    assert len(result.consumers) == 1
    assert result.producers[0].topic_raw == "t"
    assert result.consumers[0].topic_raw == "t"


def test_scan_skips_non_java_files(tmp_path: Path):
    _write(tmp_path / "src/main/java/Prod.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class Prod { void publish() { kafkaTemplate.send("t", p); } }
    """)
    _write(tmp_path / "src/main/java/README.md", "not java")
    _write(tmp_path / "src/main/java/app.properties", "kafka.topic=t")
    result = scan_repo_kafka(tmp_path)
    assert result.files_scanned == 1


def test_scan_counts_non_kafka_files_as_scanned(tmp_path: Path):
    _write(tmp_path / "src/main/java/A.java", "package a; class A {}")
    _write(tmp_path / "src/main/java/B.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class B { void m() { kafkaTemplate.send("t", p); } }
    """)
    result = scan_repo_kafka(tmp_path)
    assert result.files_scanned == 2
    assert len(result.producers) == 1


def test_scan_skips_oversized_files(tmp_path: Path):
    _write(tmp_path / "src/main/java/Big.java", "x" * (2 * 1024))
    result = scan_repo_kafka(tmp_path, max_file_kb=1)
    assert result.files_skipped == 1
    assert result.files_scanned == 0
    assert any("skipped" in w for w in result.warnings)


def test_scan_passes_config_store_to_extractor(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Svc.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Svc { void m() { kafkaTemplate.send("${kafka.topic.orders}", p); } }
    """)
    store = ConfigValueStore(repo_root=str(tmp_path))
    store.add(ConfigValue(
        repo_root=str(tmp_path), key="kafka.topic.orders", value="resolved-topic",
        source_file=str(tmp_path / "app.properties"), source_kind="properties",
    ))
    result = scan_repo_kafka(tmp_path, store=store)
    assert result.producers[0].topic_resolved == "resolved-topic"
    assert result.producers[0].confidence == "INFERRED"


def test_scan_respects_active_profile(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Svc.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Svc { void m() { kafkaTemplate.send("${kafka.topic.orders}", p); } }
    """)
    store = ConfigValueStore(repo_root=str(tmp_path))
    store.add(ConfigValue(
        repo_root=str(tmp_path), key="kafka.topic.orders", value="orders-base",
        source_file=str(tmp_path / "app.properties"), source_kind="properties",
    ))
    store.add(ConfigValue(
        repo_root=str(tmp_path), key="kafka.topic.orders", value="orders-prod",
        source_file=str(tmp_path / "app-prod.properties"),
        source_kind="properties", profile="prod",
    ))
    base = scan_repo_kafka(tmp_path, store=store)
    prod = scan_repo_kafka(tmp_path, store=store, active_profile="prod")
    assert base.producers[0].topic_resolved == "orders-base"
    assert prod.producers[0].topic_resolved == "orders-prod"


def test_scan_walks_multiple_include_dirs(tmp_path: Path):
    _write(tmp_path / "module-a/src/main/java/A.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class A { void m() { kafkaTemplate.send("a-topic", p); } }
    """)
    _write(tmp_path / "module-b/src/main/java/B.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class B { void m() { kafkaTemplate.send("b-topic", p); } }
    """)
    result = scan_repo_kafka(
        tmp_path,
        include_dirs=("module-a/src/main/java", "module-b/src/main/java"),
    )
    topics = sorted(p.topic_raw for p in result.producers)
    assert topics == ["a-topic", "b-topic"]


def test_scan_deduplicates_files_across_overlapping_dirs(tmp_path: Path):
    _write(tmp_path / "src/main/java/Svc.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class Svc { void m() { kafkaTemplate.send("t", p); } }
    """)
    result = scan_repo_kafka(
        tmp_path,
        include_dirs=("src/main/java", "src/main/java", "src"),
    )
    # The same file must be processed exactly once.
    assert result.files_scanned == 1
    assert len(result.producers) == 1


def test_scan_missing_include_dir_is_silently_ignored(tmp_path: Path):
    _write(tmp_path / "src/main/java/A.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class A { void m() { kafkaTemplate.send("a", p); } }
    """)
    result = scan_repo_kafka(
        tmp_path,
        include_dirs=("does/not/exist", "src/main/java"),
    )
    assert result.files_scanned == 1
    assert len(result.producers) == 1


def test_scan_default_dirs_include_src_main_java_and_repo_root(tmp_path: Path):
    _write(tmp_path / "src/main/java/A.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class A { void m() { kafkaTemplate.send("a", p); } }
    """)
    _write(tmp_path / "TopLevel.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class TopLevel { void m() { kafkaTemplate.send("t", p); } }
    """)
    result = scan_repo_kafka(tmp_path)
    topics = sorted(p.topic_raw for p in result.producers)
    assert "a" in topics and "t" in topics


def test_scan_result_extend_aggregates_from_multiple_files(tmp_path: Path):
    _write(tmp_path / "src/main/java/A.java", """
        import org.springframework.kafka.annotation.KafkaListener;
        class A {
            @KafkaListener(topics = "a-topic")
            public void h(String s) {}
        }
    """)
    _write(tmp_path / "src/main/java/B.java", """
        import org.springframework.kafka.core.KafkaTemplate;
        class B { void m() { kafkaTemplate.send("b-topic", p); } }
    """)
    result = scan_repo_kafka(tmp_path)
    assert {c.topic_raw for c in result.consumers} == {"a-topic"}
    assert {p.topic_raw for p in result.producers} == {"b-topic"}
