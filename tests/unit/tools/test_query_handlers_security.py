from codegraphcontext.tools.handlers.query_handlers import execute_cypher_query


class _FakeRecord:
    def data(self):
        return {"value": 1}


class _FakeResult:
    def __iter__(self):
        return iter([_FakeRecord()])


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def run(self, query):
        self.query = query
        return _FakeResult()


class _FakeDriver:
    def session(self):
        return _FakeSession()


class _FakeDbManager:
    def get_driver(self):
        return _FakeDriver()


def test_execute_cypher_query_blocks_load_csv():
    result = execute_cypher_query(
        _FakeDbManager(),
        cypher_query="LOAD CSV FROM 'https://example.com' AS row RETURN row",
    )
    assert "error" in result


def test_execute_cypher_query_blocks_write_clause():
    result = execute_cypher_query(
        _FakeDbManager(),
        cypher_query="MATCH (n) SET n.x = 1 RETURN n",
    )
    assert "error" in result


def test_execute_cypher_query_allows_simple_read_query():
    result = execute_cypher_query(
        _FakeDbManager(),
        cypher_query="MATCH (n) RETURN n LIMIT 1",
    )
    assert result["success"] is True
    assert result["record_count"] == 1
