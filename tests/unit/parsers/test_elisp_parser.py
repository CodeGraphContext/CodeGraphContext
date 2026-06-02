from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.elisp import (
    ELISP_QUERIES,
    ElispTreeSitterParser,
    pre_scan_elisp,
)
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import (
    execute_query,
    get_tree_sitter_manager,
)

ELISP_SAMPLE = r"""
;;; sample.el --- Tree-sitter CST fixture -*- lexical-binding: t; -*-
;;; Commentary:
;; This comment mentions (fake-call) and should remain a comment node.
;;; Code:

(require 'cl-lib)
(require 'subr-x)
(autoload 'sample-autoload "sample-autoload" "Autoload doc." t)

(defvar sample-count 0
  "Counter docstring.")

(defconst sample-answer 42
  "Answer docstring.")

(defcustom sample-name "neo"
  "Name docstring."
  :type 'string
  :group 'sample)

(setq sample-count (1+ sample-count)
      sample-cache (make-hash-table :test #'equal))

;;;###autoload
(defun sample-hello (name &optional loud)
  "Say hello to NAME.
When LOUD is non-nil, shout. The text (fake-string-call) is just text."
  (let ((greeting (format "Hello, %s" name)))
    (let* ((display (if loud (upcase greeting) greeting)))
      (message "%s" display)
      (sample-helper name)
      (funcall #'sample-callback name)
      (apply #'sample-variadic (list name)))))

(defsubst sample-inline (x)
  "Increment X."
  (+ x 1))

(defmacro sample-with-buffer (buffer &rest body)
  "Run BODY in BUFFER."
  `(with-current-buffer ,buffer ,@body))

(cl-defun sample-cl (&key name (count 1))
  "CL-style function."
  (dotimes (_ count)
    (sample-hello name)))

(lambda (x)
  (sample-inline x))

(provide 'sample)
"""


@pytest.fixture(scope="module")
def elisp_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("elisp"):
        pytest.skip(
            "Emacs Lisp tree-sitter grammar is not available in this environment"
        )

    wrapper = MagicMock()
    wrapper.language_name = "elisp"
    wrapper.language = manager.get_language_safe("elisp")
    wrapper.parser = manager.create_parser("elisp")
    return ElispTreeSitterParser(wrapper)


def test_tree_sitter_parser_dispatches_to_elisp_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("elisp"):
        pytest.skip(
            "Emacs Lisp tree-sitter grammar is not available in this environment"
        )

    parser = TreeSitterParser("elisp")

    assert isinstance(parser.language_specific_parser, ElispTreeSitterParser)


def test_elisp_queries_capture_mvp_shapes(elisp_parser, temp_test_dir):
    f = temp_test_dir / "sample.el"
    f.write_text(ELISP_SAMPLE)
    tree = elisp_parser.parser.parse(f.read_bytes())

    function_captures = execute_query(
        elisp_parser.language, ELISP_QUERIES["functions"], tree.root_node
    )
    function_names = {
        elisp_parser._get_node_text(node)
        for node, capture in function_captures
        if capture == "name"
    }
    assert {
        "sample-hello",
        "sample-inline",
        "sample-with-buffer",
        "sample-cl",
    }.issubset(function_names)

    variable_captures = execute_query(
        elisp_parser.language, ELISP_QUERIES["variables"], tree.root_node
    )
    variable_names = {
        elisp_parser._get_node_text(node)
        for node, capture in variable_captures
        if capture == "name"
    }
    assert {"sample-count", "sample-answer", "sample-name"}.issubset(variable_names)

    feature_captures = execute_query(
        elisp_parser.language, ELISP_QUERIES["features"], tree.root_node
    )
    features = {
        elisp_parser._get_node_text(node)
        for node, capture in feature_captures
        if capture == "feature"
    }
    assert {"cl-lib", "subr-x", "sample"}.issubset(features)


def test_parse_elisp_normalized_output(elisp_parser, temp_test_dir):
    f = temp_test_dir / "sample.el"
    f.write_text(ELISP_SAMPLE)

    result = elisp_parser.parse(f, index_source=True)

    assert result["lang"] == "elisp"
    assert result["classes"] == []

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert set(functions) == {
        "sample-hello",
        "sample-inline",
        "sample-with-buffer",
        "sample-cl",
    }
    assert functions["sample-hello"]["type"] == "defun"
    assert functions["sample-hello"]["args"] == ["name", "loud"]
    assert functions["sample-hello"]["docstring"].startswith("Say hello to NAME")
    assert functions["sample-with-buffer"]["type"] == "defmacro"
    assert functions["sample-with-buffer"]["args"] == ["buffer", "body"]
    assert functions["sample-cl"]["type"] == "cl-defun"
    assert functions["sample-cl"]["args"] == ["name", "count"]

    variables = {(var["name"], var["type"]): var for var in result["variables"]}
    assert ("sample-count", "defvar") in variables
    assert ("sample-answer", "defconst") in variables
    assert ("sample-name", "defcustom") in variables
    assert ("sample-cache", "setq") in variables
    assert variables[("sample-count", "defvar")]["docstring"] == "Counter docstring."

    imports = {(imp["name"], imp["import_type"]) for imp in result["imports"]}
    assert ("cl-lib", "require") in imports
    assert ("subr-x", "require") in imports
    assert ("sample-autoload", "autoload") in imports
    assert ("sample", "provide") in imports

    calls = {call["name"]: call for call in result["function_calls"]}
    assert "sample-helper" in calls
    assert calls["sample-helper"]["context"][0] == "sample-hello"
    assert calls["sample-callback"]["call_kind"] == "funcall"
    assert calls["sample-variadic"]["call_kind"] == "apply"
    assert "sample-hello" in calls
    assert "sample-inline" in calls
    assert "fake-call" not in calls
    assert "fake-string-call" not in calls


def test_pre_scan_elisp_indexes_definitions_and_provided_features(
    elisp_parser, temp_test_dir
):
    core = temp_test_dir / "foo-core.el"
    core.write_text("""
(defvar foo-core-count 0)
(defun foo-core-helper (name) (message "%s" name))
(defmacro foo-core-with-helper (&rest body) `(progn ,@body))
(provide 'foo-core)
""")
    ui = temp_test_dir / "foo-ui.el"
    ui.write_text("""
(require 'foo-core)
(defun foo-ui-render (name) (foo-core-helper name))
(provide 'foo-ui)
""")

    wrapper = MagicMock()
    wrapper.language_name = "elisp"
    wrapper.language = elisp_parser.language
    wrapper.parser = elisp_parser.parser

    imports_map = pre_scan_elisp([core, ui], wrapper)

    assert str(core.resolve()) in imports_map["foo-core"]
    assert str(core.resolve()) in imports_map["foo-core-helper"]
    assert str(core.resolve()) in imports_map["foo-core-with-helper"]
    assert str(core.resolve()) in imports_map["foo-core-count"]
    assert str(ui.resolve()) in imports_map["foo-ui-render"]
