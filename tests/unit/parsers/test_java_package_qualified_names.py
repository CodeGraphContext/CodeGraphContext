"""
Unit tests for Phase 1 — package_name extraction and qualified_name construction
in the Java tree-sitter parser.

Covers:
  - package_name field on the parse() return dict (File node data)
  - qualified_name on Function nodes (package.ClassName.methodName)
  - qualified_name on Class nodes (package.ClassName)
  - Files without a package declaration (default/unnamed package)
  - FQN entries in pre_scan_java imports_map
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from codegraphcontext.tools.languages.java import JavaTreeSitterParser, pre_scan_java
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "java"
    wrapper.language = manager.get_language_safe("java")
    wrapper.parser = manager.create_parser("java")
    return JavaTreeSitterParser(wrapper)


def _write_and_parse(parser, src: str) -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".java", delete=False, encoding="utf-8"
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

BILLING_SERVICE_SRC = """\
package com.example.acme.billing;

public class BillingService {
    public void processPayment(String orderId) {
        // implementation
    }

    public int calculateTotal(int qty, int price) {
        return qty * price;
    }
}
"""

INTERFACE_SRC = """\
package com.example.acme.auth;

public interface Authenticator {
    boolean authenticate(String token);
}
"""

NO_PACKAGE_SRC = """\
public class StandaloneUtil {
    public void doSomething() {}
}
"""

INNER_CLASS_SRC = """\
package com.example.acme.core;

public class Outer {
    public static class Inner {
        public void innerMethod() {}
    }

    public void outerMethod() {}
}
"""


# ---------------------------------------------------------------------------
# Tests: package_name on file data (Phase 1 — File nodes)
# ---------------------------------------------------------------------------

class TestPackageNameExtraction:

    def test_package_name_present_when_declared(self, parser):
        """parse() must return package_name matching the Java package statement."""
        data = _write_and_parse(parser, BILLING_SERVICE_SRC)
        assert data["package_name"] == "com.example.acme.billing"

    def test_package_name_for_interface(self, parser):
        """Interface files must also export package_name."""
        data = _write_and_parse(parser, INTERFACE_SRC)
        assert data["package_name"] == "com.example.acme.auth"

    def test_package_name_is_none_without_declaration(self, parser):
        """Files with no package statement must return package_name=None."""
        data = _write_and_parse(parser, NO_PACKAGE_SRC)
        assert data["package_name"] is None

    def test_package_name_key_always_present(self, parser):
        """The package_name key must always be in the result dict, even when None."""
        data = _write_and_parse(parser, NO_PACKAGE_SRC)
        assert "package_name" in data


# ---------------------------------------------------------------------------
# Tests: qualified_name on Function nodes (Phase 1 — Function nodes)
# ---------------------------------------------------------------------------

class TestFunctionQualifiedName:

    def test_method_qualified_name_includes_package_and_class(self, parser):
        """A class method qualified_name must be package.ClassName.methodName."""
        data = _write_and_parse(parser, BILLING_SERVICE_SRC)
        methods = {f["name"]: f for f in data["functions"]}

        assert "processPayment" in methods
        assert methods["processPayment"]["qualified_name"] == (
            "com.example.acme.billing.BillingService.processPayment"
        )

    def test_all_methods_have_qualified_name(self, parser):
        """Every method in a packaged class must have a non-empty qualified_name."""
        data = _write_and_parse(parser, BILLING_SERVICE_SRC)
        for fn in data["functions"]:
            assert "qualified_name" in fn, f"No qualified_name on {fn['name']}"
            assert fn["qualified_name"], f"Empty qualified_name on {fn['name']}"

    def test_method_qualified_name_uses_actual_method_name(self, parser):
        """calculateTotal qualified_name must end with the correct method name."""
        data = _write_and_parse(parser, BILLING_SERVICE_SRC)
        methods = {f["name"]: f for f in data["functions"]}
        assert methods["calculateTotal"]["qualified_name"].endswith(".calculateTotal")

    def test_no_qualified_name_without_package(self, parser):
        """Methods in files with no package declaration must not have qualified_name."""
        data = _write_and_parse(parser, NO_PACKAGE_SRC)
        for fn in data["functions"]:
            assert "qualified_name" not in fn or fn.get("qualified_name") is None, (
                f"Unexpected qualified_name on {fn['name']} in packageless file"
            )


# ---------------------------------------------------------------------------
# Tests: qualified_name on Class nodes (Phase 1 — Class nodes)
# ---------------------------------------------------------------------------

class TestClassQualifiedName:

    def test_class_qualified_name_is_package_dot_classname(self, parser):
        """Class qualified_name must be package.ClassName."""
        data = _write_and_parse(parser, BILLING_SERVICE_SRC)
        all_types = {c["name"]: c for c in data["classes"] + data["interfaces"]}

        assert "BillingService" in all_types
        assert all_types["BillingService"]["qualified_name"] == (
            "com.example.acme.billing.BillingService"
        )

    def test_interface_qualified_name(self, parser):
        """Interface nodes must also carry qualified_name."""
        data = _write_and_parse(parser, INTERFACE_SRC)
        all_types = {c["name"]: c for c in data["classes"] + data["interfaces"]}
        assert "Authenticator" in all_types
        assert all_types["Authenticator"]["qualified_name"] == "com.example.acme.auth.Authenticator"

    def test_no_class_qualified_name_without_package(self, parser):
        """Classes in packageless files must not have qualified_name."""
        data = _write_and_parse(parser, NO_PACKAGE_SRC)
        for cls in data["classes"]:
            assert "qualified_name" not in cls or cls.get("qualified_name") is None


# ---------------------------------------------------------------------------
# Tests: pre_scan_java FQN entries (Phase 1 — imports_map enrichment)
# ---------------------------------------------------------------------------

class TestPreScanJavaFQNEntries:

    def test_pre_scan_adds_fqn_entry(self, tmp_path):
        """pre_scan_java must add com.example.acme.billing.BillingService -> [path] entry."""
        java_file = tmp_path / "BillingService.java"
        java_file.write_text(BILLING_SERVICE_SRC, encoding="utf-8")

        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "java"
        wrapper.language = manager.get_language_safe("java")
        wrapper.parser = manager.create_parser("java")

        result = pre_scan_java([java_file], wrapper)

        assert "com.example.acme.billing.BillingService" in result, (
            "FQN entry missing — Phase 2 qualified-import resolution will not work"
        )
        assert str(java_file) in result["com.example.acme.billing.BillingService"]

    def test_pre_scan_retains_short_name_entry(self, tmp_path):
        """pre_scan_java must still register the short name BillingService -> [path]."""
        java_file = tmp_path / "BillingService.java"
        java_file.write_text(BILLING_SERVICE_SRC, encoding="utf-8")

        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "java"
        wrapper.language = manager.get_language_safe("java")
        wrapper.parser = manager.create_parser("java")

        result = pre_scan_java([java_file], wrapper)

        assert "BillingService" in result, "Short-name entry must be kept for backward compat"
        assert str(java_file) in result["BillingService"]

    def test_pre_scan_adds_interface_fqn(self, tmp_path):
        """pre_scan_java must add FQN entries for interfaces as well as classes."""
        java_file = tmp_path / "Authenticator.java"
        java_file.write_text(INTERFACE_SRC, encoding="utf-8")

        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "java"
        wrapper.language = manager.get_language_safe("java")
        wrapper.parser = manager.create_parser("java")

        result = pre_scan_java([java_file], wrapper)

        assert "com.example.acme.auth.Authenticator" in result
        assert str(java_file) in result["com.example.acme.auth.Authenticator"]

    def test_pre_scan_no_fqn_without_package(self, tmp_path):
        """Files without a package declaration must not produce FQN entries."""
        java_file = tmp_path / "StandaloneUtil.java"
        java_file.write_text(NO_PACKAGE_SRC, encoding="utf-8")

        manager = get_tree_sitter_manager()
        wrapper = MagicMock()
        wrapper.language_name = "java"
        wrapper.language = manager.get_language_safe("java")
        wrapper.parser = manager.create_parser("java")

        result = pre_scan_java([java_file], wrapper)

        # No dotted FQN keys should appear for this class
        fqn_keys = [k for k in result if "." in k and "StandaloneUtil" in k]
        assert not fqn_keys, f"Unexpected FQN keys for packageless class: {fqn_keys}"
