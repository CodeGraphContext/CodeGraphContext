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


def test_quote_inside_comment_does_not_hide_write_keywords():
    # A quote inside a comment must not open a string literal. Stripping
    # literals before comments let that stray quote pair with a later real
    # quote, deleting the write clause between them and passing the query.
    assert not is_read_only_cypher(
        "MATCH (n) // comment with '\nDELETE n WHERE n.x = 'y' RETURN n"
    )
    assert not is_read_only_cypher(
        'MATCH (n) /* note: " */ DETACH DELETE n WHERE n.name = "x" RETURN n'
    )


def test_backtick_quoted_identifiers_are_not_write_keywords():
    # Cypher escapes keyword-colliding labels/rel-types with backticks.
    assert is_read_only_cypher("MATCH (n)-[r:`DELETE`]->(m) RETURN r")
    assert is_read_only_cypher("MATCH (n) RETURN n.`create` AS c")


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


def test_keywords_in_safe_positions_are_allowed():
    """#1511: a forbidden word is inert as a property, label, param or alias."""
    assert is_read_only_cypher("MATCH (n:Module) RETURN n.load ORDER BY n.load")
    assert is_read_only_cypher("MATCH (n) WHERE n.update > 5 RETURN n")
    assert is_read_only_cypher("MATCH (n) RETURN n.name AS set")
    assert is_read_only_cypher("MATCH (n:Insert) RETURN count(n)")
    assert is_read_only_cypher("MATCH (a)-[r:SET]->(b) RETURN r")
    assert is_read_only_cypher("MATCH (n) RETURN n.merge AS delete, $update")


def test_clause_position_writes_still_rejected_after_1511():
    """The carve-outs must not open a path for real write clauses."""
    assert not is_read_only_cypher("RETURN 1 AS set SET n.x = 1")
    assert not is_read_only_cypher("MATCH (n) WITH n AS delete DELETE n")
    assert not is_read_only_cypher("MATCH (n) SET n.load = 1 RETURN n")
    assert not is_read_only_cypher("LOAD CSV FROM 'file:///x' AS row RETURN row")
    assert not is_read_only_cypher("FOREACH (x IN [1] | SET n.x = x)")
