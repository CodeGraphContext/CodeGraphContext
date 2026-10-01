"""Unit tests for wire.http_extractor (MULTI_REPO_LINKS PR #5)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import (
    ConfigValue,
    ConfigValueStore,
    HTTP_METHODS,
    extract_http_from_source,
    looks_like_http_source,
)


P = Path("Svc.java")


def _extract(source: str, store: ConfigValueStore | None = None, profile: str = ""):
    return extract_http_from_source(source, P, store=store, active_profile=profile)


def test_http_methods_covers_the_expected_verbs():
    assert set(HTTP_METHODS) == {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def test_looks_like_http_source_triggers_on_annotations():
    assert looks_like_http_source("@RestController class C {}")
    assert looks_like_http_source("import org.springframework.web.client.RestTemplate;")
    assert not looks_like_http_source("class Plain {}")


def test_get_mapping_literal_path_is_extracted():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api {
            @GetMapping("/hello")
            public String hi() { return "hi"; }
        }
    """
    r = _extract(src)
    assert len(r.servers) == 1
    s = r.servers[0]
    assert s.method == "GET"
    assert s.path == "/hello"
    assert s.confidence == "EXTRACTED"
    assert s.framework == "spring"
    assert s.fqn == "com.acme.Api.hi"


def test_all_mapping_verbs_are_extracted():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api {
            @GetMapping("/a") public void a() {}
            @PostMapping("/b") public void b() {}
            @PutMapping("/c") public void c() {}
            @DeleteMapping("/d") public void d() {}
            @PatchMapping("/e") public void e() {}
        }
    """
    r = _extract(src)
    verbs = {s.method for s in r.servers}
    assert verbs == {"GET", "POST", "PUT", "DELETE", "PATCH"}


def test_class_prefix_from_request_mapping_is_joined():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        @RequestMapping("/api/v1")
        class Api {
            @GetMapping("/things") public void list() {}
        }
    """
    r = _extract(src)
    assert len(r.servers) == 1
    assert r.servers[0].path == "/api/v1/things"


def test_class_not_annotated_as_controller_is_skipped():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        class NotAController {
            @GetMapping("/x") public void x() {}
        }
    """
    r = _extract(src)
    assert r.servers == []


def test_request_mapping_with_method_attribute():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        import org.springframework.web.bind.annotation.RequestMethod;
        @RestController
        class Api {
            @RequestMapping(value = "/x", method = RequestMethod.POST)
            public void x() {}
        }
    """
    r = _extract(src)
    assert len(r.servers) == 1
    assert r.servers[0].method == "POST"
    assert r.servers[0].path == "/x"


def test_rest_template_get_for_object_is_client():
    src = """
        package com.acme;
        import org.springframework.web.client.RestTemplate;
        class Client {
            RestTemplate rt;
            void call() { rt.getForObject("/downstream/{id}", String.class, 42); }
        }
    """
    r = _extract(src)
    assert len(r.clients) == 1
    c = r.clients[0]
    assert c.method == "GET"
    assert c.path == "/downstream/{id}"
    assert c.framework == "restTemplate"


def test_rest_template_post_for_object_is_client():
    src = """
        package com.acme;
        import org.springframework.web.client.RestTemplate;
        class Client { RestTemplate rt; void call() { rt.postForObject("/x", body, String.class); } }
    """
    r = _extract(src)
    assert len(r.clients) == 1
    assert r.clients[0].method == "POST"


def test_web_client_chain_uri_literal():
    src = """
        package com.acme;
        import org.springframework.web.reactive.function.client.WebClient;
        class Client {
            WebClient wc;
            void call() { wc.get().uri("/hello").retrieve().bodyToMono(String.class); }
        }
    """
    r = _extract(src)
    # WebClient chain: expect at least one client record with method GET, path /hello
    assert any(c.method == "GET" and c.path == "/hello" and c.framework == "webClient"
               for c in r.clients)


def test_placeholder_resolves_via_config_store():
    store = ConfigValueStore(repo_root="/tmp/http-test-repo")
    store.add(ConfigValue(
        repo_root="/tmp/http-test-repo",
        key="app.endpoint", value="/resolved",
        source_file="application.properties", source_kind="properties",
        profile="",
    ))
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("${app.endpoint}") public void x() {} }
    """
    r = _extract(src, store=store, profile="")
    assert len(r.servers) == 1
    s = r.servers[0]
    assert s.path == "/resolved"
    assert s.path_raw == "${app.endpoint}"
    assert s.confidence == "INFERRED"


def test_unresolved_placeholder_yields_symbolic_confidence():
    src = """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("${missing.key}") public void x() {} }
    """
    r = _extract(src)
    assert len(r.servers) == 1
    assert r.servers[0].confidence == "SYMBOLIC"


def test_source_file_and_line_are_populated():
    src = "\n\n\n" + """
        package com.acme;
        import org.springframework.web.bind.annotation.*;
        @RestController
        class Api { @GetMapping("/x") public void x() {} }
    """
    r = _extract(src)
    assert r.servers[0].source_file == str(P)
    assert r.servers[0].line > 3


def test_looks_like_returns_false_short_circuits_extract():
    r = _extract("class C {}")
    assert r.is_empty()
