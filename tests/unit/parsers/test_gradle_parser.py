"""
Tests for the Gradle build-graph parser (#888 / Task 9, slice G6).

Gradle path notation is standard on multi-module Android projects:
`include(":feature:symptoms")`, `include(":core:network")`. Before this fix,
`GradleParser` derived module identity from the leaf directory name only
(`gradle_path.parent.name`), so `:feature:a:impl` and `:feature:b:impl` both
became `impl` and collided on the `{name: ...}` MERGE key used for the
`GradleModule` node (writer.py) and for both endpoints of `MODULE_DEPENDS_ON`
/ `USES_LIBRARY` edges.

This module verifies:
  1. Canonical naming — settings-declared modules are identified by their
     full Gradle path (`:feature:symptoms`), not the leaf directory name.
  2. The collision case — two modules that share a leaf directory name but
     live under different parents remain distinct.
  3. Dependency-edge resolution — inter-module `project(...)` dependencies
     resolve to the *same* canonical identity used for the node names, so a
     downstream `MATCH (src:GradleModule {name: ...})` in the writer would
     actually find the target instead of silently matching nothing.
"""

from pathlib import Path

from codegraphcontext.tools.languages.gradle import parse_repo_gradle


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_canonical_module_names_from_settings_includes(tmp_path: Path):
    """A settings file declaring `include(":feature:symptoms")` and
    `include(":core:network")` must yield modules identified by their full
    canonical path, not the leaf directory name."""
    repo = tmp_path / "repo"
    _write(repo / "settings.gradle", """
        include(":feature:symptoms")
        include(":core:network")
    """)
    _write(repo / "feature" / "symptoms" / "build.gradle", "")
    _write(repo / "core" / "network" / "build.gradle", "")

    data = parse_repo_gradle(repo)
    names = {m["name"] for m in data["modules"]}

    assert ":feature:symptoms" in names
    assert ":core:network" in names
    # The old leaf-only names must NOT appear — they'd indicate the
    # collapse this fix removes.
    assert "symptoms" not in names
    assert "network" not in names


def test_same_leaf_name_under_different_parents_does_not_collide(tmp_path: Path):
    """Two modules both named `impl` under different feature parents must
    remain distinct — this is the collision this slice exists to fix.
    Under the pre-fix code both modules were named `impl` and collapsed
    onto a single GradleModule MERGE key."""
    repo = tmp_path / "repo"
    _write(repo / "settings.gradle", """
        include(":feature:a:impl")
        include(":feature:b:impl")
    """)
    _write(repo / "feature" / "a" / "impl" / "build.gradle", "")
    _write(repo / "feature" / "b" / "impl" / "build.gradle", "")

    data = parse_repo_gradle(repo)
    names = [m["name"] for m in data["modules"]]

    assert len(names) == 2
    assert len(set(names)) == 2, f"modules collided onto a shared name: {names}"
    assert ":feature:a:impl" in names
    assert ":feature:b:impl" in names


def test_dependency_edges_use_canonical_identity_on_both_ends(tmp_path: Path):
    """A MODULE_DEPENDS_ON from :app to :feature:symptoms must reference
    the same canonical names used for the GradleModule nodes themselves —
    otherwise the writer's `MATCH (tgt:GradleModule {name: ...})` finds
    nothing and the edge is silently dropped."""
    repo = tmp_path / "repo"
    _write(repo / "settings.gradle", """
        include(":app")
        include(":feature:symptoms")
    """)
    _write(repo / "app" / "build.gradle", """
        dependencies {
            implementation project(":feature:symptoms")
        }
    """)
    _write(repo / "feature" / "symptoms" / "build.gradle", "")

    data = parse_repo_gradle(repo)
    module_names = {m["name"] for m in data["modules"]}

    assert {":app", ":feature:symptoms"} <= module_names

    deps = data["inter_module_deps"]
    assert {"src_name": ":app", "tgt_name": ":feature:symptoms", "configuration": "implementation"} in deps

    # The permanent guard: every edge endpoint (and every external-lib
    # source) must be a name that actually exists among the module nodes.
    # If this ever fails, the writer's MATCH would find nothing and the
    # edge would be dropped silently.
    for dep in deps:
        assert dep["src_name"] in module_names, f"dangling src_name: {dep['src_name']}"
        assert dep["tgt_name"] in module_names, f"dangling tgt_name: {dep['tgt_name']}"
    for lib in data["external_libs"]:
        assert lib["src_name"] in module_names, f"dangling external_libs src_name: {lib['src_name']}"


def test_single_root_module_with_no_includes_keeps_working(tmp_path: Path):
    """Characterization test for the global constraint: a project with a
    single root module and no `include(...)` lines (no settings.gradle at
    all) must keep working — i.e. still produce exactly one module."""
    repo = tmp_path / "repo"
    _write(repo / "build.gradle", """
        dependencies {
            implementation 'com.squareup.okhttp3:okhttp:4.9.0'
        }
    """)

    data = parse_repo_gradle(repo)

    assert len(data["modules"]) == 1
    module = data["modules"][0]
    # Pin today's actual value (the leaf directory name of the repo root,
    # per the pre-existing gradle_path.parent.name convention) rather than
    # a truthiness check, so a later change to the root-module fallback
    # branch in _resolve_module_name would be caught here.
    assert module["name"] == "repo"
    assert len(data["external_libs"]) == 1
    assert data["external_libs"][0]["src_name"] == module["name"]
