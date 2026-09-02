"""Tests for Task 3: override-liveness and language-aware Android entry points
in find_dead_code (code_finder.py).

Two of the four tests below are controls, without which the other two prove
nothing:

  - test_non_override_uncalled_function_is_still_dead_code is the control for
    test_override_function_is_not_dead_code: it proves the new `modifiers`
    filter narrows dead-code detection rather than disabling it entirely.
  - test_android_lifecycle_name_is_still_dead_code_for_python is the control
    for test_android_lifecycle_name_is_not_dead_code_for_kotlin: it proves the
    Android entry-point exemption is scoped to JVM languages, not global.
    It also exercises the `modifiers IS NOT NULL` guard: the Python function
    is written with no `modifiers` key at all (the real Python parser never
    emits one), so `func.modifiers` is genuinely NULL in Ladybug -- the exact
    condition the guard exists to handle. Without the guard,
    `'override' IN NULL` is NULL rather than FALSE, which makes the whole
    WHERE predicate NULL and silently drops the row from the results.
"""
from pathlib import Path

import pytest

pytest.importorskip("ladybug")

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.code_finder import ANDROID_DECORATOR_PRESET, CodeFinder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def _fresh_ladybug_manager(db_path: Path) -> LadybugDBManager:
    if LadybugDBManager._instance is not None:
        LadybugDBManager._instance.close_driver()
    LadybugDBManager._instance = None
    LadybugDBManager._db = None
    LadybugDBManager._conn = None
    return LadybugDBManager(db_path=str(db_path))


def _write_functions(writer: GraphWriter, repo_path: Path, file_path: Path, *, lang: str, functions) -> None:
    """Index one file containing the given functions, with no callers.

    Mirrors the per-function properties real parsers attach (see
    ``tools/languages/kotlin.py``): ``lang`` and ``is_dependency`` are set on
    the function dict itself, not inherited from the file.

    Each entry in ``functions`` is a dict with ``name`` and ``line_number``,
    and optionally ``modifiers`` and/or ``decorators``. Omitting either key
    entirely (rather than passing ``[]``) leaves the corresponding Ladybug
    column truly NULL for that function -- matching what real non-Kotlin
    parsers (e.g. Python) and functions indexed before the column existed
    actually produce. Passing ``[]`` gets coerced by the writer to ``[""]``,
    which correctly matches no pattern.
    """
    writer.add_repository_to_graph(repo_path)
    fn_dicts = []
    for fn in functions:
        d = {
            "name": fn["name"],
            "line_number": fn["line_number"],
            "args": [],
            "lang": lang,
            "is_dependency": False,
        }
        if "modifiers" in fn:
            d["modifiers"] = fn["modifiers"]
        if "decorators" in fn:
            d["decorators"] = fn["decorators"]
        fn_dicts.append(d)

    writer.add_file_to_graph(
        {
            "path": str(file_path),
            "lang": lang,
            "is_dependency": False,
            "functions": fn_dicts,
            "classes": [],
            "interfaces": [],
            "objects": [],
            "variables": [],
            "imports": [],
            "function_calls": [],
        },
        repo_path.name,
        {},
        repo_path_str=str(repo_path),
    )


def test_override_function_is_not_dead_code(tmp_path):
    """A Kotlin `override fun` with no inbound caller is not dead code.

    The framework (or the supertype it overrides) reaches it, even though
    nothing in this project's call graph does. A sibling, genuinely-unused
    function in the same file proves the query still ran and found
    something, rather than returning nothing at all.
    """
    manager = _fresh_ladybug_manager(tmp_path / "override-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "PaymentProcessor.kt"
        file_path.write_text("", encoding="utf-8")

        _write_functions(
            writer,
            repo_path,
            file_path,
            lang="kotlin",
            functions=[
                {"name": "processPayment", "line_number": 3, "modifiers": ["override"]},
                {"name": "unusedHelper", "line_number": 10, "modifiers": []},
            ],
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code()

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"unusedHelper"}
    finally:
        manager.close_driver()


def test_non_override_uncalled_function_is_still_dead_code(tmp_path):
    """Control for the override test: without the override, it is still dead.

    Same shape as test_override_function_is_not_dead_code except
    modifiers=[]. If this fails, the change disabled dead-code detection
    entirely rather than narrowing it.
    """
    manager = _fresh_ladybug_manager(tmp_path / "non-override-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "PaymentProcessor.kt"
        file_path.write_text("", encoding="utf-8")

        _write_functions(
            writer,
            repo_path,
            file_path,
            lang="kotlin",
            functions=[{"name": "processPayment", "line_number": 3, "modifiers": []}],
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code()

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"processPayment"}
    finally:
        manager.close_driver()


def test_android_lifecycle_name_is_not_dead_code_for_kotlin(tmp_path):
    """A Kotlin `onCreate` with no inbound caller is not dead code.

    The Android framework invokes lifecycle methods; nothing in the project's
    own call graph needs to. A sibling, genuinely-unused function in the same
    file proves the query still ran and found something.
    """
    manager = _fresh_ladybug_manager(tmp_path / "lifecycle-kotlin-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "MainActivity.kt"
        file_path.write_text("", encoding="utf-8")

        _write_functions(
            writer,
            repo_path,
            file_path,
            lang="kotlin",
            functions=[
                {"name": "onCreate", "line_number": 3, "modifiers": []},
                {"name": "unusedHelper", "line_number": 10, "modifiers": []},
            ],
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code()

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"unusedHelper"}
    finally:
        manager.close_driver()


def test_android_lifecycle_name_is_still_dead_code_for_python(tmp_path):
    """Control for the lifecycle test: the exemption is language-scoped.

    A Python function named `onCreate` (no Android framework involved) with
    no caller must still be reported. Proves the Android entry-point list
    only suppresses findings for kotlin/java, not every language.

    The function is written with no `modifiers` key at all -- the real
    Python parser never emits one -- so `func.modifiers` is genuinely NULL
    in Ladybug. This is what exercises the `modifiers IS NOT NULL` guard: an
    unguarded `'override' IN NULL` evaluates to NULL, which makes the whole
    WHERE predicate NULL and would silently drop this row from the results.
    """
    manager = _fresh_ladybug_manager(tmp_path / "lifecycle-python-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "main.py"
        file_path.write_text("", encoding="utf-8")

        _write_functions(
            writer,
            repo_path,
            file_path,
            lang="python",
            functions=[{"name": "onCreate", "line_number": 3}],
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code()

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"onCreate"}
    finally:
        manager.close_driver()


def test_android_preset_excludes_annotated_functions(tmp_path):
    """The preset must exclude annotated functions and retain un-annotated ones.

    Three uncalled functions: one carrying @Composable, one carrying @Test,
    and one plain. Passing ANDROID_DECORATOR_PRESET to exclude_decorated_with
    must return exactly the plain one -- not a subset check ("the composable
    is absent"), which would also pass if the query returned nothing at all.
    """
    manager = _fresh_ladybug_manager(tmp_path / "android-preset-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "MainScreen.kt"
        file_path.write_text("", encoding="utf-8")

        _write_functions(
            writer,
            repo_path,
            file_path,
            lang="kotlin",
            functions=[
                {
                    "name": "MainScreenPreview",
                    "line_number": 3,
                    "decorators": ["@Composable"],
                },
                {
                    "name": "testMainScreenRenders",
                    "line_number": 10,
                    "decorators": ["@Test"],
                },
                {
                    "name": "plainUnusedHelper",
                    "line_number": 17,
                    "decorators": [],
                },
            ],
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code(
            exclude_decorated_with=list(ANDROID_DECORATOR_PRESET)
        )

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"plainUnusedHelper"}
    finally:
        manager.close_driver()
