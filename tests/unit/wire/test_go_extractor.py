"""Unit tests for wire.go_extractor (MULTI_REPO_LINKS PR #7)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import extract_go_from_source, looks_like_go_http_source


P = Path("main.go")


def _extract(src: str):
    return extract_go_from_source(src, P)


def test_looks_like_triggers_on_common_signals():
    assert looks_like_go_http_source('import "net/http"')
    assert looks_like_go_http_source('import "github.com/gin-gonic/gin"')
    assert not looks_like_go_http_source("package main\nfunc main() {}")


def test_gin_get_route():
    src = """
package main
import "github.com/gin-gonic/gin"
func main() {
    r := gin.Default()
    r.GET("/hello", helloHandler)
}
"""
    r = _extract(src)
    assert len(r.servers) == 1
    s = r.servers[0]
    assert s.method == "GET"
    assert s.path == "/hello"
    assert s.framework == "gin_or_echo_or_chi"
    assert s.fqn == "main.helloHandler"


def test_net_http_handle_func_uses_wildcard_verb():
    src = """
package main
import "net/http"
func main() {
    http.HandleFunc("/x", xHandler)
}
"""
    r = _extract(src)
    assert len(r.servers) == 1
    s = r.servers[0]
    assert s.method == "*"
    assert s.framework == "net_http"


def test_gorilla_mux_methods_records_specific_verb():
    src = """
package main
import "github.com/gorilla/mux"
func main() {
    r := mux.NewRouter()
    r.HandleFunc("/x", xHandler).Methods("POST")
}
"""
    r = _extract(src)
    # Should record POST via gorilla; the fallback net_http rule must not double-add "/x".
    posts = [s for s in r.servers if s.method == "POST" and s.path == "/x"]
    stars = [s for s in r.servers if s.method == "*" and s.path == "/x"]
    assert len(posts) == 1
    assert stars == []


def test_multiple_verbs_on_same_router():
    src = """
package main
import "github.com/gin-gonic/gin"
func main() {
    r := gin.Default()
    r.GET("/a", a)
    r.POST("/a", a)
}
"""
    r = _extract(src)
    verbs = sorted(s.method for s in r.servers)
    assert verbs == ["GET", "POST"]


def test_non_http_source_yields_empty():
    r = _extract("package main\nfunc main() {}")
    assert r.is_empty()
