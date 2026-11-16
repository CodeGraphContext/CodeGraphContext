#!/usr/bin/env python3
"""Independent explicit-oracle audit for Gradle, Maven and MyBatis extraction."""
from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path

from codegraphcontext.tools.languages.gradle import GradleParser, parse_repo_gradle
from codegraphcontext.tools.languages.maven import MavenParser, parse_repo_maven
from codegraphcontext.tools.languages.mybatis import parse_mybatis_mapper


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not expected:
            return actual == []
        if expected and not isinstance(expected[0], dict):
            return actual == expected
        return isinstance(actual, list) and all(any(contains(a, e) for a in actual) for e in expected)
    return actual == expected


CASES = []


def case(lang, name, files, expected, repo=False):
    CASES.append(dict(lang=lang, name=name, files=files, expected=expected, repo=repo))


def pom(body, namespace=True):
    ns = ' xmlns="http://maven.apache.org/POM/4.0.0"' if namespace else ""
    return f"<project{ns}><modelVersion>4.0.0</modelVersion>{body}</project>"


for suffix in ("gradle", "gradle.kts"):
    case("gradle", "parenthesized_external_" + suffix, {"build." + suffix: 'dependencies {\n api("org.example:lib:1.0")\n}\n'}, {"external_libs": [{"group_id": "org.example", "artifact_id": "lib", "version": "1.0", "configuration": "api"}]})
case("gradle", "groovy_external", {"build.gradle": "dependencies {\n api 'org.example:lib:1.0'\n}\n"}, {"external_libs": [{"artifact_id": "lib", "configuration": "api"}]})
case("gradle", "inline_configuration", {"build.gradle": "dependencies { testImplementation 'org.example:lib:1.0' }"}, {"external_libs": [{"artifact_id": "lib", "configuration": "testImplementation"}]})
case("gradle", "no_final_newline", {"build.gradle": "api 'org.example:lib:1.0'"}, {"external_libs": [{"configuration": "api"}]})
case("gradle", "comments_not_dependencies", {"build.gradle": "// implementation 'ghost:line:1'\n/* api 'ghost:block:1'\n implementation project(':ghost') */\n"}, {"external_libs": [], "inter_module_deps": []})
case("gradle", "strings_not_dependencies", {"build.gradle": 'def documentation = "implementation \'ghost:fake:1\'"\n'}, {"external_libs": []})
case("gradle", "version_range", {"build.gradle": "dependencies {\n implementation 'org.example:lib:1.+'\n}\n"}, {"external_libs": [{"version": "1.+"}]})
case("gradle", "project_dependency", {"build.gradle.kts": 'dependencies {\n api(project(":core"))\n}\n'}, {"inter_module_deps": [{"tgt_name": ":core", "configuration": "api"}]})
case("gradle", "custom_configuration", {"build.gradle.kts": 'dependencies {\n kapt("org.example:processor:1")\n}\n'}, {"external_libs": [{"artifact_id": "processor", "configuration": "kapt"}]})
case("gradle", "settings_comments", {"settings.gradle": "// include ':ghost'\ninclude ':core'\n", "build.gradle": "", "core/build.gradle": ""}, {"modules": [{"name": ":core"}]}, repo=True)

for ns in (False, True):
    case("maven", "parent_inheritance_" + str(ns), {"pom.xml": pom('<parent><groupId>org.demo</groupId><artifactId>parent</artifactId><version>1.0</version></parent><artifactId>child</artifactId>', ns)}, {"modules": [{"artifact_id": "child", "group_id": "org.demo", "version": "1.0"}]})
case("maven", "property_version", {"pom.xml": pom('<groupId>app</groupId><artifactId>main</artifactId><properties><lib.version>2</lib.version></properties><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${lib.version}</version></dependency></dependencies>')}, {"external_libs": [{"artifact_id": "lib", "version": "2"}]})
case("maven", "builtin_properties", {"pom.xml": pom('<groupId>app</groupId><artifactId>main</artifactId><version>3</version><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${project.version}</version></dependency></dependencies>')}, {"external_libs": [{"artifact_id": "lib", "version": "3"}]})
case("maven", "nested_properties", {"pom.xml": pom('<groupId>app</groupId><artifactId>main</artifactId><properties><base>2</base><lib.version>${base}.1</lib.version></properties><dependencies><dependency><groupId>other</groupId><artifactId>lib</artifactId><version>${lib.version}</version></dependency></dependencies>')}, {"external_libs": [{"version": "2.1"}]})
case("maven", "same_group_external", {"pom.xml": pom('<groupId>org.demo</groupId><artifactId>app</artifactId><dependencies><dependency><groupId>org.demo</groupId><artifactId>published-lib</artifactId><version>1</version></dependency></dependencies>')}, {"external_libs": [{"artifact_id": "published-lib"}], "inter_module_deps": []}, repo=True)
case("maven", "child_artifact_identity", {"pom.xml": pom('<groupId>org.demo</groupId><artifactId>root</artifactId><modules><module>directory</module></modules>'), "directory/pom.xml": pom('<groupId>org.demo</groupId><artifactId>actual-artifact</artifactId>')}, {"child_relations": [{"parent_artifact_id": "root", "child_artifact_id": "actual-artifact"}]}, repo=True)
case("maven", "reactor_dependency", {"pom.xml": pom('<groupId>org.demo</groupId><artifactId>app</artifactId><dependencies><dependency><groupId>org.demo</groupId><artifactId>lib</artifactId></dependency></dependencies>'), "lib/pom.xml": pom('<groupId>org.demo</groupId><artifactId>lib</artifactId>')}, {"inter_module_deps": [{"src_artifact_id": "app", "tgt_artifact_id": "lib"}]}, repo=True)
case("maven", "malformed", {"pom.xml": "<project>"}, None)

case("mybatis", "simple_select", {"UserMapper.xml": '<mapper namespace="UserMapper"><select id="find">SELECT * FROM users</select></mapper>'}, [{"method_name": "find", "db_tables": ["users"], "operation": "READS"}])
case("mybatis", "cdata", {"UserMapper.xml": '<mapper namespace="UserMapper"><select id="find"><![CDATA[SELECT * FROM users WHERE id < 5]]></select></mapper>'}, [{"db_tables": ["users"]}])
case("mybatis", "nested_dynamic_sql", {"UserMapper.xml": '<mapper namespace="UserMapper"><select id="find"><choose><when test="flag">SELECT * FROM users</when><otherwise>SELECT * FROM archived_users</otherwise></choose></select></mapper>'}, [{"db_tables": ["users", "archived_users"]}])
case("mybatis", "local_include", {"UserMapper.xml": '<mapper namespace="UserMapper"><sql id="base">SELECT * FROM users</sql><select id="find"><include refid="base" /></select></mapper>'}, [{"db_tables": ["users"]}])
case("mybatis", "qualified_local_include", {"UserMapper.xml": '<mapper namespace="demo.UserMapper"><sql id="base">SELECT * FROM users</sql><select id="find"><include refid="demo.UserMapper.base" /></select></mapper>'}, [{"db_tables": ["users"]}])
case("mybatis", "sql_comments_and_literals", {"UserMapper.xml": '<mapper namespace="UserMapper"><select id="find">SELECT \'FROM fake\' FROM users /* JOIN phantom */</select></mapper>'}, [{"db_tables": ["users"]}])
case("mybatis", "deep_foreach", {"UserMapper.xml": '<mapper namespace="UserMapper"><select id="find"><if test="flag"><foreach collection="items" item="x"><trim>SELECT * FROM users</trim></foreach></if></select></mapper>'}, [{"db_tables": ["users"]}])
case("mybatis", "write_operation", {"UserMapper.xml": '<mapper namespace="UserMapper"><update id="save">UPDATE users SET name = #{name}</update></mapper>'}, [{"db_tables": ["users"], "operation": "WRITES"}])
case("mybatis", "malformed", {"UserMapper.xml": "<mapper>"}, [])


def audit():
    records = []
    for item in CASES:
        with tempfile.TemporaryDirectory(prefix="cgc_build_audit_") as directory:
            root = Path(directory)
            for filename, source in item["files"].items():
                target = root / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8")
            row = dict(lang=item["lang"], name=item["name"], files=item["files"], expected=item["expected"])
            try:
                if item["lang"] == "gradle":
                    actual = parse_repo_gradle(root) if item["repo"] else GradleParser().parse(root / next(iter(item["files"])))
                elif item["lang"] == "maven":
                    actual = parse_repo_maven(root) if item["repo"] else MavenParser().parse(root / "pom.xml")
                else:
                    actual = parse_mybatis_mapper(root / "UserMapper.xml")
                row["actual"] = actual
                row["failures"] = [] if contains(actual, item["expected"]) else [dict(check=item["expected"], actual=actual)]
            except Exception:
                row["exception"] = traceback.format_exc()
            records.append(row)
    return records


if __name__ == "__main__":
    results = audit()
    Path("build-parser-audit.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for row in results:
        print(row["lang"], row["name"], "FAIL" if row.get("exception") or row.get("failures") else "PASS")
    raise SystemExit(any(r.get("exception") or r.get("failures") for r in results))
