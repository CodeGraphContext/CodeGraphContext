"""Build/mapper semantic regression oracles from the installed-checkout audit."""
import pytest
from codegraphcontext.tools.languages.mybatis import parse_mybatis_mapper


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not expected or not isinstance(expected[0], dict):
            return actual == expected
        return isinstance(actual, list) and all(any(_contains(a, e) for a in actual) for e in expected)
    return actual == expected


CASES = [('simple_select',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><select id="find">SELECT * FROM '
                     'users</select></mapper>'},
  [{'db_tables': ['users'], 'method_name': 'find', 'operation': 'READS'}],
  False),
 ('cdata',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><select id="find"><![CDATA[SELECT * FROM users WHERE id '
                     '< 5]]></select></mapper>'},
  [{'db_tables': ['users']}],
  False),
 ('nested_dynamic_sql',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><select id="find"><choose><when test="flag">SELECT * '
                     'FROM users</when><otherwise>SELECT * FROM '
                     'archived_users</otherwise></choose></select></mapper>'},
  [{'db_tables': ['users', 'archived_users']}],
  False),
 ('local_include',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><sql id="base">SELECT * FROM users</sql><select '
                     'id="find"><include refid="base" /></select></mapper>'},
  [{'db_tables': ['users']}],
  False),
 ('qualified_local_include',
  {'UserMapper.xml': '<mapper namespace="demo.UserMapper"><sql id="base">SELECT * FROM users</sql><select '
                     'id="find"><include refid="demo.UserMapper.base" /></select></mapper>'},
  [{'db_tables': ['users']}],
  False),
 ('sql_comments_and_literals',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><select id="find">SELECT \'FROM fake\' FROM users /* '
                     'JOIN phantom */</select></mapper>'},
  [{'db_tables': ['users']}],
  False),
 ('deep_foreach',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><select id="find"><if test="flag"><foreach '
                     'collection="items" item="x"><trim>SELECT * FROM '
                     'users</trim></foreach></if></select></mapper>'},
  [{'db_tables': ['users']}],
  False),
 ('write_operation',
  {'UserMapper.xml': '<mapper namespace="UserMapper"><update id="save">UPDATE users SET name = '
                     '#{name}</update></mapper>'},
  [{'db_tables': ['users'], 'operation': 'WRITES'}],
  False),
 ('malformed', {'UserMapper.xml': '<mapper>'}, [], False)]

@pytest.mark.parametrize("name,files,expected,repo", CASES, ids=[c[0] for c in CASES])
def test_build_audit(tmp_path, name, files, expected, repo):
    for filename, source in files.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    actual = parse_mybatis_mapper(tmp_path / "UserMapper.xml")
    assert _contains(actual, expected), actual


def test_fragment_cycles_unknown_includes_and_tableless_sql_do_not_invent_tables(tmp_path):
    path = tmp_path / 'UserMapper.xml'
    path.write_text('<mapper namespace="UserMapper"><sql id="cycle"><include refid="cycle"/></sql><select id="cyclic"><include refid="cycle"/></select><select id="unknown"><include refid="missing"/></select><select id="constant">SELECT 1</select></mapper>')
    assert parse_mybatis_mapper(path) == []


def test_quoted_tables_and_literal_text_are_distinguished(tmp_path):
    path = tmp_path / 'UserMapper.xml'
    path.write_text('<mapper namespace="UserMapper"><select id="find">SELECT \'it\'\'s FROM fake\' FROM "app"."users" -- JOIN phantom\n</select></mapper>')
    assert parse_mybatis_mapper(path)[0]['db_tables'] == ['users']


def test_repository_resolves_cross_file_fragment_namespaces(tmp_path):
    from codegraphcontext.tools.languages.mybatis import find_and_parse_mybatis_mappers
    (tmp_path / 'Shared.xml').write_text('<mapper namespace="demo.Shared"><sql id="base">SELECT * FROM real_users</sql></mapper>')
    (tmp_path / 'UserMapper.xml').write_text('<mapper namespace="demo.UserMapper"><select id="find"><include refid="demo.Shared.base"/></select></mapper>')
    records = find_and_parse_mybatis_mappers(tmp_path)
    assert len(records) == 1 and records[0]['db_tables'] == ['real_users']
