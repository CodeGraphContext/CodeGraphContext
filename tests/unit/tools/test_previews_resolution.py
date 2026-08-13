"""Tests for resolving @Preview-annotated Compose functions into PREVIEWS
row payloads.

Lives here rather than tests/unit/parsers/test_kotlin_parser.py because it
exercises a resolution builder (build_previews_links), not the parser
itself -- the parser output it consumes is treated as a fixed input,
verified once via the real KotlinTreeSitterParser and then asserted
against directly, matching how test_hilt_resolution.py tests the
neighbouring build_binds_links builder in this same resolution layer.

PREVIEWS answers "which composables have no preview": a @Preview function
exists only to render some composable, so the edge is
`@Preview function -> the composable it calls`.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.inheritance import build_previews_links
from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project_kotlin"
    / "AndroidAnnotations.kt"
)


@pytest.fixture(scope="module")
def parsed_annotations_file():
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
    assume, so a downstream absence assertion can't pass by accident."""

    def test_greeting_preview_is_composable_and_previewed(self, parsed_annotations_file):
        greeting_preview = next(
            f for f in parsed_annotations_file["functions"] if f["name"] == "GreetingPreview"
        )
        assert greeting_preview["is_composable"] is True
        assert any(
            d.startswith("@Preview") for d in greeting_preview["decorators"]
        )

    def test_greeting_preview_body_calls_greeting(self, parsed_annotations_file):
        greeting_preview = next(
            f for f in parsed_annotations_file["functions"] if f["name"] == "GreetingPreview"
        )
        matching_calls = [
            call
            for call in parsed_annotations_file["function_calls"]
            if call["context"][0] == greeting_preview["name"]
            and call["context"][2] == greeting_preview["line_number"]
        ]
        matching_names = {call["name"] for call in matching_calls}
        # The parser also records the "@Preview(...)" annotation itself as
        # a call sharing the same context (it is a constructor-shaped
        # invocation) -- build_previews_links relies on the is_composable
        # check to filter that one out, since "Preview" the annotation
        # class is never a @Composable function.
        assert "Greeting" in matching_names
        assert "Preview" in matching_names

    def test_label_is_composable_with_no_preview_decorator(self, parsed_annotations_file):
        label = next(f for f in parsed_annotations_file["functions"] if f["name"] == "Label")
        assert label["is_composable"] is True
        assert not any(d.startswith("@Preview") for d in label["decorators"])


class TestBuildPreviewsLinks:
    def test_greeting_preview_links_to_greeting(self, parsed_annotations_file):
        rows = build_previews_links([parsed_annotations_file], {})

        matching = [r for r in rows if r["preview_name"] == "GreetingPreview"]
        assert len(matching) == 1
        row = matching[0]
        assert row["composable_name"] == "Greeting"
        assert row["composable_path"] == _fixture_path()
        assert row["preview_path"] == _fixture_path()
        assert row["confidence_label"] == "EXTRACTED"

    def test_title_preview_links_to_title(self, parsed_annotations_file):
        """A second positive case, so the query exercised below isn't
        trivially satisfied by a single edge in the whole batch."""
        rows = build_previews_links([parsed_annotations_file], {})

        matching = [r for r in rows if r["preview_name"] == "TitlePreview"]
        assert len(matching) == 1
        assert matching[0]["composable_name"] == "Title"

    def test_composables_with_no_inbound_preview_are_identifiable(self, parsed_annotations_file):
        """This is the query PREVIEWS exists to answer: which composables
        have no preview. Label is the negative case -- it is a real
        @Composable function, but must never appear as a PREVIEWS target."""
        rows = build_previews_links([parsed_annotations_file], {})
        previewed_names = {r["composable_name"] for r in rows}

        composable_names = {
            f["name"]
            for f in parsed_annotations_file["functions"]
            if f.get("is_composable")
        }
        unpreviewed = composable_names - previewed_names

        assert "Label" in unpreviewed
        assert "Greeting" not in unpreviewed
        assert "Title" not in unpreviewed
        # GreetingPreview/TitlePreview are themselves @Composable functions
        # (Compose previews must be), but they call something rather than
        # being called by a preview, so they legitimately have no inbound
        # PREVIEWS edge either -- this loop is not itself evidence of a bug.
        assert "GreetingPreview" in unpreviewed
        assert "TitlePreview" in unpreviewed

    def test_bare_preview_decorator_on_hand_built_data_produces_edge(self):
        """Positive control for the two boundary tests below: same
        function/call shape, differing only in the decorator string,
        must produce exactly one row. Without this, a bug in how the
        hand-built `context` tuple lines up with the builder's matching
        logic could make every `rows == []` boundary assertion below pass
        vacuously (for the wrong reason) rather than because @Preview was
        correctly rejected."""
        file_data = {
            "path": "/tmp/repo/Positive.kt",
            "lang": "kotlin",
            "classes": [],
            "imports": [],
            "function_calls": [
                {
                    "name": "Widget",
                    "context": ("WidgetPreview", "function_declaration", 10),
                    "class_context": (None, None),
                }
            ],
            "functions": [
                {
                    "name": "Widget",
                    "decorators": ["@Composable"],
                    "is_composable": True,
                    "line_number": 1,
                },
                {
                    "name": "WidgetPreview",
                    "decorators": ["@Composable", "@Preview"],
                    "is_composable": True,
                    "line_number": 10,
                },
            ],
        }

        rows = build_previews_links([file_data], {})

        assert len(rows) == 1
        assert rows[0]["preview_name"] == "WidgetPreview"
        assert rows[0]["composable_name"] == "Widget"

    def test_preview_parameter_annotation_does_not_produce_edge(self):
        """Boundary test: @PreviewParameter must not be mistaken for
        @Preview. A naive substring/startswith("@Preview") check would
        wrongly match this and pass vacuously (startswith("@Preview") on
        "@PreviewParameter" is True) -- only an exact-name comparison (via
        _parse_decorator_name) correctly rejects it. Same shape as the
        positive control above, so a rows == [] result here is evidence
        the decorator name was rejected, not evidence the matching logic
        is broken."""
        file_data = {
            "path": "/tmp/repo/Boundary.kt",
            "lang": "kotlin",
            "classes": [],
            "imports": [],
            "function_calls": [
                {
                    "name": "Widget",
                    "context": ("WidgetPreview", "function_declaration", 10),
                    "class_context": (None, None),
                }
            ],
            "functions": [
                {
                    "name": "Widget",
                    "decorators": ["@Composable"],
                    "is_composable": True,
                    "line_number": 1,
                },
                {
                    "name": "WidgetPreview",
                    "decorators": ["@Composable", "@PreviewParameter"],
                    "is_composable": True,
                    "line_number": 10,
                },
            ],
        }

        rows = build_previews_links([file_data], {})

        assert rows == []

    def test_preview_screen_sizes_annotation_does_not_produce_edge(self):
        """Same boundary as @PreviewParameter, for @PreviewScreenSizes."""
        file_data = {
            "path": "/tmp/repo/Boundary2.kt",
            "lang": "kotlin",
            "classes": [],
            "imports": [],
            "function_calls": [
                {
                    "name": "Widget",
                    "context": ("WidgetScreenSizes", "function_declaration", 10),
                    "class_context": (None, None),
                }
            ],
            "functions": [
                {
                    "name": "Widget",
                    "decorators": ["@Composable"],
                    "is_composable": True,
                    "line_number": 1,
                },
                {
                    "name": "WidgetScreenSizes",
                    "decorators": ["@Composable", "@PreviewScreenSizes"],
                    "is_composable": True,
                    "line_number": 10,
                },
            ],
        }

        rows = build_previews_links([file_data], {})

        assert rows == []

    def test_call_to_non_composable_function_does_not_produce_edge(self):
        """A @Preview function's body may call helper functions that are
        not themselves composables (e.g. a logger); those must not be
        mistaken for the previewed composable."""
        file_data = {
            "path": "/tmp/repo/NotComposable.kt",
            "lang": "kotlin",
            "classes": [],
            "imports": [],
            "function_calls": [
                {
                    "name": "logDebug",
                    "context": ("WidgetPreview", "function_declaration", 10),
                    "class_context": (None, None),
                }
            ],
            "functions": [
                {
                    "name": "logDebug",
                    "decorators": [],
                    "is_composable": False,
                    "line_number": 1,
                },
                {
                    "name": "WidgetPreview",
                    "decorators": ["@Composable", "@Preview"],
                    "is_composable": True,
                    "line_number": 10,
                },
            ],
        }

        rows = build_previews_links([file_data], {})

        assert rows == []

    def test_annotation_echo_is_rejected_even_when_a_same_named_composable_exists(self):
        """Pins the fix for the annotation-echo finding: the Kotlin parser
        records an annotation-with-arguments (e.g. this function's own
        "@Preview(...)") as a phantom entry in function_calls sharing the
        annotated function's context, because it is syntactically a
        constructor_invocation. A composable_index membership check alone
        cannot reject this -- it only failed to match by coincidence, when
        no @Composable function happened to be named "Preview". Here one
        exists (and is uniquely resolvable, being in the same file), so
        without the own-decorator-name filter this would wrongly produce a
        PREVIEWS edge from WidgetPreview to a composable named Preview
        that WidgetPreview never actually calls -- only the widget it calls
        for real."""
        file_data = {
            "path": "/tmp/repo/AnnotationEcho.kt",
            "lang": "kotlin",
            "classes": [],
            "imports": [],
            "function_calls": [
                {
                    # The genuine call in the function body.
                    "name": "Widget",
                    "context": ("WidgetPreview", "function_declaration", 10),
                    "class_context": (None, None),
                },
                {
                    # The parser's phantom echo of "@Preview(...)" itself,
                    # sharing WidgetPreview's context.
                    "name": "Preview",
                    "context": ("WidgetPreview", "function_declaration", 10),
                    "class_context": (None, None),
                },
            ],
            "functions": [
                {
                    "name": "Widget",
                    "decorators": ["@Composable"],
                    "is_composable": True,
                    "line_number": 1,
                },
                {
                    # A @Composable function that happens to be named
                    # exactly like the bare annotation name -- the case
                    # the coincidental composable_index-only check missed.
                    "name": "Preview",
                    "decorators": ["@Composable"],
                    "is_composable": True,
                    "line_number": 5,
                },
                {
                    "name": "WidgetPreview",
                    "decorators": ["@Composable", "@Preview(showBackground = true)"],
                    "is_composable": True,
                    "line_number": 10,
                },
            ],
        }

        rows = build_previews_links([file_data], {})

        assert len(rows) == 1
        assert rows[0]["preview_name"] == "WidgetPreview"
        assert rows[0]["composable_name"] == "Widget"
