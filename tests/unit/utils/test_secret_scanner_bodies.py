"""Redaction of code bodies.

`scan_and_redact` replaces a whole value when any part of it looks like a secret, and
`is_likely_secret`'s entropy fallback calls a string a secret when it is at least 16 characters,
contains one of ten common words (`private`, `auth`, `key`, `access`, ...) and scores 3.8 bits. A
body of source clears that on its own, so storing `source` for a node blanked it, which also makes
the node invisible to the full-text index over name, source and docstring.

A multi-line `source` or `docstring` is now redacted span by span: a pattern match replaces the
secret it captures, a private key is replaced from BEGIN through END, and the entropy test runs on
each candidate token instead of the whole body, replacing the string literal that holds it.
"""

import pytest

from codegraphcontext.utils.secret_scanner import (
    REDACTED,
    scan_body_and_redact,
    scan_props_and_redact,
)

BODY_KEYS = ["source", "docstring"]


def redact(key, body):
    result, findings = scan_props_and_redact({"name": "f", key: body}, redact=True)
    assert result["name"] == "f"
    return result[key], findings


# --- opaque values with no credential name -------------------------------------------------

@pytest.mark.parametrize("key", BODY_KEYS)
def test_unnamed_opaque_literal_in_java_is_the_only_thing_redacted(key):
    body = (
        "public Client build() {\n"
        '    String seed = "8f3a1b2c9d4e5f60718293a4zQ";\n'
        "    return new Client(seed, timeout);\n"
        "}"
    )
    value, findings = redact(key, body)
    assert value == body.replace("8f3a1b2c9d4e5f60718293a4zQ", REDACTED)
    assert findings == [(key, "entropy")]


@pytest.mark.parametrize("key", BODY_KEYS)
def test_unnamed_aws_style_secret_in_python_is_the_only_thing_redacted(key):
    body = (
        "def client():\n"
        "    return boto3.client(\n"
        "        's3',\n"
        "        ACCESS_ID,\n"
        "        'Zx81Qp/4vTn2Lk9Wb+7RcY3mHd6Fs0Ga5JeU1oNi',\n"
        "    )"
    )
    value, _ = redact(key, body)
    assert value == body.replace("Zx81Qp/4vTn2Lk9Wb+7RcY3mHd6Fs0Ga5JeU1oNi", REDACTED)


def test_unnamed_opaque_token_outside_quotes_is_redacted_alone():
    body = "Configure the client with:\n\n    seed: 8f3a1b2c9d4e5f60718293a4zQ\n\nthen call connect()."
    value, detected, _ = scan_body_and_redact(body, redact=True)
    assert detected is True
    assert value == body.replace("8f3a1b2c9d4e5f60718293a4zQ", REDACTED)


def test_key_material_under_a_credential_name_is_redacted():
    body = (
        "credentials = {\n"
        '    "private_key_data": "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC",\n'
        "}\n"
        "unrelated = 1"
    )
    value, detected, _ = scan_body_and_redact(body, redact=True)
    assert detected is True
    assert value == body.replace("MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC", REDACTED)


def test_named_hex_token_is_redacted_but_an_unnamed_one_is_not():
    """Hex cannot exceed 4 bits, so a hex token below the 3.8-bit threshold counts only when
    its name carries a hint word."""
    named = 'def f():\n    api_secret_hex = "0a1b2c3d0a1b2c3d4e5f6a7b0a1b2c3d"\n    return 1'
    unnamed = 'def f():\n    checksum = "0a1b2c3d0a1b2c3d4e5f6a7b0a1b2c3d"\n    return 1'
    assert scan_body_and_redact(named, redact=True)[0] == named.replace(
        "0a1b2c3d0a1b2c3d4e5f6a7b0a1b2c3d", REDACTED
    )
    assert scan_body_and_redact(unnamed, redact=True) == (unnamed, False, None)


# --- known patterns -------------------------------------------------------------------------

@pytest.mark.parametrize("key", BODY_KEYS)
def test_aws_access_key_id_is_redacted_as_a_span(key):
    body = 'void configure() {\n    String id = "AKIAIOSFODNN7EXAMPLE";\n    connect(id);\n}'
    value, findings = redact(key, body)
    assert value == body.replace("AKIAIOSFODNN7EXAMPLE", REDACTED)
    assert findings[0][1].startswith("regex:")


@pytest.mark.parametrize("key", BODY_KEYS)
def test_client_secret_value_is_redacted_but_its_name_survives(key):
    body = (
        "void refresh() {\n"
        '    String client_secret = "8f3a1b2c9d4e5f60718293a4";\n'
        "    exchange(client_secret);\n"
        "}"
    )
    value, _ = redact(key, body)
    assert value == body.replace("8f3a1b2c9d4e5f60718293a4", REDACTED)


def test_a_pattern_spanning_two_lines_redacts_only_the_value():
    body = 'def connect():\n    password =\n        "hunter2"\n    return password'
    value, detected, pattern = scan_body_and_redact(body, redact=True)
    assert detected is True and pattern.startswith("regex:")
    assert value == body.replace("hunter2", REDACTED)


def test_every_credential_in_a_body_is_redacted():
    body = (
        "def connect():\n"
        '    api_key = "AAAABBBBCCCCDDDDEEEE"\n'
        "    password =\n"
        '        "hunter2"\n'
        '    token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n'
        "    return 1"
    )
    value, detected, _ = scan_body_and_redact(body, redact=True)
    assert detected is True
    for secret in ("AAAABBBBCCCCDDDDEEEE", "hunter2", "ghp_ABCDEFGHIJ"):
        assert secret not in value
    assert value.count(REDACTED) == 3
    assert value.startswith("def connect():\n    api_key = ") and value.endswith("    return 1")


# --- private keys ---------------------------------------------------------------------------

KEY_LINES = ["MIIEpAIBAAKCAQEAxWm3kPq8ZrT4vNhLb2cD5eF7gH9iJ1kL3mN5oP7qR9sT1uV3", "JEblzIfvBvqS45Z7-hNzyReo_dGVzdA"]


@pytest.mark.parametrize("key", BODY_KEYS)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_a_private_key_block_is_redacted_whole(key, newline):
    body = newline.join([
        "KEY = '''",
        "-----BEGIN PRIVATE KEY-----",
        *KEY_LINES,
        "-----END PRIVATE KEY-----",
        "'''",
        "unrelated = 1",
    ])
    value, findings = redact(key, body)
    assert value == newline.join(["KEY = '''", REDACTED, "'''", "unrelated = 1"])
    assert findings == [(key, "pem-block")]


def test_a_key_block_with_doubled_spacing_split_over_concatenated_literals():
    body = (
        "String key =\n"
        '    "-----BEGIN RSA PRIVATE  KEY-----" +\n'
        f'    "{KEY_LINES[0]}" +\n'
        f'    "{KEY_LINES[1]}" +\n'
        '    "-----END RSA PRIVATE  KEY-----";\n'
        "int unrelated = 1;"
    )
    value, detected, pattern = scan_body_and_redact(body, redact=True)
    assert detected is True and pattern == "pem-block"
    assert value == f'String key =\n    "{REDACTED}";\nint unrelated = 1;'


def test_a_key_block_without_end_is_redacted_to_the_end_of_the_value():
    """A body is truncated before it is stored, which can cut a key block short."""
    body = "def load():\n    pem = '''-----BEGIN EC PRIVATE KEY-----\n" + KEY_LINES[0]
    value, detected, _ = scan_body_and_redact(body, redact=True)
    assert detected is True
    assert value == "def load():\n    pem = '''" + REDACTED


# --- ordinary code --------------------------------------------------------------------------

ORDINARY_JAVA = (
    "@Service\n"
    "public class TokenRefresher {\n"
    "    private final AuthService authService;\n"
    "    private String accessKey;\n"
    '    private static final String TOKEN_HEADER = "X-Authorization-Token";\n'
    '    private static final String KEY_PREFIX = "privateKeyRotation";\n'
    "\n"
    "    public String refreshAccessToken(String token) {\n"
    "        String accessToken = currentAccessTokenValue;\n"
    "        String label = ChangeHistoryI18nEnum.SUMMARY_LABEL.key();\n"
    '        Path fixture = Path.of("src/test/resources/fixtures/order2024.json");\n'
    '        UUID tenant = UUID.fromString("123e4567-e89b-12d3-a456-426614174000");\n'
    '        String enumName = "UTF8CodeUnitOffsetFromLineStart";\n'
    "        return authService.exchange(accessKey, token, accessToken, label, fixture, tenant, enumName);\n"
    "    }\n"
    "}"
)

ORDINARY_PYTHON = (
    "def get_private_key_path(self, auth_token: str) -> str:\n"
    '    """Return where the private key for *auth_token* is stored."""\n'
    "    access_key = self.settings.access_key_id\n"
    "    token_cache = TokenCache(max_entries=1024)\n"
    "    return os.path.join(self.base_dir, 'keys', access_key, token_cache.slot(auth_token))"
)

ORDINARY_DOCSTRING = (
    "Exchange a refresh token for an access token.\n"
    "\n"
    "The private key never leaves the KeyVault; authService signs the request with it\n"
    "and returns the token to the caller. See getAllRevisionsByEntityIdOrderByModificationAscending."
)


@pytest.mark.parametrize("key", BODY_KEYS)
@pytest.mark.parametrize("body", [ORDINARY_JAVA, ORDINARY_PYTHON, ORDINARY_DOCSTRING])
def test_ordinary_code_with_credential_words_is_left_alone(key, body):
    value, findings = redact(key, body)
    assert value == body
    assert findings == []


# --- what stays as it was -------------------------------------------------------------------

def test_other_multi_line_properties_are_still_replaced_whole():
    value = 'line one\napi_key = "AAAAAAAAAAAAAAAAAAAA"'
    result, findings = scan_props_and_redact({"value": value}, redact=True)
    assert result["value"] == REDACTED
    assert findings == [("value", "regex:0")]


def test_a_single_line_source_is_still_replaced_whole():
    result, _ = scan_props_and_redact({"source": 'api_key = "AAAAAAAAAAAAAAAAAAAA"'}, redact=True)
    assert result["source"] == REDACTED


def test_reporting_without_redacting_leaves_the_value_alone():
    body = 'void f() {\n    String t = "glpat-EXAMPLEEXAMPLEEXAMPLE";\n}'
    result, findings = scan_props_and_redact({"source": body}, redact=False)
    assert result["source"] == body
    assert len(findings) == 1


def test_crlf_endings_survive():
    body = 'first line\r\nString t = "glpat-EXAMPLEEXAMPLEEXAMPLE";\r\nlast line'
    value, _, _ = scan_body_and_redact(body, redact=True)
    assert value == body.replace("glpat-EXAMPLEEXAMPLEEXAMPLE", REDACTED)
