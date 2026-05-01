"""Build global imports_map via language-specific pre-scan (registry dispatch)."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# (extension -> callable(files, get_parser_for_ext) -> dict updates)
_PreScanFn = Callable[[List[Path], Callable[[str], Any]], dict]


def _register_prescans() -> Dict[str, _PreScanFn]:
    from ..languages import python as python_lang_module
    from ..languages import javascript as js_lang_module
    from ..languages import go as go_lang_module
    from ..languages import typescript as ts_lang_module
    from ..languages import typescriptjsx as tsx_lang_module
    from ..languages import cpp as cpp_lang_module
    from ..languages import rust as rust_lang_module
    from ..languages import c as c_lang_module
    from ..languages import java as java_lang_module
    from ..languages import ruby as ruby_lang_module
    from ..languages import csharp as csharp_lang_module
    from ..languages import kotlin as kotlin_lang_module
    from ..languages import scala as scala_lang_module
    from ..languages import swift as swift_lang_module
    from ..languages import dart as dart_lang_module
    from ..languages import perl as perl_lang_module
    from ..languages import php as php_lang_module
    from ..languages import haskell as haskell_lang_module
    from ..languages import elixir as elixir_lang_module

    def make_py(ext: str) -> _PreScanFn:
        def scan(files: List[Path], gp: Callable[[str], Any]) -> dict:
            return python_lang_module.pre_scan_python(files, gp(ext))

        return scan

    def make_js(ext: str) -> _PreScanFn:
        def scan(files: List[Path], gp: Callable[[str], Any]) -> dict:
            return js_lang_module.pre_scan_javascript(files, gp(ext))

        return scan

    return {
        ".py": make_py(".py"),
        ".ipynb": make_py(".ipynb"),
        ".js": make_js(".js"),
        ".jsx": make_js(".jsx"),
        ".mjs": make_js(".mjs"),
        ".cjs": make_js(".cjs"),
        ".go": lambda files, gp: go_lang_module.pre_scan_go(files, gp(".go")),
        ".ts": lambda files, gp: ts_lang_module.pre_scan_typescript(files, gp(".ts")),
        ".tsx": lambda files, gp: tsx_lang_module.pre_scan_typescript(files, gp(".tsx")),
        ".cpp": lambda files, gp: cpp_lang_module.pre_scan_cpp(files, gp(".cpp")),
        ".h": lambda files, gp: cpp_lang_module.pre_scan_cpp(files, gp(".h")),
        ".hpp": lambda files, gp: cpp_lang_module.pre_scan_cpp(files, gp(".hpp")),
        ".hh": lambda files, gp: cpp_lang_module.pre_scan_cpp(files, gp(".hh")),
        ".rs": lambda files, gp: rust_lang_module.pre_scan_rust(files, gp(".rs")),
        ".c": lambda files, gp: c_lang_module.pre_scan_c(files, gp(".c")),
        ".java": lambda files, gp: java_lang_module.pre_scan_java(files, gp(".java")),
        ".rb": lambda files, gp: ruby_lang_module.pre_scan_ruby(files, gp(".rb")),
        ".cs": lambda files, gp: csharp_lang_module.pre_scan_csharp(files, gp(".cs")),
        ".kt": lambda files, gp: kotlin_lang_module.pre_scan_kotlin(files, gp(".kt")),
        ".scala": lambda files, gp: scala_lang_module.pre_scan_scala(files, gp(".scala")),
        ".sc": lambda files, gp: scala_lang_module.pre_scan_scala(files, gp(".sc")),
        ".swift": lambda files, gp: swift_lang_module.pre_scan_swift(files, gp(".swift")),
        ".dart": lambda files, gp: dart_lang_module.pre_scan_dart(files, gp(".dart")),
        ".pl": lambda files, gp: perl_lang_module.pre_scan_perl(files, gp(".pl")),
        ".pm": lambda files, gp: perl_lang_module.pre_scan_perl(files, gp(".pm")),
        ".php": lambda files, gp: php_lang_module.pre_scan_php(files, gp(".php")),
        ".hs": lambda files, gp: haskell_lang_module.pre_scan_haskell(files, gp(".hs")),
        ".ex": lambda files, gp: elixir_lang_module.pre_scan_elixir(files, gp(".ex")),
        ".exs": lambda files, gp: elixir_lang_module.pre_scan_elixir(files, gp(".exs")),
    }


_PRESCAN_REGISTRY: Optional[Dict[str, _PreScanFn]] = None


def _get_registry() -> Dict[str, _PreScanFn]:
    global _PRESCAN_REGISTRY
    if _PRESCAN_REGISTRY is None:
        _PRESCAN_REGISTRY = _register_prescans()
    return _PRESCAN_REGISTRY


def pre_scan_for_imports(
    files: List[Path],
    parsers_keys: Any,
    get_parser: Callable[[str], Any],
) -> dict:
    """Dispatch pre-scan by file extension; *parsers_keys* is the set of supported extensions (e.g. graph_builder.parsers.keys())."""
    imports_map: dict = {}
    files_by_ext: Dict[str, List[Path]] = {}
    for file in files:
        if file.suffix in parsers_keys:
            ext = file.suffix
            files_by_ext.setdefault(ext, []).append(file)

    registry = _get_registry()
    for ext, file_list in files_by_ext.items():
        scanner = registry.get(ext)
        if scanner:
            imports_map.update(scanner(file_list, get_parser))

    return imports_map
