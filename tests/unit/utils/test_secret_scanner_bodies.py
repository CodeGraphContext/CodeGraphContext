"""Redaction of multi-line values.

`scan_and_redact` replaced the whole value when any part of it looked like a secret, and
`is_likely_secret`'s entropy fallback calls a string a secret when it is at least 16 characters,
contains one of ten common words (`private`, `auth`, `key`, `access`, ...) and scores 3.8 bits. A
body of source clears that on its own, so storing `source` for a node blanked it, which also makes
the node invisible to the full-text index over name, source and docstring.

A multi-line value is now scanned per line. Scalars are untouched: for a single line, redacting
the matching line is redacting the value.
"""

from codegraphcontext.utils.secret_scanner import REDACTED, scan_and_redact

ORDINARY_CODE = (
    "private int accessCounter = 0;\n"
    "public int authorize(int n) {\n"
    "    return accessCounter + n;\n"
    "}"
)

WITH_TOKEN = (
    "void configure() {\n"
    '    String token = "glpat-EXAMPLEEXAMPLEEXAMPLE";\n'
    "    connect(token);\n"
    "}"
)

WITH_KEY_BLOCK = (
    "String key =\n"
    '    "-----BEGIN RSA PRIVATE  KEY-----" +\n'  # doubled spacing, which the BEGIN patterns tolerate
    '    "MIIEpAIBAAKCAQEAxWm3kPq8ZrT4vNhLb2cD5eF7gH9iJ1kL3mN5oP7qR9sT1uV3" +\n'
    '    "JEblzIfvBvqS45Z7-hNzyReo_dGVzdA" +\n'  # base64url, inside the block
    '    "-----END RSA PRIVATE  KEY-----";\n'
    "int unrelated = 1;"
)

WITH_CLIENT_SECRET = (
    "void refresh() {\n"
    '    String client_secret = "8f3a1b2c9d4e5f60718293a4";\n'
    "    exchange(client_secret);\n"
    "}"
)

TWO_CREDENTIALS = (
    "def connect():\n"
    '    api_key = "AAAABBBBCCCCDDDDEEEE"\n'
    "    password =\n"
    '        "hunter2"\n'
    "    return 1"
)

KEY_MATERIAL_ALONE = (
    "credentials = {\n"
    '    "private_key_data": "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC",\n'
    "}\n"
    "unrelated = 1"
)

LONG_IDENTIFIERS = (
    "public interface RevisionRepository {\n"
    "    List<Revision> getAllRevisionsByEntityIdOrderByModificationAscending(Long id);\n"
    "}"
)


def test_ordinary_code_survives():
    value, detected, _ = scan_and_redact(ORDINARY_CODE, redact=True)
    assert detected is False
    assert value == ORDINARY_CODE


def test_only_the_credential_line_is_replaced():
    value, detected, _ = scan_and_redact(WITH_TOKEN, redact=True)
    assert detected is True
    assert "glpat-EXAMPLE" not in value
    assert "connect(token);" in value
    assert value.count(REDACTED) == 1


def test_a_key_block_is_redacted_whole():
    """The header matches a pattern; the key material on the next lines matches nothing."""
    value, detected, pattern = scan_and_redact(WITH_KEY_BLOCK, redact=True)
    assert detected is True and pattern == "pem-block"
    assert "MIIEpAIBAAKCAQEA" not in value
    assert "JEblzIfvBvqS45Z7" not in value
    assert "int unrelated = 1;" in value


def test_credential_names_outside_the_original_list():
    value, detected, _ = scan_and_redact(WITH_CLIENT_SECRET, redact=True)
    assert detected is True
    assert "8f3a1b2c9d4e" not in value
    assert "exchange(client_secret);" in value


def test_a_second_credential_does_not_switch_off_the_cross_line_check():
    """The whole-value pass has to run whatever the line pass found, or a body carrying both an
    inline key and a line-split password keeps the password."""
    value, detected, _ = scan_and_redact(TWO_CREDENTIALS, redact=True)
    assert detected is True
    assert "hunter2" not in value and "AAAABBBBCCCC" not in value


def test_a_pattern_spanning_two_lines_is_still_caught():
    """`\\s` matches a newline, so most patterns are written to span one. Scanning line by line
    would see neither half, so the whole value has to be checked before giving up."""
    body = 'def connect():\n    password =\n        "hunter2"\n    return password'
    value, detected, pattern = scan_and_redact(body, redact=True)
    assert detected is True and pattern.startswith("regex:")
    assert value == REDACTED


def test_key_material_outside_a_key_block_is_not_detected():
    """A documented reduction: entropy used to catch this as collateral of blanking the body, and
    nothing replaces it. Inside BEGIN/END the block tracking still covers it."""
    value, detected, _ = scan_and_redact(KEY_MATERIAL_ALONE, redact=True)
    assert detected is False and value == KEY_MATERIAL_ALONE


def test_a_long_identifier_is_not_mistaken_for_a_secret():
    value, detected, _ = scan_and_redact(LONG_IDENTIFIERS, redact=True)
    assert detected is False and value == LONG_IDENTIFIERS


def test_a_scalar_is_still_replaced_whole():
    value, detected, _ = scan_and_redact('api_key = "AAAAAAAAAAAAAAAAAAAA"', redact=True)
    assert detected is True and value == REDACTED


def test_reporting_without_redacting_leaves_the_value_alone():
    value, detected, _ = scan_and_redact(WITH_TOKEN, redact=False)
    assert detected is True and value == WITH_TOKEN


def test_a_non_string_value_is_returned_unchanged():
    assert scan_and_redact(123, redact=True) == (123, False, None)


def test_crlf_endings_survive():
    body = 'first line\r\nString t = "glpat-EXAMPLEEXAMPLEEXAMPLE";\r\nlast line'
    value, _, _ = scan_and_redact(body, redact=True)
    assert value.count("\r") == body.count("\r")
