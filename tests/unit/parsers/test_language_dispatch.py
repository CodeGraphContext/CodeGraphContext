"""Language dispatch in TreeSitterParser (see issue #1309).

An unrecognised or misspelled language name must fail loudly with the list of
supported languages, rather than leaving `language_specific_parser` as None and
failing later somewhere unrelated.
"""

import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize("bad_name", ["pyhton", "nosuchlang", "cobol", ""])
def test_invalid_language_name_raises_with_supported_list(bad_name):
    with pytest.raises(ValueError) as exc_info:
        TreeSitterParser(bad_name)

    message = str(exc_info.value)
    assert bad_name in message or "language" in message.lower()
    # The error must be actionable: it names languages that do work.
    assert "python" in message.lower()


def test_valid_language_builds_a_language_specific_parser():
    parser = TreeSitterParser("python")

    assert parser.language_specific_parser is not None
    assert parser.language_name == "python"


def test_every_mapped_language_resolves_to_an_importable_parser():
    """Guards against a map entry whose module or class was renamed: without
    this, a typo'd mapping only surfaces the first time someone indexes that
    language."""
    # Re-read the map from the source of truth rather than duplicating it.
    import inspect
    import re

    source = inspect.getsource(TreeSitterParser.__init__)
    mapped = re.findall(r'"([a-z_]+)":\s*\(".languages\.[a-z_]+",\s*"(\w+)"\)', source)
    assert mapped, "could not read LANGUAGE_PARSER_MAP out of the constructor"

    failures = []
    for language_name, class_name in mapped:
        try:
            parser = TreeSitterParser(language_name)
            assert type(parser.language_specific_parser).__name__ == class_name
        except Exception as exc:  # noqa: BLE001 - collect all, report together
            failures.append(f"{language_name}: {type(exc).__name__}: {exc}")

    assert not failures, "mapped languages that failed to load:\n" + "\n".join(failures)
