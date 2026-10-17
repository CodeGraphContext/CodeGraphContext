#!/usr/bin/env python3
"""Executable parser audit with explicit semantic oracles, not snapshot generation.

Run from an installed checkout. JSON evidence retains inputs, checks, actual
records, grammar recovery state, versions and exceptions for independent triage.
This is an audit tool: a finding produces a nonzero exit code.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import tempfile
import traceback
from collections import Counter
from pathlib import Path

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.tools.indexing.pre_scan import pre_scan_for_imports

CASES = []


def case(lang, name, source, **expected):
    checks = []
    for bucket, names in expected.items():
        if bucket == "import_suffixes":
            checks.extend(("suffix", "imports", n) for n in names)
        elif bucket == "attrs":
            checks.extend(("attr", *row) for row in names)
        elif bucket == "absent":
            checks.extend(("absent", *row) for row in names)
        elif bucket == "counts":
            checks.extend(("count", *row) for row in names)
        else:
            checks.extend(("has", bucket, n) for n in names)
    CASES.append(dict(lang=lang, name=name, source=source, checks=checks))


# Definitions, binding forms, ownership, calls, imports and negative controls.
case("python", "nested_async", "async def outer(x):\n    def inner(y):\n        return helper(y)\n    return inner(x)\n", functions=["outer", "inner"], function_calls=["helper", "inner"], attrs=[("function_calls", "helper", "context.0", "inner")])
case("python", "decorated_class", "@decorate\nclass Child(Base):\n    @staticmethod\n    def run(x):\n        return helper(x)\n", classes=["Child"], functions=["run"], attrs=[("classes", "Child", "bases", ["Base"]), ("functions", "run", "line_number", 4)])
case("python", "import_bindings", "import os.path as path\nfrom ..pkg import one as first, two\n", imports=["os.path", "one", "two"], attrs=[("imports", "one", "alias", "first"), ("imports", "one", "full_import_name", "..pkg.one")])
case("python", "destructuring", "a, (b, c) = (1, (2, 3))\n", variables=["a", "b", "c"])
case("python", "lambda_owner", "def outer():\n    cb = lambda x: helper(x)\n    return cb(1)\n", functions=["outer", "cb"], function_calls=["helper", "cb"], attrs=[("function_calls", "helper", "context.0", "cb")])
case("python", "annotations_are_not_calls", "def run(x: list[int]) -> str:\n    return helper(x)\n", functions=["run"], function_calls=["helper"], absent=[("function_calls", "list"), ("function_calls", "str")])

for lang in ("javascript", "typescript", "tsx"):
    case(lang, "nested_arrows", "function outer() {\n  const inner = (x) => helper(x);\n  return inner(1);\n}\n", functions=["outer", "inner"], function_calls=["helper", "inner"], attrs=[("function_calls", "helper", "context.0", "inner")])
    case(lang, "function_expression", "const build = function named(x) { return helper(x); };\n", functions=["build"], function_calls=["helper"])
    case(lang, "class_methods", "class Child extends Base {\n  run(x) { return this.helper(x); }\n  static build() { return new Child(); }\n}\n", classes=["Child"], functions=["run", "build"], function_calls=["helper", "Child"], attrs=[("function_calls", "helper", "class_context.0", "Child")])
    case(lang, "imports", "import main, {one as first, two} from './lib';\nimport * as ns from './other';\n", imports=["default", "one", "two", "*"], attrs=[("imports", "one", "alias", "first"), ("imports", "one", "source", "./lib"), ("imports", "default", "alias", "main"), ("imports", "*", "alias", "ns")])
    case(lang, "destructure", "const {one: first, two, ...rest} = input;\nconst [a, b] = values;\n", variables=["first", "two", "rest", "a", "b"], absent=[("variables", "one")])
    case(lang, "optional_calls", "function run(obj) { obj?.work?.(1); obj.work(2); }\n", functions=["run"], counts=[("function_calls", "work", 2)])
    case(lang, "template_and_comments", "const text = 'fake()';\n// phantom()\nfunction run() { return `${helper()}`; }\n", functions=["run"], function_calls=["helper"], absent=[("function_calls", "fake"), ("function_calls", "phantom")])
for lang in ("typescript", "tsx"):
    case(lang, "type_declarations", "interface Box<T> { value: T; }\ntype Pair<T> = [T, T];\nabstract class Base { abstract run(): void; }\n", interfaces=["Box"], type_aliases=["Pair"], classes=["Base"], functions=["run"])
    case(lang, "generic_calls", "function run() { return identity<string>('x'); }\n", functions=["run"], function_calls=["identity"], counts=[("function_calls", "identity", 1)])
case("tsx", "component_precision", "function util(x: number) { return x + 1; }\nfunction View() { return <div />; }\nclass Plain {}\n", components=["View"], absent=[("components", "util"), ("components", "Plain")])
case("tsx", "component_reference", "import {Button} from './Button';\nfunction View() { return <Button />; }\n", components=["View"], imports=["Button"])

case("go", "receiver", "package demo\ntype Service struct {}\nfunc (s *Service) Run(x int) int { return helper(x) }\nfunc helper(x int) int { return x }\n", functions=["Run", "helper"], structs=["Service"], function_calls=["helper"], attrs=[("functions", "Run", "class_context", "Service")])
case("go", "imports_aliases", 'package demo\nimport (\n alias "example.com/one"\n "fmt"\n)\n', imports=["one", "fmt"], attrs=[("imports", "one", "alias", "alias")])
case("go", "generic_invocation", "package demo\nfunc run() { identity[int](1) }\n", functions=["run"], function_calls=["identity"])
case("go", "closure_owner", "package demo\nfunc outer() {\n inner := func() { helper() }\n inner()\n}\n", functions=["outer", "inner"], function_calls=["helper", "inner"], attrs=[("function_calls", "helper", "context.0", "inner")])
case("go", "interface", "package demo\ntype Reader interface { Read(p []byte) (int, error) }\n", interfaces=["Reader"])

case("rust", "generic_calls", "fn run() { identity::<u32>(1); }\n", functions=["run"], function_calls=["identity"])
case("rust", "generic_impl", "struct Box<T> { value: T }\nimpl<T> Box<T> {\n fn get(&self) { helper(); }\n}\n", structs=["Box"], functions=["get"], function_calls=["helper"], attrs=[("functions", "get", "class_context", "Box")])
case("rust", "trait_signatures", "trait Draw {\n fn draw(&self);\n fn size(&self) -> u32 { 1 }\n}\n", traits=["Draw"], functions=["draw", "size"])
case("rust", "nested_import", "use crate::{self, foo::{Bar, Baz as Q}, baz::*};\n", imports=["self", "Bar", "Q", "*"], attrs=[("imports", "Q", "full_import_name", "crate::foo::Baz")])
case("rust", "method_chain", "fn run() { service.build().send(); }\n", function_calls=["build", "send"], counts=[("function_calls", "build", 1), ("function_calls", "send", 1)])

for lang in ("c", "cpp"):
    case(lang, "pointer_returns", "int *build(int x) { helper(x); return 0; }\n", functions=["build"], function_calls=["helper"], absent=[("functions", "x")])
    case(lang, "function_pointer", "int run(int (*cb)(int), int x) { return cb(x); }\n", functions=["run"], function_calls=["cb"], absent=[("functions", "cb")])
    case(lang, "nested_calls", "int run(void) { return outer(inner(1), inner(2)); }\n", function_calls=["outer", "inner"], counts=[("function_calls", "inner", 2)])
    case(lang, "prototypes", "int helper(int x);\nint run(void) { return helper(1); }\n", functions=["run"], function_calls=["helper"], counts=[("function_calls", "helper", 1)])
case("cpp", "namespaces", "namespace demo {\nclass Service { public: void run() { helper(); } };\n}\n", classes=["Service"], functions=["run"], function_calls=["helper"], attrs=[("functions", "run", "class_context", "Service")])
case("cpp", "constructor_destructor", "class S { public: S() { init(); } ~S() { cleanup(); } };\n", functions=["S", "~S"], function_calls=["init", "cleanup"])
case("cpp", "generic_call", "void run() { identity<int>(1); }\n", functions=["run"], function_calls=["identity"])

case("java", "nested_types", "package demo;\nclass Outer {\n class Inner { void run() { helper(); } }\n}\n", classes=["Outer", "Inner"], functions=["run"], function_calls=["helper"], attrs=[("function_calls", "helper", "class_context.0", "Inner")])
case("java", "generic_inheritance", "class Child extends Parent<String> implements A, B {}\n", classes=["Child"], attrs=[("classes", "Child", "bases", ["Parent<String>", "A", "B"])])
case("java", "constructor", "class S { S(int x) { helper(x); } }\n", functions=["S"], function_calls=["helper"])
case("java", "interface", "interface S { void run(); default void go() { run(); } }\n", interfaces=["S"], functions=["run", "go"], function_calls=["run"])
case("java", "record", "record Point(int x, int y) { int sum() { return add(x,y); } }\n", classes=["Point"], functions=["sum"], function_calls=["add"], attrs=[("functions", "sum", "class_context", "Point")])
case("java", "static_import", "import static java.util.Collections.emptyList;\nclass S { void run() { emptyList(); } }\n", imports=["java.util.Collections.emptyList"], function_calls=["emptyList"])

case("c_sharp", "nested_context", "namespace Demo { class Outer { class Inner { void Run() { Helper(); } } } }\n", classes=["Outer", "Inner"], functions=["Run"], function_calls=["Helper"], attrs=[("function_calls", "Helper", "class_context.0", "Inner")])
case("c_sharp", "record", "record Point(int X, int Y) { int Sum() => Add(X, Y); }\n", records=["Point"], functions=["Sum"], function_calls=["Add"])
case("c_sharp", "local_function", "class S { void Outer() { void Inner() { Helper(); } Inner(); } }\n", functions=["Outer", "Inner"], function_calls=["Helper", "Inner"], attrs=[("function_calls", "Helper", "context.0", "Inner")])
case("c_sharp", "generic_bases", "class Child : Map<string, int>, IOne, ITwo {}\n", classes=["Child"], attrs=[("classes", "Child", "bases", ["Map<string, int>", "IOne", "ITwo"])])
case("c_sharp", "constructor", "class S { public S(int x) { Helper(x); } }\n", functions=["S"], function_calls=["Helper"])

case("ruby", "singleton", "class S\n def self.build(x)\n  helper(x)\n end\nend\n", classes=["S"], functions=["build"], function_calls=["helper"])
case("ruby", "module_context", "module Demo\n class S\n  def run\n   helper\n  end\n end\nend\n", modules=["Demo"], classes=["S"], functions=["run"], function_calls=["helper"])
case("ruby", "attribute_variables", "class S\n @@count = 0\n def run\n  @name = 'x'\n end\nend\n$flag = true\n", variables=["@@count", "@name", "$flag"])
case("ruby", "imports", "require 'json'\nrequire_relative './helper'\n", imports=["json", "./helper"])

case("php", "namespace", "<?php\nnamespace Demo;\nclass S { function run() { helper(); } }\n", classes=["S"], functions=["run"], function_calls=["helper"], attrs=[("function_calls", "helper", "class_context.0", "S")])
case("php", "enum", "<?php\nenum Status: string { case Ok = 'ok'; public function label() { return helper(); } }\n", classes=["Status"], functions=["label"], function_calls=["helper"])
case("php", "trait", "<?php\ntrait Work { function run() { helper(); } }\n", traits=["Work"], functions=["run"], function_calls=["helper"])
case("php", "imports", "<?php\nuse Vendor\\Package\\Thing as T;\nuse Vendor\\Package\\{One, Two as Second};\n", imports=["T", "One", "Second"])
case("php", "arrow_function", "<?php\nfunction outer() { $cb = fn($x) => helper($x); return $cb(1); }\n", functions=["outer", "cb"], function_calls=["helper"])

case("lua", "dot_colon_methods", "local M = {}\nfunction M.run(x) return helper(x) end\nfunction M:work(x) return helper(x) end\n", functions=["run", "work"], function_calls=["helper"], attrs=[("functions", "run", "class_context", "M"), ("functions", "work", "class_context", "M")])
case("lua", "assigned_functions", "local build = function(x) return helper(x) end\n", functions=["build"], function_calls=["helper"])
case("lua", "imports", "local json = require('json')\nlocal util = require 'util'\n", imports=["json", "util"])
case("lua", "nested_owner", "local function outer()\n local function inner() helper() end\n inner()\nend\n", functions=["outer", "inner"], function_calls=["helper", "inner"], attrs=[("function_calls", "helper", "context.0", "inner")])

case("kotlin", "extension", "fun String.clean(): String = trim()\n", functions=["clean"], function_calls=["trim"])
case("kotlin", "nested_context", "class Outer {\n class Inner { fun run() { helper() } }\n}\n", classes=["Outer", "Inner"], functions=["run"], function_calls=["helper"], attrs=[("function_calls", "helper", "class_context.0", "Inner")])
case("kotlin", "companion", "class S {\n companion object {\n  fun build() = S()\n }\n}\n", classes=["S"], functions=["build"], function_calls=["S"])
case("kotlin", "destructuring", "fun run() { val (first, second) = pair() }\n", functions=["run"], variables=["first", "second"], function_calls=["pair"])
case("kotlin", "interface", "interface Draw { fun draw() }\n", interfaces=["Draw"], functions=["draw"])

case("scala", "definitions", "object S {\n def run = helper()\n def helper(): Int = 1\n}\n", objects=["S"], functions=["run", "helper"], function_calls=["helper"])
case("scala", "trait_signatures", "trait Draw {\n def draw(x: Int): Unit\n}\n", traits=["Draw"], functions=["draw"])
case("scala", "curried_parameters", "def add(x: Int)(y: Int): Int = x + y\n", functions=["add"], attrs=[("functions", "add", "args", ["x", "y"])])
case("scala", "imports", "import scala.collection.{mutable, immutable}\n", imports=["scala.collection.mutable", "scala.collection.immutable"])

case("swift", "struct_method", "struct S {\n func run() { helper() }\n}\n", structs=["S"], functions=["run"], function_calls=["helper"], attrs=[("function_calls", "helper", "class_context.0", "S")])
case("swift", "protocol_signature", "protocol Draw {\n func draw(x: Int)\n}\n", traits=["Draw"], functions=["draw"])
case("swift", "extension", "extension String {\n func clean() { helper() }\n}\n", functions=["clean"], function_calls=["helper"], attrs=[("functions", "clean", "class_context", "String")])
case("swift", "init_deinit", "class S {\n init() { setup() }\n deinit { cleanup() }\n}\n", functions=["init", "deinit"], function_calls=["setup", "cleanup"])

case("haskell", "curried_call", "module Demo where\nrun x y = helper x y\n", functions=["run"], function_calls=["helper"], counts=[("function_calls", "helper", 1)])
case("haskell", "types", "module Demo where\ndata Point = Point Int Int\nclass Draw a where\n draw :: a -> String\n", classes=["Point", "Draw"])
case("haskell", "imports", "module Demo where\nimport qualified Data.Map as M\nimport Data.List (sort, nub)\n", imports=["Data.Map", "Data.List"])
case("haskell", "infix_call", "module Demo where\nrun x y = x `helper` y\n", functions=["run"], function_calls=["helper"], counts=[("function_calls", "helper", 1)])

case("dart", "class_methods", "class S {\n void run() { helper(); }\n}\n", classes=["S"], functions=["run"], function_calls=["helper"])
case("dart", "expression_function", "int add(int x, int y) => helper(x, y);\n", functions=["add"], function_calls=["helper"])
case("dart", "constructors", "class S {\n S() { setup(); }\n S.named() { setup(); }\n}\n", classes=["S"], functions=["S", "S.named"], function_calls=["setup"])
case("dart", "import_alias", "import 'dart:math' as math;\n", imports=["dart:math"], attrs=[("imports", "dart:math", "alias", "math")])

case("perl", "subroutine", "package Demo;\nsub run { helper(); }\n1;\n", classes=["Demo"], functions=["run"], function_calls=["helper"])
case("perl", "imports", "use strict;\nuse JSON;\n", imports=["strict", "JSON"])
case("perl", "variables", "my $count = 1;\nmy @items = (1, 2);\nmy %map = (a => 1);\n", variables=["count", "items", "map"])
case("perl", "multiple_packages", "package First;\nsub one { helper(); }\npackage Second;\nsub two { helper(); }\n", classes=["First", "Second"], functions=["one", "two"], attrs=[("functions", "one", "class_context", "First"), ("functions", "two", "class_context", "Second")])

case("elixir", "module_functions", "defmodule Demo do\n def run(x), do: helper(x)\n defp helper(x), do: x\nend\n", modules=["Demo"], functions=["run", "helper"], function_calls=["helper"])
case("elixir", "aliases", "defmodule Demo do\n alias MyApp.{One, Two}\n alias MyApp.Three, as: Third\nend\n", imports=["MyApp.One", "MyApp.Two", "MyApp.Three"], attrs=[("imports", "MyApp.Three", "alias", "Third")])
case("elixir", "pipeline", "defmodule Demo do\n def run(x), do: x |> helper() |> finish()\nend\n", function_calls=["helper", "finish"], counts=[("function_calls", "helper", 1)])
case("elixir", "guards_not_definitions", "defmodule Demo do\n def run(x) when is_integer(x), do: helper(x)\nend\n", functions=["run"], function_calls=["helper"], absent=[("functions", "is_integer")])

case("elisp", "function_macro", "(defun run (x) (helper x))\n(defmacro wrap (x) `(helper ,x))\n", functions=["run", "wrap"], function_calls=["helper"])
case("elisp", "quotes", "(setq value '(phantom 1))\n(defun run () (helper))\n", functions=["run"], function_calls=["helper"], absent=[("function_calls", "phantom")])
case("elisp", "imports", "(require 'cl-lib)\n(load \"helper\")\n", imports=["cl-lib", "helper"])

case("html", "quoted_attributes", '<div id="main" class="one two"></div>\n<script src="app.js"></script>\n<link href="app.css" rel="stylesheet">\n', classes=["one", "two"], variables=["main"], imports=["app.js", "app.css"])
case("html", "unquoted_attributes", '<div id=main class=one></div>\n<script src=app.js></script>\n<link href=app.css rel=stylesheet>\n', classes=["one"], variables=["main"], imports=["app.js", "app.css"])
case("html", "void_selfclosing_tags", '<img src="x.png" />\n<input id="email">\n<br>\n', tags=["img", "input", "br"], imports=["x.png"], variables=["email"])
case("html", "upper_case", '<DIV CLASS="one" ID="main"></DIV>\n', classes=["one"], variables=["main"], tags=["div"])

case("css", "selectors_variables", ".one, #main, button { --accent: red; color: var(--accent); }\n", functions=[".one", "#main", "button"], variables=["--accent"], attrs=[("variables", "--accent", "value", "red")])
case("css", "import_string", '@import "base.css";\n', imports=["base.css"])
case("css", "import_url", '@import url("base.css");\n@import url(theme.css);\n', imports=["base.css", "theme.css"])
case("css", "nested_media", "@media (width > 10px) { .one { color: red; } }\n", functions=[".one"])

for lang in ("vue", "svelte"):
    case(lang, "javascript_script", "<script>\nimport {helper} from './util';\nfunction run() { helper(); }\n</script>\n<p>Hello</p>\n", functions=["run"], imports=["helper"], function_calls=["helper"], attrs=[("functions", "run", "line_number", 3)])
    case(lang, "typescript_script", '<script lang="ts">\ninterface Props { name: string }\ntype ID = string;\nfunction run(x: ID) { return helper(x); }\n</script>\n', interfaces=["Props"], type_aliases=["ID"], functions=["run"], function_calls=["helper"])
    case(lang, "two_scripts", '<script context="module">\nfunction moduleFn() {}\n</script>\n<script>\nfunction instanceFn() { moduleFn(); }\n</script>\n', functions=["moduleFn", "instanceFn"], function_calls=["moduleFn"])
    case(lang, "template_is_not_script", "<p>phantom()</p>\n<style>.ghost {color:red}</style>\n", absent=[("function_calls", "phantom"), ("functions", "ghost")])

case("solidity", "contract", "pragma solidity ^0.8.0;\ncontract S { function run(uint x) public { helper(x); } function helper(uint x) internal {} }\n", classes=["S"], functions=["run", "helper"], function_calls=["helper"])
case("solidity", "interface", "pragma solidity ^0.8.0;\ninterface Draw { function draw() external; }\n", interfaces=["Draw"], functions=["draw"])
case("solidity", "library", "pragma solidity ^0.8.0;\nlibrary Math { function add(uint a,uint b) internal pure returns(uint) { return a+b; } }\n", classes=["Math"], functions=["add"])
case("solidity", "imports", 'pragma solidity ^0.8.0;\nimport {One as First, Two} from "./lib.sol";\n', imports=["One", "Two"], attrs=[("imports", "One", "alias", "First")])
case("hcl", "blocks", 'resource "aws_instance" "web" {\n ami = "ami-test"\n}\nmodule "network" {\n source = "./modules/network"\n}\n', classes=["aws_instance.web", "module.network"], import_suffixes=["/modules/network"])
case("hcl", "variables_locals", 'variable "region" {\n default = "us-east-1"\n}\nlocals {\n name = "demo"\n}\n', variables=["var.region", "local.name"])
case("hcl", "computed_source", 'module "network" {\n source = var.module_source\n}\n', classes=["module.network"], absent=[("imports", "var.module_source")])

# Cross-language invocation identity and nested argument boundary oracles.
EXTRA_CALL_CASES = [{'lang': 'python', 'name': 'repeated_same_line', 'source': 'def run(): helper(1); helper(2);\n'},
 {'lang': 'python', 'name': 'nested_arguments', 'source': 'def run(): helper(inner(1, 2), 3);\n'},
 {'lang': 'javascript', 'name': 'repeated_same_line', 'source': 'function run() { helper(1); helper(2); }\n'},
 {'lang': 'javascript', 'name': 'nested_arguments', 'source': 'function run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'typescript', 'name': 'repeated_same_line', 'source': 'function run() { helper(1); helper(2); }\n'},
 {'lang': 'typescript', 'name': 'nested_arguments', 'source': 'function run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'tsx', 'name': 'repeated_same_line', 'source': 'function run() { helper(1); helper(2); }\n'},
 {'lang': 'tsx', 'name': 'nested_arguments', 'source': 'function run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'go',
  'name': 'repeated_same_line',
  'source': 'package demo\nfunc run() { helper(1); helper(2); }\n'},
 {'lang': 'go',
  'name': 'nested_arguments',
  'source': 'package demo\nfunc run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'rust', 'name': 'repeated_same_line', 'source': 'fn run() { helper(1); helper(2); }\n'},
 {'lang': 'rust', 'name': 'nested_arguments', 'source': 'fn run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'c', 'name': 'repeated_same_line', 'source': 'void run(void) { helper(1); helper(2); }\n'},
 {'lang': 'c', 'name': 'nested_arguments', 'source': 'void run(void) { helper(inner(1, 2), 3); }\n'},
 {'lang': 'cpp', 'name': 'repeated_same_line', 'source': 'void run() { helper(1); helper(2); }\n'},
 {'lang': 'cpp', 'name': 'nested_arguments', 'source': 'void run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'java',
  'name': 'repeated_same_line',
  'source': 'class S { void run() { helper(1); helper(2); } }\n'},
 {'lang': 'java',
  'name': 'nested_arguments',
  'source': 'class S { void run() { helper(inner(1, 2), 3); } }\n'},
 {'lang': 'c_sharp',
  'name': 'repeated_same_line',
  'source': 'class S { void run() { helper(1); helper(2); } }\n'},
 {'lang': 'c_sharp',
  'name': 'nested_arguments',
  'source': 'class S { void run() { helper(inner(1, 2), 3); } }\n'},
 {'lang': 'ruby', 'name': 'repeated_same_line', 'source': 'def run; helper(1); helper(2);; end\n'},
 {'lang': 'ruby', 'name': 'nested_arguments', 'source': 'def run; helper(inner(1, 2), 3);; end\n'},
 {'lang': 'php', 'name': 'repeated_same_line', 'source': '<?php function run() { helper(1); helper(2); }\n'},
 {'lang': 'php', 'name': 'nested_arguments', 'source': '<?php function run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'lua', 'name': 'repeated_same_line', 'source': 'function run() helper(1); helper(2); end\n'},
 {'lang': 'lua', 'name': 'nested_arguments', 'source': 'function run() helper(inner(1, 2), 3); end\n'},
 {'lang': 'kotlin', 'name': 'repeated_same_line', 'source': 'fun run() { helper(1); helper(2); }\n'},
 {'lang': 'kotlin', 'name': 'nested_arguments', 'source': 'fun run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'scala',
  'name': 'repeated_same_line',
  'source': 'object S { def run() = { helper(1); helper(2); } }\n'},
 {'lang': 'scala',
  'name': 'nested_arguments',
  'source': 'object S { def run() = { helper(inner(1, 2), 3); } }\n'},
 {'lang': 'swift', 'name': 'repeated_same_line', 'source': 'func run() { helper(1); helper(2); }\n'},
 {'lang': 'swift', 'name': 'nested_arguments', 'source': 'func run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'haskell',
  'name': 'repeated_same_line',
  'source': 'module Demo where\nrun = (helper 1, helper 2)\n'},
 {'lang': 'haskell', 'name': 'nested_arguments', 'source': 'module Demo where\nrun = helper (inner 1 2) 3\n'},
 {'lang': 'dart', 'name': 'repeated_same_line', 'source': 'void run() { helper(1); helper(2); }\n'},
 {'lang': 'dart', 'name': 'nested_arguments', 'source': 'void run() { helper(inner(1, 2), 3); }\n'},
 {'lang': 'perl', 'name': 'repeated_same_line', 'source': 'sub run { helper(1); helper(2); }\n'},
 {'lang': 'perl', 'name': 'nested_arguments', 'source': 'sub run { helper(inner(1, 2), 3); }\n'},
 {'lang': 'elixir',
  'name': 'repeated_same_line',
  'source': 'defmodule Demo do\n def run do\n helper(1); helper(2);\n end\nend\n'},
 {'lang': 'elixir',
  'name': 'nested_arguments',
  'source': 'defmodule Demo do\n def run do\n helper(inner(1, 2), 3);\n end\nend\n'},
 {'lang': 'elisp', 'name': 'repeated_same_line', 'source': '(defun run () (helper 1) (helper 2))\n'},
 {'lang': 'elisp', 'name': 'nested_arguments', 'source': '(defun run () (helper (inner 1 2) 3))\n'},
 {'lang': 'vue',
  'name': 'repeated_same_line',
  'source': '<script> function run() { helper(1); helper(2); } </script>\n'},
 {'lang': 'vue',
  'name': 'nested_arguments',
  'source': '<script> function run() { helper(inner(1, 2), 3); } </script>\n'},
 {'lang': 'svelte',
  'name': 'repeated_same_line',
  'source': '<script> function run() { helper(1); helper(2); } </script>\n'},
 {'lang': 'svelte',
  'name': 'nested_arguments',
  'source': '<script> function run() { helper(inner(1, 2), 3); } </script>\n'},
 {'lang': 'solidity',
  'name': 'repeated_same_line',
  'source': 'pragma solidity ^0.8.0; contract S { function run() public { helper(1); helper(2); } }\n'},
 {'lang': 'solidity',
  'name': 'nested_arguments',
  'source': 'pragma solidity ^0.8.0; contract S { function run() public { helper(inner(1, 2), 3); } }\n'}]
for item in EXTRA_CALL_CASES:
    if item["name"] == "repeated_same_line":
        case(**item, counts=[("function_calls", "helper", 2)])
        identical_source = (item["source"].replace("helper(2)", "helper(1)")
                            .replace("(helper 2)", "(helper 1)")
                            .replace("helper 2", "helper 1"))
        case(item["lang"], "repeated_identical_same_line", identical_source,
             counts=[("function_calls", "helper", 2)])
    else:
        inner = "(inner 1 2)" if item["lang"] in ("haskell", "elisp") else "inner(1, 2)"
        case(**item, attrs=[("function_calls", "helper", "args", [inner, "3"])])

EXTENSIONS = dict(python="py", javascript="js", typescript="ts", tsx="tsx", go="go", rust="rs", c="c", cpp="cpp", java="java", c_sharp="cs", ruby="rb", php="php", lua="lua", kotlin="kt", scala="scala", swift="swift", haskell="hs", dart="dart", perl="pl", elixir="ex", elisp="el", html="html", css="css", vue="vue", svelte="svelte", solidity="sol", hcl="tf")
COMMENTS = {lang: "// audit π\n" for lang in EXTENSIONS}
COMMENTS.update({lang: "# audit π\n" for lang in ("python", "ruby", "perl", "elixir", "hcl")})
COMMENTS.update({lang: "-- audit π\n" for lang in ("lua", "haskell")})
COMMENTS.update(elisp="; audit π\n", html="<!-- audit π -->\n", vue="<!-- audit π -->\n", svelte="<!-- audit π -->\n", css="/* audit π */\n")


def field(record, key):
    current = record
    for part in key.split("."):
        if isinstance(current, (list, tuple)) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def check_result(result, checks, line_offset=0):
    failures = []
    for check in checks:
        op, bucket, name, *rest = check
        rows = [r for r in result.get(bucket, []) if isinstance(r, dict) and r.get("name") == name]
        if op == "suffix":
            ok = any(r.get("name", "").endswith(name) for r in result.get(bucket, []))
        elif op == "has":
            ok = bool(rows)
        elif op == "absent":
            ok = not rows
        elif op == "count":
            ok = len(rows) == rest[0]
        else:
            key, value = rest
            if key == "line_number":
                value += line_offset
            ok = any(field(row, key) == value for row in rows)
        if not ok:
            failures.append(dict(check=check, actual=rows if op != "has" else result.get(bucket, [])))
    return failures


def audit(languages=None):
    results = []
    with tempfile.TemporaryDirectory(prefix="cgc_parser_audit_") as directory:
        for lang in EXTENSIONS:
            if languages and lang not in languages:
                continue
            try:
                parser = TreeSitterParser(lang)
            except Exception:
                results.append(dict(lang=lang, name="initialization", exception=traceback.format_exc()))
                continue
            language_cases = [c for c in CASES if c["lang"] == lang]
            for blank_name, source in (("empty", ""), ("whitespace", " \n\t\n"), ("comments_only", COMMENTS[lang]), ("recovery", "{ [ (\n")):
                path = Path(directory) / ("empty." + EXTENSIONS[lang])
                path.write_text(source, encoding="utf-8")
                try:
                    data = parser.parse(path)
                    errors = []
                    if not isinstance(data, dict) or data.get("error"):
                        errors.append(dict(check="dict_without_error", actual=data))
                    if blank_name != "recovery":
                        for bucket in ("functions", "classes", "imports", "variables", "function_calls", "structs", "traits", "interfaces", "enums", "components"):
                            unexpected = [r for r in data.get(bucket, []) if not r.get("is_synthetic")]
                            if unexpected:
                                errors.append(dict(check=["empty", bucket], actual=unexpected))
                    results.append(dict(lang=lang, name=blank_name, failures=errors))
                except Exception:
                    results.append(dict(lang=lang, name=blank_name, exception=traceback.format_exc()))
            for item in language_cases:
                for variant in ("plain", "crlf", "padded_unicode", "dependency_source", "plain_again"):
                    source = item["source"]
                    offset = 0
                    if variant == "crlf":
                        source = source.replace("\n", "\r\n")
                    elif variant == "padded_unicode":
                        source = COMMENTS[lang] + source
                        offset = 1
                    path = Path(directory) / (item["name"] + "." + EXTENSIONS[lang])
                    path.write_bytes(source.encode("utf-8"))
                    record = dict(lang=lang, name=item["name"], variant=variant, source=source, checks=item["checks"])
                    try:
                        tree = parser.parser.parse(source.encode("utf-8"))
                        record["grammar_has_error"] = tree.root_node.has_error
                        data = parser.parse(path, is_dependency=variant == "dependency_source", index_source=variant == "dependency_source")
                        errors = check_result(data, item["checks"], offset)
                        if data.get("error"):
                            errors.append(dict(check="no_error", actual=data["error"]))
                        if data.get("is_dependency") != (variant == "dependency_source"):
                            errors.append(dict(check="dependency_flag", actual=data.get("is_dependency")))
                        record["failures"] = errors
                        record["actual"] = data
                    except Exception:
                        record["exception"] = traceback.format_exc()
                    results.append(record)
                # The full parser and cross-file pre-scan must agree on ordinary
                # top-level declarations. Keep this separate from call extraction.
                path.write_text(item["source"], encoding="utf-8")
                try:
                    data = parser.parse(path)
                    ext = "." + EXTENSIONS[lang]
                    scanned = pre_scan_for_imports([path], {ext}, lambda _: parser)
                    missing = []
                    if lang not in ("html", "css", "hcl"):
                        for bucket in ("functions", "classes", "structs", "traits", "interfaces", "enums", "modules", "objects", "type_aliases"):
                            for declaration in data.get(bucket, []):
                                contexts = [declaration.get(k) for k in ("context", "class_context", "module_context")]
                                contexts = [v[0] if isinstance(v, (tuple, list)) and v else v for v in contexts]
                                if any(contexts) or declaration.get("is_synthetic"):
                                    continue
                                name = declaration.get("name")
                                if name and name not in scanned:
                                    missing.append(dict(check=["prescan", bucket, name], actual=sorted(scanned)))
                    results.append(dict(lang=lang, name=item["name"], variant="prescan", source=item["source"], failures=missing))
                except Exception:
                    results.append(dict(lang=lang, name=item["name"], variant="prescan", source=item["source"], exception=traceback.format_exc()))
            failed = sum(bool(x.get("failures") or x.get("exception")) for x in results if x["lang"] == lang)
            total = sum(x["lang"] == lang for x in results)
            print(f"{lang}: {total - failed}/{total} cases passed", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", action="append")
    parser.add_argument("--output", type=Path, default=Path("parser-audit.json"))
    args = parser.parse_args()
    # Deliberately fail if registry growth outpaces the audit matrix.
    module = Path(__file__).resolve().parents[1] / "src/codegraphcontext/tools/tree_sitter_parser.py"
    registry = next(n.value for n in ast.walk(ast.parse(module.read_text())) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LANGUAGE_PARSER_MAP" for t in n.targets))
    assert set(ast.literal_eval(registry)) == set(EXTENSIONS), "Parser registry and audit language inventory differ"
    results = audit(set(args.language) if args.language else None)
    versions = {name: importlib.metadata.version(name) for name in ("codegraphcontext", "tree-sitter", "tree-sitter-language-pack")}
    failures = [r for r in results if r.get("failures") or r.get("exception")]
    args.output.write_text(json.dumps(dict(versions=versions, results=results), indent=2, default=str), encoding="utf-8")
    print(json.dumps(dict(total=len(results), failing=len(failures), by_language=dict(Counter(r["lang"] for r in failures)))), flush=True)
    for r in failures:
        if r.get("variant") not in (None, "plain"):
            continue
        print("FINDING " + json.dumps({k: r[k] for k in ("lang", "name", "grammar_has_error", "failures", "exception") if k in r}, default=str), flush=True)
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
