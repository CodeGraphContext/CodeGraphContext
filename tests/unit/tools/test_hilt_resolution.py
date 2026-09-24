"""Tests for resolving Hilt @Binds/@Provides into BINDS row payloads.

Lives here rather than tests/unit/parsers/test_kotlin_parser.py because it
exercises a resolution builder (build_binds_links), not the parser itself --
the parser output it consumes is treated as a fixed input, verified once via
the real KotlinTreeSitterParser and then asserted against directly, matching
how test_cross_lang_call_resolution_patterns.py tests the neighbouring
build_decorated_by_links / build_metaclass_links builders in this same
resolution layer.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.inheritance import build_binds_links
from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project_kotlin"
    / "AndroidHilt.kt"
)


@pytest.fixture(scope="module")
def parsed_hilt_file():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    parser = KotlinTreeSitterParser(wrapper)
    result = parser.parse(FIXTURE)
    result["lang"] = "kotlin"
    return result


def _fixture_path() -> str:
    return str(FIXTURE.resolve().as_posix())


class TestParserOutputSanity:
    """Confirms the fixture actually parsed the way the resolution tests
    assume, so a downstream absence assertion can't pass by accident
    (e.g. because the parser silently dropped a declaration)."""

    def test_hilt_view_model_class_and_its_load_method_are_captured(self, parsed_hilt_file):
        class_names = {c["name"] for c in parsed_hilt_file["classes"]}
        assert "UserViewModel" in class_names
        view_model = next(c for c in parsed_hilt_file["classes"] if c["name"] == "UserViewModel")
        assert "@HiltViewModel" in view_model["decorators"]

        function_names = {(f["name"], f["class_context"]) for f in parsed_hilt_file["functions"]}
        assert ("load", "UserViewModel") in function_names

    def test_inject_constructor_is_not_captured_as_a_function(self, parsed_hilt_file):
        # Kotlin never emits `primary_constructor` as a Function node (a
        # pre-existing parser limitation, not something this task changes).
        # UserViewModel's only captured function is `load`.
        view_model_functions = [
            f for f in parsed_hilt_file["functions"] if f["class_context"] == "UserViewModel"
        ]
        assert [f["name"] for f in view_model_functions] == ["load"]

    def test_binds_function_has_single_arg_type_and_return_type(self, parsed_hilt_file):
        binds_fn = next(
            f for f in parsed_hilt_file["functions"] if f["name"] == "bindUserRepository"
        )
        assert binds_fn["return_type"] == "UserRepository"
        assert binds_fn["arg_types"] == ["UserRepositoryImpl"]
        assert binds_fn["class_context"] == "RepositoryModule"
        assert "@Binds" in binds_fn["decorators"]

    def test_provides_function_body_constructor_call_is_in_function_calls(self, parsed_hilt_file):
        provides_fn = next(
            f for f in parsed_hilt_file["functions"] if f["name"] == "provideNetworkClient"
        )
        matching_calls = [
            call
            for call in parsed_hilt_file["function_calls"]
            if call["context"][0] == provides_fn["name"]
            and call["context"][2] == provides_fn["line_number"]
        ]
        assert len(matching_calls) == 1
        assert matching_calls[0]["name"] == "NetworkClientImpl"


class TestBuildBindsLinks:
    def test_binds_function_resolves_interface_to_impl(self, parsed_hilt_file):
        rows = build_binds_links([parsed_hilt_file], {})

        binds_rows = [r for r in rows if r["provider"] == "Binds"]
        assert len(binds_rows) == 1
        row = binds_rows[0]
        assert row["source_name"] == "UserRepository"
        assert row["target_name"] == "UserRepositoryImpl"
        assert row["source_path"] == _fixture_path()
        assert row["target_path"] == _fixture_path()
        assert row["provider"] == "Binds"
        assert row["confidence_label"] == "EXTRACTED"

    def test_provides_function_resolves_return_type_to_constructed_type(self, parsed_hilt_file):
        rows = build_binds_links([parsed_hilt_file], {})

        provides_rows = [r for r in rows if r["provider"] == "Provides"]
        assert len(provides_rows) == 1
        row = provides_rows[0]
        assert row["source_name"] == "NetworkClient"
        assert row["target_name"] == "NetworkClientImpl"
        assert row["source_path"] == _fixture_path()
        assert row["target_path"] == _fixture_path()
        assert row["provider"] == "Provides"
        assert row["confidence_label"] == "EXTRACTED"

    def test_hilt_view_model_and_inject_constructor_produce_no_rows(self, parsed_hilt_file):
        # UserViewModel carries no @Module, so it is out of scope regardless;
        # this asserts the outcome that keeps constructor injection excluded.
        rows = build_binds_links([parsed_hilt_file], {})

        for row in rows:
            assert row["source_name"] != "UserViewModel"
            assert row["target_name"] != "UserViewModel"
        assert len(rows) == 2

    def test_no_rows_for_functions_outside_a_module(self):
        # A @Binds-decorated function whose enclosing class has no @Module
        # annotation must not produce a row.
        file_data = {
            "path": "/tmp/repo/NotAModule.kt",
            "lang": "kotlin",
            "classes": [
                {"name": "RepositoryModule", "decorators": [], "line_number": 1},
                {"name": "UserRepositoryImpl", "decorators": [], "line_number": 5},
            ],
            "interfaces": [{"name": "UserRepository", "decorators": [], "line_number": 3}],
            "objects": [],
            "imports": [],
            "function_calls": [],
            "functions": [
                {
                    "name": "bindUserRepository",
                    "class_context": "RepositoryModule",
                    "decorators": ["@Binds"],
                    "return_type": "UserRepository",
                    "arg_types": ["UserRepositoryImpl"],
                    "line_number": 2,
                }
            ],
        }

        rows = build_binds_links([file_data], {})

        assert rows == []

    def test_binds_function_with_empty_arg_types_is_skipped(self):
        file_data = {
            "path": "/tmp/repo/EmptyArgsModule.kt",
            "lang": "kotlin",
            "classes": [{"name": "EmptyArgsModule", "decorators": ["@Module"], "line_number": 1}],
            "interfaces": [{"name": "Thing", "decorators": [], "line_number": 3}],
            "objects": [],
            "imports": [],
            "function_calls": [],
            "functions": [
                {
                    "name": "bindThing",
                    "class_context": "EmptyArgsModule",
                    "decorators": ["@Binds"],
                    "return_type": "Thing",
                    "arg_types": [],
                    "line_number": 2,
                }
            ],
        }

        rows = build_binds_links([file_data], {})

        assert rows == []

    def test_binds_function_with_multiple_args_is_skipped(self):
        file_data = {
            "path": "/tmp/repo/AmbiguousModule.kt",
            "lang": "kotlin",
            "classes": [{"name": "AmbiguousModule", "decorators": ["@Module"], "line_number": 1}],
            "interfaces": [{"name": "Thing", "decorators": [], "line_number": 3}],
            "objects": [],
            "imports": [],
            "function_calls": [],
            "functions": [
                {
                    "name": "bindThing",
                    "class_context": "AmbiguousModule",
                    "decorators": ["@Binds"],
                    "return_type": "Thing",
                    "arg_types": ["ThingImpl", "Extra"],
                    "line_number": 2,
                }
            ],
        }

        rows = build_binds_links([file_data], {})

        assert rows == []

    def test_provides_function_with_two_resolvable_calls_in_body_is_skipped(self):
        # Routine Hilt idiom: construct a dependency, then construct-and-
        # return the real implementation --
        #   val logger = LoggerImpl()      // line 10, resolvable
        #   return ThingImpl(logger)       // line 11, resolvable, the
        #                                  // actual returned type
        # Two calls in the body resolve to known types. Neither a first-
        # nor a last-line tie-break is correct in general (nested
        # construction like `return ThingImpl(LoggerImpl())` wants the
        # *first* textual call instead), so no row must be emitted -- a
        # wrong DI edge is worse for impact analysis than a missing one.
        file_data = {
            "path": "/tmp/repo/AmbiguousProvidesModule.kt",
            "lang": "kotlin",
            "classes": [
                {"name": "AmbiguousProvidesModule", "decorators": ["@Module"], "line_number": 1},
                {"name": "LoggerImpl", "decorators": [], "line_number": 20},
                {"name": "ThingImpl", "decorators": [], "line_number": 25},
            ],
            "interfaces": [{"name": "Thing", "decorators": [], "line_number": 3}],
            "objects": [],
            "imports": [],
            "functions": [
                {
                    "name": "provideThing",
                    "class_context": "AmbiguousProvidesModule",
                    "decorators": ["@Provides"],
                    "return_type": "Thing",
                    "arg_types": [],
                    "line_number": 9,
                }
            ],
            "function_calls": [
                {
                    "name": "LoggerImpl",
                    "context": ["provideThing", "function_declaration", 9],
                    "class_context": ["AmbiguousProvidesModule", 1],
                    "line_number": 10,
                },
                {
                    "name": "ThingImpl",
                    "context": ["provideThing", "function_declaration", 9],
                    "class_context": ["AmbiguousProvidesModule", 1],
                    "line_number": 11,
                },
            ],
        }

        rows = build_binds_links([file_data], {})

        assert rows == []
