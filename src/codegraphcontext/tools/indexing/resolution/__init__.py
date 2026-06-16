# src/codegraphcontext/tools/indexing/resolution/__init__.py
from .calls import build_function_call_groups, resolve_function_call
from .inheritance import (
    build_go_implements_links,
    build_haskell_implements_links,
    build_inheritance_and_csharp_files,
    build_partial_of_links,
    build_part_of_links,
)

__all__ = [
    "build_function_call_groups",
    "resolve_function_call",
    "build_go_implements_links",
    "build_haskell_implements_links",
    "build_inheritance_and_csharp_files",
    "build_partial_of_links",
    "build_part_of_links",
]
