"""
Regression tests for #1509 — repo-scoped bundle paths collide on import.

Export with --repo rewrites the repo root to '.' and files to './README.md'.
Import used to write those relative strings into the graph, so:

* _check_existing_repository(path='.') matched any previously imported bundle
* File MERGE keys collapsed across flask vs requests
* Function uid built from name+path+line_number collided the same way

Import now rebases '.' / './…' onto a per-bundle destination root. These tests
mock the driver; they do not need a live graph database.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.core.cgc_bundle import (
    CGCBundle,
    _default_bundle_install_root,
    _is_bundle_relative_path,
    _is_identifying_repo_path,
    _rebase_bundle_path,
    _sanitize_bundle_repo_slug,
)


def _bundle(backend: str = "falkordb") -> CGCBundle:
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = backend
    return CGCBundle(db_manager)


def _session_for(bundle: CGCBundle) -> MagicMock:
    session = MagicMock()
    bundle.db_manager.get_driver.return_value.session.return_value.__enter__.return_value = session
    return session


def _empty_result():
    result = MagicMock()
    result.single.return_value = None
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "val,expected",
    [
        (".", True),
        ("./", True),
        (".\\", True),
        ("./README.md", True),
        (".\\src\\a.py", True),
        ("./src/foo.py", True),
        ("/abs/flask", False),
        ("os.path", False),
        ("E:/repo", False),
        ("C:/Users/hp/project", False),
        ("", False),
        (None, False),
        ("README.md", False),
    ],
)
def test_is_bundle_relative_path(val, expected):
    assert _is_bundle_relative_path(val) is expected


@pytest.mark.parametrize(
    "val,expected",
    [
        (None, False),
        ("", False),
        (".", False),
        ("./README.md", False),
        ("/abs/flask", True),
        ("C:/Users/hp/.codegraphcontext/bundles/flask", True),
    ],
)
def test_is_identifying_repo_path(val, expected):
    assert _is_identifying_repo_path(val) is expected


def test_rebase_dot_is_dest_root():
    assert _rebase_bundle_path(".", "/dest/flask") == "/dest/flask"


def test_rebase_posix_relative_file():
    assert _rebase_bundle_path("./README.md", "/dest/flask") == "/dest/flask/README.md"


def test_rebase_windows_relative_file():
    assert _rebase_bundle_path(".\\src\\a.py", "/dest/flask") == "/dest/flask/src/a.py"


def test_rebase_leaves_absolute_paths_alone():
    assert _rebase_bundle_path("/abs/flask", "/dest/x") == "/abs/flask"
    assert _rebase_bundle_path("os.path", "/dest/x") == "os.path"
    assert _rebase_bundle_path("E:/repo", "/dest/x") == "E:/repo"


def test_slug_owner_slash_repo():
    assert _sanitize_bundle_repo_slug("pallets/flask") == "pallets__flask"


def test_slug_empty_falls_back_to_unknown():
    assert _sanitize_bundle_repo_slug("") == "unknown"
    assert _sanitize_bundle_repo_slug(None) == "unknown"


def test_default_install_root_uses_home_and_slug(tmp_path):
    root = _default_bundle_install_root({"repo": "pallets/flask"}, tmp_path)
    assert root == (tmp_path / "pallets__flask").resolve().as_posix()


# ---------------------------------------------------------------------------
# _check_existing_repository
# ---------------------------------------------------------------------------


def test_check_existing_skips_dot_path_match():
    """path='.' must not issue MATCH (r:Repository {path: $path})."""
    bundle = _bundle()
    session = _session_for(bundle)
    session.run.return_value = _empty_result()

    found = bundle._check_existing_repository("requests", ".")

    assert found is False
    queries = [call.args[0] for call in session.run.call_args_list]
    assert any("name: $name" in q for q in queries)
    assert not any("{path: $path}" in q for q in queries)


def test_check_existing_still_matches_absolute_path():
    bundle = _bundle()
    session = _session_for(bundle)
    session.run.return_value = _empty_result()

    bundle._check_existing_repository("flask", "/abs/flask")

    queries = [call.args[0] for call in session.run.call_args_list]
    assert any("{path: $path}" in q for q in queries)
    path_call = next(c for c in session.run.call_args_list if "{path: $path}" in c.args[0])
    assert path_call.kwargs["path"] == "/abs/flask"


def test_check_existing_name_match_still_runs():
    bundle = _bundle()
    session = _session_for(bundle)
    name_hit = MagicMock()
    name_hit.single.return_value = {"r": object()}
    session.run.return_value = name_hit

    assert bundle._check_existing_repository("flask", ".") is True
    assert session.run.call_count == 1
    assert "name: $name" in session.run.call_args.args[0]
    assert session.run.call_args.kwargs["name"] == "flask"


# ---------------------------------------------------------------------------
# _import_node_batch — File PK uniqueness + uid
# ---------------------------------------------------------------------------


def _pk_vals(session: MagicMock):
    return [c.kwargs["pk_val"] for c in session.run.call_args_list if "pk_val" in c.kwargs]


def test_file_rows_with_same_relative_path_get_distinct_merge_keys():
    flask_root = "/dest/flask"
    requests_root = "/dest/requests"
    row = (["File"], {"path": "./README.md"}, "1")

    flask_session = MagicMock()
    flask_session.run.return_value.single.return_value = {"new_id": 1}
    _bundle()._import_node_batch(flask_session, [row], {}, flask_root)

    requests_session = MagicMock()
    requests_session.run.return_value.single.return_value = {"new_id": 1}
    _bundle()._import_node_batch(
        requests_session, [(["File"], {"path": "./README.md"}, "1")], {}, requests_root
    )

    flask_pk = _pk_vals(flask_session)[0]
    requests_pk = _pk_vals(requests_session)[0]
    assert flask_pk == f"{flask_root}/README.md"
    assert requests_pk == f"{requests_root}/README.md"
    assert flask_pk != requests_pk


def test_function_uid_includes_dest_root_not_relative_path():
    dest = "/dest/flask"
    session = MagicMock()
    session.run.return_value.single.return_value = {"new_id": 1}
    props = {"name": "parse", "path": "./src/foo.py", "line_number": 12, "uid": "parse./src/foo.py12"}

    _bundle()._import_node_batch(session, [(["Function"], props, "1")], {}, dest)

    pk = _pk_vals(session)[0]
    assert dest in pk
    assert "./" not in pk
    # occurrence_index (default 0) joined the uid parts in #1393.
    assert pk == f"parse{dest}/src/foo.py120"


def test_absolute_paths_are_unchanged_when_not_repo_scoped():
    session = MagicMock()
    session.run.return_value.single.return_value = {"new_id": 1}
    abs_path = "/home/me/numpy/core.py"

    _bundle()._import_node_batch(
        session, [(["File"], {"path": abs_path}, "1")], {}, dest_root=None
    )

    assert _pk_vals(session)[0] == abs_path


def test_absolute_paths_are_unchanged_even_with_dest_root():
    session = MagicMock()
    session.run.return_value.single.return_value = {"new_id": 1}
    abs_path = "/home/me/numpy/core.py"

    _bundle()._import_node_batch(
        session, [(["File"], {"path": abs_path}, "1")], {}, dest_root="/dest/numpy"
    )

    assert _pk_vals(session)[0] == abs_path


# ---------------------------------------------------------------------------
# _delete_repository
# ---------------------------------------------------------------------------


def test_delete_repository_noops_when_path_is_dot():
    bundle = _bundle()
    session = _session_for(bundle)
    found = MagicMock()
    found.single.return_value = {"path": "."}
    session.run.return_value = found

    bundle._delete_repository("flask")

    assert session.run.call_count == 1, (
        "DETACH DELETE must not run when r.path is '.' — that would wipe "
        "every repo-scoped bundle import"
    )
    assert "DETACH DELETE" not in session.run.call_args.args[0]
