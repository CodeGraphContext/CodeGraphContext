"""Build/mapper semantic regression oracles from the installed-checkout audit."""
import pytest
from codegraphcontext.tools.languages.gradle import GradleParser, parse_repo_gradle


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not expected or not isinstance(expected[0], dict):
            return actual == expected
        return isinstance(actual, list) and all(any(_contains(a, e) for a in actual) for e in expected)
    return actual == expected


CASES = [('parenthesized_external_gradle',
  {'build.gradle': 'dependencies {\n api("org.example:lib:1.0")\n}\n'},
  {'external_libs': [{'artifact_id': 'lib',
                      'configuration': 'api',
                      'group_id': 'org.example',
                      'version': '1.0'}]},
  False),
 ('parenthesized_external_gradle.kts',
  {'build.gradle.kts': 'dependencies {\n api("org.example:lib:1.0")\n}\n'},
  {'external_libs': [{'artifact_id': 'lib',
                      'configuration': 'api',
                      'group_id': 'org.example',
                      'version': '1.0'}]},
  False),
 ('groovy_external',
  {'build.gradle': "dependencies {\n api 'org.example:lib:1.0'\n}\n"},
  {'external_libs': [{'artifact_id': 'lib', 'configuration': 'api'}]},
  False),
 ('inline_configuration',
  {'build.gradle': "dependencies { testImplementation 'org.example:lib:1.0' }"},
  {'external_libs': [{'artifact_id': 'lib', 'configuration': 'testImplementation'}]},
  False),
 ('no_final_newline',
  {'build.gradle': "api 'org.example:lib:1.0'"},
  {'external_libs': [{'configuration': 'api'}]},
  False),
 ('comments_not_dependencies',
  {'build.gradle': "// implementation 'ghost:line:1'\n"
                   "/* api 'ghost:block:1'\n"
                   " implementation project(':ghost') */\n"},
  {'external_libs': [], 'inter_module_deps': []},
  False),
 ('strings_not_dependencies',
  {'build.gradle': 'def documentation = "implementation \'ghost:fake:1\'"\n'},
  {'external_libs': []},
  False),
 ('version_range',
  {'build.gradle': "dependencies {\n implementation 'org.example:lib:1.+'\n}\n"},
  {'external_libs': [{'version': '1.+'}]},
  False),
 ('project_dependency',
  {'build.gradle.kts': 'dependencies {\n api(project(":core"))\n}\n'},
  {'inter_module_deps': [{'configuration': 'api', 'tgt_name': ':core'}]},
  False),
 ('custom_configuration',
  {'build.gradle.kts': 'dependencies {\n kapt("org.example:processor:1")\n}\n'},
  {'external_libs': [{'artifact_id': 'processor', 'configuration': 'kapt'}]},
  False),
 ('settings_comments',
  {'build.gradle': '', 'core/build.gradle': '', 'settings.gradle': "// include ':ghost'\ninclude ':core'\n"},
  {'modules': [{'name': ':core'}]},
  True)]

@pytest.mark.parametrize("name,files,expected,repo", CASES, ids=[c[0] for c in CASES])
def test_build_audit(tmp_path, name, files, expected, repo):
    for filename, source in files.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    actual = parse_repo_gradle(tmp_path) if repo else GradleParser().parse(tmp_path / next(iter(files)))
    assert _contains(actual, expected), actual


def test_constraints_wrappers_named_arguments_and_backup_files(tmp_path):
    (tmp_path / 'build.gradle.kts').write_text('dependencies {\n constraints { api("ghost:constraint:1") }\n api(platform("org.example:bom:2"))\n custom(group = "org.example", name = "lib", version = "3")\n add("runtimeOnly", "org.example:runtime:4")\n}\n')
    (tmp_path / 'build.gradle.backup').write_text('api("ghost:backup:1")')
    actual = parse_repo_gradle(tmp_path)
    assert {(r['artifact_id'], r['configuration'], r['version']) for r in actual['external_libs']} == {('bom', 'api', '2'), ('lib', 'custom', '3'), ('runtime', 'runtimeOnly', '4')}
    assert len(actual['modules']) == 1
