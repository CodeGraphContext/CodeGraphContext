from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.swift import SwiftTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def swift_parser(tmp_path_factory):
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("swift"):
        pytest.skip("Swift tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "swift"
    wrapper.language = manager.get_language_safe("swift")
    wrapper.parser = manager.create_parser("swift")
    return SwiftTreeSitterParser(wrapper)


def test_swift_cyclomatic_complexity_increases_for_control_flow(swift_parser, tmp_path):
    code = """
import Foundation

struct Helpers {
    func simpleHelper() -> Int {
        return 1
    }

    func complexFunction(x: Int, items: [Int]) -> Int {
        var result = x
        if x > 0 {
            result += 1
        } else {
            result -= 1
        }

        for item in items {
            if item % 2 == 0 && result > 0 {
                result += item
            }
        }

        switch result {
        case 1:
            result += 2
        case 2, 3:
            result += 3
        default:
            result = 0
        }

        guard result >= 0 else {
            return -1
        }

        do {
            try mightThrow()
        } catch {
            result = -2
        }

        return result > 0 ? result : 0
    }

    func mightThrow() throws {}
}
"""
    f = tmp_path / "complexity_sample.swift"
    f.write_text(code)

    result = swift_parser.parse(f)

    by_name = {fn["name"]: fn for fn in result["functions"]}
    assert "simpleHelper" in by_name
    assert "complexFunction" in by_name

    assert by_name["simpleHelper"]["cyclomatic_complexity"] == 1
    assert by_name["complexFunction"]["cyclomatic_complexity"] > 8
