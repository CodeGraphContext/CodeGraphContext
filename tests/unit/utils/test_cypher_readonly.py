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
