"""Resolve XML mapper namespaces from indexed Java declarations, not filenames."""

from codegraphcontext.tools.languages.mybatis import (
    find_and_parse_mybatis_mappers,
    resolve_mybatis_sources,
)


def java_data(path, package, name="UserMapper"):
    return {"path": str(path), "package_name": package,
            "interfaces": [{"name": name, "qualified_name": f"{package}.{name}"}]}


def test_xml_namespace_selects_exact_package_and_nonmatching_filename(tmp_path):
    source = tmp_path / "src" / "OtherFilename.java"
    xml = tmp_path / "resources" / "Queries.xml"
    xml.parent.mkdir()
    xml.write_text('<mapper namespace="a.UserMapper"><select id="find">SELECT * FROM users</select>'
                   '<delete id="remove">DELETE FROM users</delete></mapper>')
    data = [java_data(source, "a"), java_data(tmp_path / "other" / "UserMapper.java", "b")]
    records = find_and_parse_mybatis_mappers(tmp_path, data)
    assert {r["operation"] for r in records} == {"READS", "WRITES"}
    assert {r["method_path"] for r in records} == {source.resolve().as_posix()}
    assert all(r["mapper_namespace"] == "a.UserMapper" for r in records)


def test_duplicate_qualified_names_and_missing_namespaces_stay_unresolved(tmp_path):
    data = [java_data(tmp_path / "module-a" / "UserMapper.java", "a"),
            java_data(tmp_path / "module-b" / "UserMapper.java", "a")]
    records = [{"mapper_namespace": name, "class_name": "UserMapper"}
               for name in ("a.UserMapper", "missing.UserMapper")]
    assert all(r["method_path"] is None for r in resolve_mybatis_sources(records, data, tmp_path))


def test_foreign_repo_sources_do_not_satisfy_namespace(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    records = [{"mapper_namespace": "a.UserMapper", "class_name": "UserMapper"}]
    data = [java_data(tmp_path / "foreign" / "UserMapper.java", "a")]
    assert resolve_mybatis_sources(records, data, repo)[0]["method_path"] is None
