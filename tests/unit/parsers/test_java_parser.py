"""
Tests for the Java tree-sitter parser — cross-file CALLS via DI field injection.

Fixes issue #823: Java CALLS graph does not resolve cross-file method invocations.

Root cause: `inferred_obj_type` was always None, so calls on field/local-variable
receivers could not be resolved to a cross-file target by resolve_function_call.

Fix: build a var_type_map from field and local-variable declarations, then
populate `inferred_obj_type` when the base object of a method call matches a
known variable name. The resolver uses this to look up imports_map and produce
accurate cross-file CALLS edges.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from codegraphcontext.tools.languages.java import JavaTreeSitterParser
from codegraphcontext.tools.indexing.resolution.calls import resolve_function_call
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


# ---------------------------------------------------------------------------
# Shared fixture — follows the pattern from test_python_parser.py
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "java"
    wrapper.language = manager.get_language_safe("java")
    wrapper.parser = manager.create_parser("java")
    return JavaTreeSitterParser(wrapper)


def _write_and_parse(parser, src: str, suffix: str = ".java") -> dict:
    """Write src to a temp file and parse it."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        tmp = f.name
    try:
        return parser.parse(Path(tmp))
    finally:
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# Sample sources
# ---------------------------------------------------------------------------

CONTROLLER_SRC = """
package com.example.app;

import com.example.app.service.WorkService;

public class Controller {
    private WorkService workService;

    public void setWorkService(WorkService workService) {
        this.workService = workService;
    }

    public String handle(String input) {
        String result = workService.doWork(input);
        int computed = workService.computeResult(42);
        return result + " (" + computed + ")";
    }
}
"""

WORK_SERVICE_SRC = """
package com.example.app.service;

public class WorkService {
    public String doWork(String input) {
        return "processed: " + input;
    }

    public int computeResult(int value) {
        return value * 2;
    }
}
"""

GENERIC_FIELD_SRC = """
package com.example.app;

import java.util.List;
import com.example.app.service.WorkService;

public class GenericHolder {
    private List<WorkService> services;

    public void process() {
        // services is typed List — strip_generic should resolve to 'List', not 'WorkService'
        services.add(null);
    }
}
"""


# ---------------------------------------------------------------------------
# Tests: inferred_obj_type population (issue #823 regression tests)
# ---------------------------------------------------------------------------

class TestJavaDiCrossFileCalls:

    def test_di_field_call_has_inferred_obj_type(self, parser):
        """workService.doWork() must carry inferred_obj_type='WorkService' (fix for #823)."""
        data = _write_and_parse(parser, CONTROLLER_SRC)
        calls = data["function_calls"]

        do_work_calls = [c for c in calls if c["name"] == "doWork"]
        assert do_work_calls, "Expected at least one doWork call to be parsed"

        call = do_work_calls[0]
        assert call["inferred_obj_type"] == "WorkService", (
            f"Expected inferred_obj_type='WorkService', got {call['inferred_obj_type']!r}. "
            "Cross-file DI field call resolution is broken (issue #823)."
        )

    def test_second_di_call_on_same_field_also_inferred(self, parser):
        """workService.computeResult() must also carry inferred_obj_type='WorkService'."""
        data = _write_and_parse(parser, CONTROLLER_SRC)
        calls = data["function_calls"]

        compute_calls = [c for c in calls if c["name"] == "computeResult"]
        assert compute_calls, "Expected at least one computeResult call"
        assert compute_calls[0]["inferred_obj_type"] == "WorkService"

    def test_calls_without_receiver_have_no_inferred_type(self, parser):
        """Bare method calls (no object receiver) must have inferred_obj_type=None."""
        data = _write_and_parse(parser, WORK_SERVICE_SRC)
        for call in data["function_calls"]:
            assert call["inferred_obj_type"] is None, (
                f"Unexpected inferred_obj_type={call['inferred_obj_type']!r} "
                f"for call '{call['name']}' in WorkService (no DI fields present)"
            )

    def test_generic_field_strips_type_parameter(self, parser):
        """List<WorkService> field receiver resolves to 'List', not 'WorkService'."""
        data = _write_and_parse(parser, GENERIC_FIELD_SRC)
        add_calls = [c for c in data["function_calls"] if c["name"] == "add"]
        assert add_calls, "Expected 'add' call on List field"
        # The field is typed List<WorkService>; strip_generic gives 'List'
        assert add_calls[0]["inferred_obj_type"] == "List"

    def test_strip_generic_static_method(self, parser):
        """Verify _strip_generic handles all common forms correctly."""
        assert JavaTreeSitterParser._strip_generic("WorkService") == "WorkService"
        assert JavaTreeSitterParser._strip_generic("List<String>") == "List"
        assert JavaTreeSitterParser._strip_generic("Map<String, Object>") == "Map"
        assert JavaTreeSitterParser._strip_generic("  RoidFraudCheckService  ") == "RoidFraudCheckService"


# ---------------------------------------------------------------------------
# End-to-end: full cross-file CALLS resolution via resolve_function_call
# ---------------------------------------------------------------------------

class TestJavaCrossFileResolution:

    def test_di_call_resolves_to_cross_file_path(self, parser):
        """End-to-end: workService.doWork() resolves to WorkService.java, not self."""
        controller_data = _write_and_parse(parser, CONTROLLER_SRC)
        service_data = _write_and_parse(parser, WORK_SERVICE_SRC)

        controller_path = controller_data["path"]
        service_path = service_data["path"]

        # imports_map mirrors what GraphBuilder builds during indexing:
        # class simple name -> [absolute file path]
        imports_map = {"WorkService": [service_path]}

        local_names = {f["name"] for f in controller_data["functions"]} | {
            c["name"] for c in controller_data["classes"]
        }
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in controller_data.get("imports", [])
        }

        do_work_calls = [c for c in controller_data["function_calls"] if c["name"] == "doWork"]
        assert do_work_calls, "doWork call not found — parser may have regressed"

        resolved = resolve_function_call(
            do_work_calls[0],
            caller_file_path=controller_path,
            local_names=local_names,
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None, "resolve_function_call returned None"
        assert resolved["called_file_path"] == service_path, (
            f"Expected cross-file path {service_path!r}, "
            f"got {resolved['called_file_path']!r}. "
            "DI CALLS edge would be self-referential (issue #823 not fixed)."
        )

    def test_non_di_call_stays_in_caller_file(self, parser):
        """Calls where the receiver is not a known typed variable stay in the caller file."""
        service_data = _write_and_parse(parser, WORK_SERVICE_SRC)
        service_path = service_data["path"]
        local_names = {f["name"] for f in service_data["functions"]} | {
            c["name"] for c in service_data["classes"]
        }

        for call in service_data["function_calls"]:
            resolved = resolve_function_call(
                call,
                caller_file_path=service_path,
                local_names=local_names,
                local_imports={},
                imports_map={},
                skip_external=False,
            )
            if resolved:
                assert resolved["called_file_path"] == service_path, (
                    f"WorkService has no DI fields; expected self-resolution for '{call['name']}'"
                )
