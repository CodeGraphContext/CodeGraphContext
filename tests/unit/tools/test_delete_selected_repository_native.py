"""A selected stored key must survive a symlink retarget without deleting its target."""
import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

pytest.importorskip("kuzu")


@pytest.mark.parametrize("retarget", [False, True])
def test_selected_repository_deletion_preserves_other_repository(tmp_path, retarget):
    selected = tmp_path / "selected"
    target = tmp_path / "target"
    selected.mkdir()
    target.mkdir()
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        writer = GraphWriter(driver)
        writer.add_repository_to_graph(selected)
        writer.add_repository_to_graph(target)
        for repo in (selected, target):
            writer.add_file_to_graph(
                {"path": str(repo / "example.py"), "repo_path": str(repo),
                 "lang": "python", "imports": [], "functions": [],
                 "classes": [], "variables": []},
                repo.name, {}, repo_path_str=str(repo),
            )
        selected.rmdir()
        if retarget:
            selected.symlink_to(target, target_is_directory=True)
        builder = GraphBuilder.__new__(GraphBuilder)
        builder._writer = writer
        assert builder.delete_indexed_repository_from_graph(str(selected))
        with driver.session() as session:
            repositories = session.run("MATCH (r:Repository) RETURN r.path AS path").data()
            files = session.run("MATCH (f:File) RETURN f.path AS path").data()
        assert {r["path"] for r in repositories} == {str(target)}
        assert {f["path"] for f in files} == {str(target / "example.py")}
    finally:
        manager.close_driver()
