"""Unit tests for wire.http_scanner (MULTI_REPO_LINKS PR #5)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import scan_repo_http


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_empty_repo(tmp_path: Path):
    r = scan_repo_http(tmp_path)
    assert r.servers == [] and r.clients == []
    assert r.files_scanned == 0


def test_scan_finds_spring_controller(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Api.java", """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/x") public void x() {} }
    """)
    r = scan_repo_http(tmp_path)
    assert len(r.servers) == 1
    assert r.servers[0].path == "/x"


def test_scan_finds_rest_template_client(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Client.java", """
        package com.acme;
        import org.springframework.web.client.RestTemplate;
        class Client { RestTemplate rt; void call() { rt.getForObject("/a", String.class); } }
    """)
    r = scan_repo_http(tmp_path)
    assert len(r.clients) == 1
    assert r.clients[0].path == "/a"


def test_scan_skips_non_http_files(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Plain.java", "package com.acme; class Plain {}\n")
    r = scan_repo_http(tmp_path)
    assert r.servers == []
    assert r.files_scanned == 1


def test_scan_skips_oversize_files(tmp_path: Path):
    src = "package com.acme;\nimport org.springframework.web.bind.annotation.*;\n" + ("//" + "x" * 200 + "\n") * 500
    _write(tmp_path / "src/main/java/com/acme/Huge.java", src)
    r = scan_repo_http(tmp_path, max_file_kb=1)
    assert r.files_skipped == 1
    assert any("skipped" in w for w in r.warnings)


def test_scan_dedups_overlapping_include_dirs(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Api.java", """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/x") public void x() {} }
    """)
    r = scan_repo_http(tmp_path, include_dirs=("src/main/java", "."))
    # Same file must not be extracted twice.
    assert len(r.servers) == 1


def test_scan_kotlin_source_dir(tmp_path: Path):
    _write(tmp_path / "src/main/kotlin/com/acme/Api.java", """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/k") public void k() {} }
    """)
    r = scan_repo_http(tmp_path)
    assert any(s.path == "/k" for s in r.servers)
