"""Unit tests for wire.kafka_extractor.scan_config_kafka_bindings.

Covers config-driven Kafka producer/consumer registration — a `topicName`
key alongside a sibling `consumingEnabled` / `producingEnabled` /
`publishingEnabled: true` flag, with no Java-level call site at all. This is
the pattern used by Guice/Dropwizard-style services (e.g. a generic queue
manager reading `KafkaClusterConfig` objects from YAML) that the
Java-source-based extractor cannot see.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from codegraphcontext.wire import (
    ConfigValue,
    ConfigValueStore,
    scan_config_kafka_bindings,
    scan_repo_config,
)
from codegraphcontext.wire.kafka_scanner import scan_repo_kafka


def _add(store: ConfigValueStore, key: str, value: str, source_file: str = "/x/app.yml") -> None:
    store.add(ConfigValue(
        repo_root=store.repo_root, key=key, value=value,
        source_file=source_file, source_kind="yaml",
    ))


def test_consumer_binding_detected_when_enabled_true():
    store = ConfigValueStore(repo_root="/repo")
    _add(store, "streamMapping[0].clusterConfigs[0].topicName", "order-events")
    _add(store, "streamMapping[0].clusterConfigs[0].consumingEnabled", "true")

    result = scan_config_kafka_bindings(store)

    assert len(result.consumers) == 1
    assert result.producers == []
    consumer = result.consumers[0]
    assert consumer.topic_raw == "order-events"
    assert consumer.confidence == "INFERRED"
    assert "config-pattern:consumingenabled" in consumer.provenance


def test_producer_binding_detected_for_publishing_and_producing_flags():
    store = ConfigValueStore(repo_root="/repo")
    _add(store, "producerConfiguration.clusterConfigs[0].topicName", "order-events")
    _add(store, "producerConfiguration.clusterConfigs[0].publishingEnabled", "true")
    _add(store, "producerConfiguration.clusterConfigs[1].topicName", "other_topic")
    _add(store, "producerConfiguration.clusterConfigs[1].producingEnabled", "true")

    result = scan_config_kafka_bindings(store)

    assert result.consumers == []
    topics = sorted(p.topic_raw for p in result.producers)
    assert topics == ["order-events", "other_topic"]
    assert all(p.confidence == "INFERRED" for p in result.producers)


def test_disabled_flag_is_not_reported():
    store = ConfigValueStore(repo_root="/repo")
    _add(store, "clusterConfigs[0].topicName", "unused_topic")
    _add(store, "clusterConfigs[0].consumingEnabled", "false")

    result = scan_config_kafka_bindings(store)

    assert result.consumers == []
    assert result.producers == []


def test_topic_key_without_enabled_sibling_is_not_reported():
    store = ConfigValueStore(repo_root="/repo")
    _add(store, "clusterConfigs[0].topicName", "orphan_topic")

    result = scan_config_kafka_bindings(store)

    assert result.consumers == []
    assert result.producers == []


def test_siblings_across_different_parents_are_not_cross_matched():
    store = ConfigValueStore(repo_root="/repo")
    _add(store, "clusterConfigs[0].topicName", "topic_a")
    _add(store, "clusterConfigs[1].consumingEnabled", "true")  # different parent, no topic sibling here

    result = scan_config_kafka_bindings(store)

    assert result.consumers == []
    assert result.producers == []


def test_end_to_end_via_scan_repo_kafka_and_scan_repo_config(tmp_path: Path):
    """Mirrors a typical Guice/Dropwizard notification-worker YAML shape."""
    (tmp_path / "dev.yml").write_text(
        """
        notification:
          consumer:
            streamMapping:
              - streamField: gns
                clusterConfigs:
                  - clusterName: MSKCluster
                    consumingEnabled: true
                    topicName: order-events
        """,
        encoding="utf-8",
    )
    store = scan_repo_config(tmp_path, include_dirs=(".",))
    result = scan_repo_kafka(tmp_path, store=store)

    assert len(result.consumers) == 1
    assert result.consumers[0].topic_raw == "order-events"
    assert result.consumers[0].confidence == "INFERRED"
