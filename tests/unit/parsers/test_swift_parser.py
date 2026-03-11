from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.swift import SwiftTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def swift_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("swift"):
        pytest.skip("Swift tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "swift"
    wrapper.language = manager.get_language_safe("swift")
    wrapper.parser = manager.create_parser("swift")
    return SwiftTreeSitterParser(wrapper)


def test_parse_swift_declarations_with_current_grammar(swift_parser, temp_test_dir):
    code = """
import Foundation

struct MetricTracker {
    let sampleCount: Int
    func record(value: Int) {
        print(value)
    }
}

enum ProcessingState {
    case idle
    case running
}

actor TaskWorker {
    func compute() {}
}

class GenericController {
    let name: String

    init(name: String) {
        self.name = name
    }

    func track() {
        print(name)
    }
}
"""
    f = temp_test_dir / "sample.swift"
    f.write_text(code)

    result = swift_parser.parse(f)

    assert len(result["functions"]) >= 4
    assert any(item["name"] == "MetricTracker" for item in result["structs"])
    assert any(item["name"] == "ProcessingState" for item in result["enums"])
    assert any(item["name"] == "TaskWorker" for item in result["classes"])
    assert any(item["name"] == "GenericController" for item in result["classes"])
    assert len(result["imports"]) == 1
    assert any(item["name"] == "sampleCount" for item in result["variables"])
