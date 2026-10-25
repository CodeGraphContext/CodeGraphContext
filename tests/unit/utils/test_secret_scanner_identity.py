import pytest

from codegraphcontext.tools.indexing.sanitize import sanitize_props, sanitize_props_with_secrets
from codegraphcontext.utils.secret_scanner import is_likely_secret, scan_props_and_redact


@pytest.mark.parametrize('sanitize', [
    lambda props: scan_props_and_redact(props, redact=True)[0],
    lambda props: sanitize_props(props, _redact=True),
    lambda props: sanitize_props_with_secrets(props, redact=True)[0],
])
def test_redaction_preserves_identity_and_still_redacts_values(sanitize):
    name = 'Module_private_access_key_123456789'
    assert is_likely_secret(name)[0]
    props = {
        'name': name, 'full_name': name, 'uid': name, 'path': '/repo/' + name,
        'caller_name': name, 'module_name': name, 'caller_file_path': name,
        'source': 'password = "ThisIsATestCredential123456"',
        'docstring': 'password = "ThisIsATestCredential123456"',
        'value': 'password = "ThisIsATestCredential123456"',
    }
    result = sanitize(props)
    for key in ('source', 'docstring', 'value'):
        assert result[key] == '[REDACTED]'
    for key in props.keys() - {'source', 'docstring', 'value'}:
        assert result[key] == props[key]


def test_two_distinct_module_names_cannot_collapse_to_redaction_marker():
    names = ['Module_private_access_key_123456789', 'Module_private_access_key_987654321']
    assert all(is_likely_secret(name)[0] for name in names)
    rows = [scan_props_and_redact({'name': name}, redact=True)[0] for name in names]
    assert [row['name'] for row in rows] == names


def test_findings_contain_content_only_and_input_is_not_mutated():
    props = {'name': 'Module_private_access_key_123456789', 'value': 'password = "ThisIsATestCredential123456"'}
    result, findings = scan_props_and_redact(props, redact=True)
    assert [key for key, _ in findings] == ['value']
    assert props['value'] != result['value']
