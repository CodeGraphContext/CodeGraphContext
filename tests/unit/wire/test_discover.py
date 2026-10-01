"""Unit tests for wire.discover cross-repo aggregation (MULTI_REPO_LINKS PR #8)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import discover


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_producer_repo(root: Path) -> None:
    _write(root / "src/main/java/com/acme/Prod.java", """
        package com.acme;
        import org.springframework.kafka.core.KafkaTemplate;
        class Prod { KafkaTemplate<String,String> kt; void go() { kt.send("orders", "p"); } }
    """)


def _make_consumer_repo(root: Path) -> None:
    _write(root / "src/main/java/com/acme/Cons.java", """
        package com.acme;
        import org.springframework.kafka.annotation.KafkaListener;
        class Cons {
            @KafkaListener(topics = "orders")
            public void h(String s) {}
        }
    """)


def _make_http_server_repo(root: Path) -> None:
    _write(root / "src/main/java/com/acme/Api.java", """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/x") public void x() {} }
    """)


def _make_http_client_repo(root: Path) -> None:
    _write(root / "src/main/java/com/acme/Client.java", """
        package com.acme;
        import org.springframework.web.client.RestTemplate;
        class Client { RestTemplate rt; void call() { rt.getForObject("/x", String.class); } }
    """)


def test_matched_kafka_topic_across_two_repos(tmp_path: Path):
    a = tmp_path / "repoA"; b = tmp_path / "repoB"
    _make_producer_repo(a); _make_consumer_repo(b)
    r = discover([a, b])
    matched = r.matched_topics()
    assert len(matched) == 1
    assert matched[0].identity.name == "orders"
    assert matched[0].producers[0]["repo"] != matched[0].consumers[0]["repo"]


def test_matched_http_endpoint_across_two_repos(tmp_path: Path):
    a = tmp_path / "repoA"; b = tmp_path / "repoB"
    _make_http_server_repo(a); _make_http_client_repo(b)
    r = discover([a, b])
    matched = r.matched_endpoints()
    assert len(matched) == 1
    e = matched[0]
    assert e.identity.protocol == "http"
    assert e.identity.method == "GET"
    assert e.identity.path == "/x"


def test_orphan_producer_reported_when_no_consumer_present(tmp_path: Path):
    a = tmp_path / "repoA"
    _make_producer_repo(a)
    r = discover([a])
    assert r.orphan_producers()
    assert not r.matched_topics()


def test_orphan_consumer_reported_when_no_producer_present(tmp_path: Path):
    a = tmp_path / "repoA"
    _make_consumer_repo(a)
    r = discover([a])
    assert r.orphan_consumers()


def test_orphan_server_reported_when_no_client_present(tmp_path: Path):
    a = tmp_path / "repoA"
    _make_http_server_repo(a)
    r = discover([a])
    assert r.orphan_servers()


def test_orphan_client_reported_when_no_server_present(tmp_path: Path):
    a = tmp_path / "repoA"
    _make_http_client_repo(a)
    r = discover([a])
    assert r.orphan_clients()


def test_per_repo_stats_capture_counts(tmp_path: Path):
    a = tmp_path / "repoA"
    _make_producer_repo(a); _make_http_server_repo(a)
    r = discover([a])
    stats = r.per_repo_stats[str(a.resolve())]
    assert stats["kafka_producers"] == 1
    assert stats["http_servers_java"] == 1


def test_cross_language_http_server_matches_java_client(tmp_path: Path):
    """Python Flask server + Java RestTemplate client on the same path must match."""
    a = tmp_path / "repoA"; b = tmp_path / "repoB"
    _write(a / "app.py", """
from flask import Flask
app = Flask(__name__)
@app.route("/x")
def x(): return "hi"
""")
    _make_http_client_repo(b)
    r = discover([a, b])
    matched = r.matched_endpoints()
    # Flask emits GET /x; RestTemplate.getForObject also GET /x → identity should match.
    assert any(e.identity.method == "GET" and e.identity.path == "/x" for e in matched)


def test_empty_repos_return_empty_discovery(tmp_path: Path):
    r = discover([tmp_path])
    assert not r.topics
    assert not r.endpoints
