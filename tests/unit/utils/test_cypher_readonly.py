from codegraphcontext.utils import cypher_readonly
from codegraphcontext.utils.cypher_readonly import is_read_only_cypher


def test_allows_read_queries():
    assert is_read_only_cypher("MATCH (n) RETURN n LIMIT 1")
    assert is_read_only_cypher("MATCH (n) WHERE n.name = 'CREATE' RETURN n")


def test_blocks_write_keywords():
    assert not is_read_only_cypher("CREATE (n:Foo {name: 'x'})")
    assert not is_read_only_cypher("MATCH (n) DELETE n")
    assert not is_read_only_cypher("MATCH (n) SET n.x = 1")
    assert not is_read_only_cypher("COPY tbl FROM '/tmp/x'")
    assert not is_read_only_cypher("ALTER TABLE Foo ADD col INT")


def test_blocks_apoc_and_subquery_calls():
    assert not is_read_only_cypher("CALL apoc.load.json('file:///tmp/x') YIELD value RETURN value")
    assert not is_read_only_cypher("CALL { MATCH (n) RETURN n } RETURN 1")
    assert not is_read_only_cypher("CALL db.index.fulltext.createNodeIndex('idx', ['Person'], ['name'])")
    assert not is_read_only_cypher("CALL dbms.security.createUser('x', 'y', false)")


def test_blocks_multi_statement_queries():
    assert not is_read_only_cypher("MATCH (n) RETURN n; DELETE n")


def test_ignores_write_keywords_in_comments():
    assert is_read_only_cypher("// CREATE (n)\nMATCH (n) RETURN n")


def test_blocks_write_apoc_procedures():
    # Write-side APOC namespaces must be rejected, whether called or inline.
    assert not is_read_only_cypher("CALL apoc.create.node(['L'], {}) YIELD node RETURN node")
    assert not is_read_only_cypher("CALL apoc.merge.node(['L'], {id: 1}) YIELD node RETURN node")
    assert not is_read_only_cypher("CALL apoc.refactor.mergeNodes([n]) YIELD node RETURN node")
    assert not is_read_only_cypher(
        "CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DELETE n', {}) YIELD batches RETURN batches"
    )
    # Inline (non-CALL) invocation of a write namespace is still rejected.
    assert not is_read_only_cypher("RETURN apoc.create.uuid() AS id")


def test_keyword_as_substring_not_false_positive():
    # A variable/identifier that merely contains a write keyword as a substring
    # (e.g. `created`, `deleted`, `Asset`) must NOT be rejected.
    assert is_read_only_cypher("MATCH (n) WHERE n.created > 0 RETURN n.created AS created")
    assert is_read_only_cypher("MATCH (n) RETURN n.deleted AS deleted")
    assert is_read_only_cypher("MATCH (n:Asset) RETURN n")
    # Read-only APOC helpers (path/coll/text) are still permitted inline.
    assert is_read_only_cypher("RETURN apoc.coll.max([1, 2, 3]) AS m")


def test_rejection_is_logged_with_the_offending_keyword(monkeypatch):
    """Rejections must leave an audit trail naming the reason."""
    logged = []
    monkeypatch.setattr(cypher_readonly, "warning_logger", logged.append)

    assert not cypher_readonly.is_read_only_cypher("MATCH (n) DELETE n")

    assert len(logged) == 1
    assert "DELETE" in logged[0]


def test_every_rejection_path_logs_exactly_once(monkeypatch):
    logged = []
    monkeypatch.setattr(cypher_readonly, "warning_logger", logged.append)

    cases = {
        "": "empty",
        "   ": "empty",
        "MATCH (n) RETURN n; MATCH (m) RETURN m": "multiple statements",
        "CREATE (n:Foo)": "CREATE",
        # Hits a forbidden *pattern* rather than a keyword. (apoc.create would
        # not do: the keyword loop runs first and catches its "create".)
        "CALL dbms.components()": "dbms",
    }
    for query, expected_fragment in cases.items():
        logged.clear()
        assert not cypher_readonly.is_read_only_cypher(query)
        assert len(logged) == 1, f"expected one log line for {query!r}, got {logged}"
        assert expected_fragment.lower() in logged[0].lower(), (
            f"{logged[0]!r} does not mention {expected_fragment!r}"
        )


def test_accepted_queries_log_nothing(monkeypatch):
    logged = []
    monkeypatch.setattr(cypher_readonly, "warning_logger", logged.append)

    assert cypher_readonly.is_read_only_cypher("MATCH (n) RETURN n LIMIT 1")

    assert logged == []


def test_rejection_log_does_not_leak_query_text(monkeypatch):
    """A rejected query may carry caller-supplied literals; keep them out."""
    logged = []
    monkeypatch.setattr(cypher_readonly, "warning_logger", logged.append)

    assert not cypher_readonly.is_read_only_cypher(
        "CREATE (n:Secret {token: 'hunter2-super-secret'})"
    )

    assert logged
    assert "hunter2-super-secret" not in logged[0]
