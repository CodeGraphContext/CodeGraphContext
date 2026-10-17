"""Build/mapper semantic regression oracles from the installed-checkout audit."""
import pytest
from codegraphcontext.tools.languages.maven import MavenParser, parse_repo_maven


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not expected or not isinstance(expected[0], dict):
            return actual == expected
        return isinstance(actual, list) and all(any(_contains(a, e) for a in actual) for e in expected)
    return actual == expected


CASES = [('parent_inheritance_False',
  {'pom.xml': '<project><modelVersion>4.0.0</modelVersion><parent><groupId>org.demo</groupId><artifactId>parent</artifactId><version>1.0</version></parent><artifactId>child</artifactId></project>'},
  {'modules': [{'artifact_id': 'child', 'group_id': 'org.demo', 'version': '1.0'}]},
  False),
 ('parent_inheritance_True',
  {'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.demo</groupId><artifactId>parent</artifactId><version>1.0</version></parent><artifactId>child</artifactId></project>'},
  {'modules': [{'artifact_id': 'child', 'group_id': 'org.demo', 'version': '1.0'}]},
  False),
 ('property_version',
  {'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>app</groupId><artifactId>main</artifactId><properties><lib.version>2</lib.version></properties><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${lib.version}</version></dependency></dependencies></project>'},
  {'external_libs': [{'artifact_id': 'lib', 'version': '2'}]},
  False),
 ('builtin_properties',
  {'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>app</groupId><artifactId>main</artifactId><version>3</version><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${project.version}</version></dependency></dependencies></project>'},
  {'external_libs': [{'artifact_id': 'lib', 'version': '3'}]},
  False),
 ('nested_properties',
  {'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>app</groupId><artifactId>main</artifactId><properties><base>2</base><lib.version>${base}.1</lib.version></properties><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${lib.version}</version></dependency></dependencies></project>'},
  {'external_libs': [{'version': '2.1'}]},
  False),
 ('same_group_external',
  {'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.demo</groupId><artifactId>app</artifactId><dependencies><dependency><groupId>org.demo</groupId><artifactId>published-lib</artifactId><version>1</version></dependency></dependencies></project>'},
  {'external_libs': [{'artifact_id': 'published-lib'}], 'inter_module_deps': []},
  True),
 ('child_artifact_identity',
  {'directory/pom.xml': '<project '
                        'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.demo</groupId><artifactId>actual-artifact</artifactId></project>',
   'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.demo</groupId><artifactId>root</artifactId><modules><module>directory</module></modules></project>'},
  {'child_relations': [{'child_artifact_id': 'actual-artifact', 'parent_artifact_id': 'root'}]},
  True),
 ('reactor_dependency',
  {'lib/pom.xml': '<project '
                  'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.demo</groupId><artifactId>lib</artifactId></project>',
   'pom.xml': '<project '
              'xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.demo</groupId><artifactId>app</artifactId><dependencies><dependency><groupId>org.demo</groupId><artifactId>lib</artifactId></dependency></dependencies></project>'},
  {'inter_module_deps': [{'src_artifact_id': 'app', 'tgt_artifact_id': 'lib'}]},
  True),
 ('malformed', {'pom.xml': '<project>'}, None, False)]

@pytest.mark.parametrize("name,files,expected,repo", CASES, ids=[c[0] for c in CASES])
def test_build_audit(tmp_path, name, files, expected, repo):
    for filename, source in files.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    actual = parse_repo_maven(tmp_path) if repo else MavenParser().parse(tmp_path / "pom.xml")
    assert _contains(actual, expected), actual


def test_property_cycles_terminate_and_version_mismatches_stay_external(tmp_path):
    (tmp_path / 'pom.xml').write_text('<project><groupId>g</groupId><artifactId>app</artifactId><properties><a>${b}</a><b>${a}</b></properties><dependencies><dependency><groupId>g</groupId><artifactId>lib</artifactId><version>1</version></dependency><dependency><groupId>x</groupId><artifactId>cycle</artifactId><version>${a}</version></dependency></dependencies></project>')
    child = tmp_path / 'lib'
    child.mkdir()
    (child / 'pom.xml').write_text('<project><groupId>g</groupId><artifactId>lib</artifactId><version>2</version></project>')
    result = parse_repo_maven(tmp_path)
    assert not result['inter_module_deps']
    assert {d['artifact_id'] for d in result['external_libs']} == {'lib', 'cycle'}
    assert next(d for d in result['external_libs'] if d['artifact_id'] == 'cycle')['version'] in {'${a}', '${b}'}
