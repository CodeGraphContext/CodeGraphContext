from unittest.mock import patch

import pytest

from codegraphcontext.utils.cypher_readonly import is_read_only_cypher


@pytest.mark.parametrize("query,reason", [
    ("MATCH (n) DELETE n", "forbidden keyword 'DELETE'"),
    ("RETURN 1; RETURN 2", "statement separator"),
    ("RETURN apoc.create.uuid()", "write-side procedure"),
    ("CALL secretProcedure() RETURN 1", "read-only allowlist"),
])
def test_rejection_records_a_reason_without_query_text(query, reason):
    with patch("codegraphcontext.utils.cypher_readonly.warning_logger") as warning:
        assert not is_read_only_cypher(query)
    warning.assert_called_once()
    message = warning.call_args.args[0]
    assert reason in message
    assert query not in message


def test_audit_never_includes_literals_or_parameters():
    query = "MATCH (n {token: 'sensitive-value'}) SET n.token = $sensitive_parameter"
    with patch("codegraphcontext.utils.cypher_readonly.warning_logger") as warning:
        assert not is_read_only_cypher(query)
    message = warning.call_args.args[0]
    assert "sensitive" not in message


def test_read_only_query_with_write_words_in_data_is_not_logged():
    with patch("codegraphcontext.utils.cypher_readonly.warning_logger") as warning:
        assert is_read_only_cypher("MATCH (n) RETURN n.delete AS set, 'CREATE'")
    warning.assert_not_called()
