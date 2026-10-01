# src/codegraphcontext/tools/languages/hcl.py
"""A parser for HCL2 files using tree-sitter.

Covers Terraform / OpenTofu (`.tf`, `.tfvars`) and Terragrunt (`.hcl`). Blocks become
Class nodes under their canonical Terraform address (`azurerm_key_vault.this`,
`module.network`, `data.azurerm_client_config.current`), inputs and locals become
Variable nodes, and anything that names another unit of code -- a module `source`, a
Terragrunt `terraform { source }`, `include { path }` or `dependency { config_path }` --
becomes an import when it is written as a literal, so "which stacks consume this module" is a
graph query.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# `resource "azurerm_key_vault" "this"`: the first label is the type, the second the name.
_TYPE_AND_NAME_BLOCKS = {"resource", "data"}
# Terragrunt attribute holding a path to another configuration, per block type.
_PATH_ATTRIBUTES = {"include": "path", "dependency": "config_path", "terraform": "source"}
# Terragrunt functions for "the directory of this file". A reference built on one of them points
# somewhere different from every file that writes it, exactly like a relative path.
_OWN_DIR = re.compile(r"^\$\{\s*get(?:_original)?_terragrunt_dir\(\)\s*\}/?")


class HclTreeSitterParser:
    """A parser for HCL files using tree-sitter."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.language_name = "hcl"
        self.index_source = False

    def _text(self, node) -> str:
        return node.text.decode("utf-8", errors="replace")

    def _labels(self, block) -> List[str]:
        """The quoted labels of a block, unquoted: `resource "a" "b"` -> ["a", "b"]."""
        return [self._text(c).strip('"') for c in block.children if c.type == "string_lit"]

    def _body(self, block):
        for child in block.children:
            if child.type == "body":
                return child
        return None

    def _attributes(self, body) -> Dict[str, Any]:
        """Direct attribute children of a body, by name."""
        found = {}
        if body is None:
            return found
        for child in body.children:
            if child.type != "attribute":
                continue
            name = next((self._text(c) for c in child.children if c.type == "identifier"), None)
            if name is not None:
                found.setdefault(name, child)
        return found

    def _value_of(self, attribute) -> Optional[str]:
        """The right-hand side of `name = expression`, as written."""
        if attribute is None:
            return None
        expression = next((c for c in attribute.children if c.type == "expression"), None)
        return self._text(expression).strip() if expression is not None else None

    def _unquoted(self, value: Optional[str]) -> Optional[str]:
        """Strips the quotes of a string literal; leaves any other expression as written."""
        if value and len(value) > 1 and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    def _literal(self, attribute) -> Optional[str]:
        """The value of an attribute only when it is a string literal. An expression such as
        `find_in_parent_folders("root.hcl")` names no single target: taken literally it would
        merge every stack that uses the idiom onto one Module node, since imports merge by name."""
        value = self._value_of(attribute)
        if value and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return None

    def _address(self, block_type: str, labels: List[str]) -> str:
        if block_type in _TYPE_AND_NAME_BLOCKS and len(labels) >= 2:
            address = ".".join(labels[:2])
            return address if block_type == "resource" else f"{block_type}.{address}"
        if labels:
            return f"{block_type}.{labels[0]}"
        return block_type

    def _import(self, reference: Optional[str], node, path: Path) -> Optional[Dict[str, Any]]:
        if not reference:
            return None
        # Imports merge into Module nodes by name alone, so the name has to identify the target on
        # its own. A reference relative to the file that writes it therefore has to be resolved:
        # "../.." and "${get_terragrunt_dir()}/../this" name something different in every file.
        name = reference
        own_dir = _OWN_DIR.match(reference)
        if own_dir:
            name = reference[own_dir.end():]
        if own_dir or name.startswith("."):
            name = (Path(path).parent / name).resolve().as_posix()
        return {
            "name": name,
            "full_import_name": name,
            "source": name,
            "alias": None,
            "line_number": node.start_point[0] + 1,
            "lang": self.language_name,
        }

    def _block_node(self, block, block_type: str, labels: List[str], body) -> Dict[str, Any]:
        attributes = self._attributes(body)
        node = {
            "name": self._address(block_type, labels),
            "line_number": block.start_point[0] + 1,
            "end_line": block.end_point[0] + 1,
            "node_type": block_type,
            "context": None,
            "lang": self.language_name,
            "is_dependency": False,
            # Terraform's own description attribute is the block's documentation. Only a literal
            # one: an expression would store code where a reader expects prose.
            "docstring": self._literal(attributes.get("description")),
        }
        if self.index_source:
            node["source"] = self._text(block)
        return node

    def _variable(self, name: str, node, value: Optional[str], docstring: Optional[str] = None) -> Dict[str, Any]:
        return {
            "name": name,
            "line_number": node.start_point[0] + 1,
            "value": value,
            "docstring": docstring,
            "context": None,
            "lang": self.language_name,
            "is_dependency": False,
        }

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses an HCL file and returns its structure."""
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            source_code = handle.read()

        root_node = self.parser.parse(bytes(source_code, "utf8")).root_node

        classes: List[Dict[str, Any]] = []
        variables: List[Dict[str, Any]] = []
        imports: List[Dict[str, Any]] = []

        # A leading comment is a sibling of the body, not part of it, so the body is not
        # reliably the first child.
        top_level = []
        for child in root_node.children:
            top_level.extend(child.children if child.type == "body" else [child])

        for child in top_level:
            if child.type == "attribute":
                # Bare top-level assignment: a .tfvars entry, or Terragrunt `inputs = {...}`.
                name = next((self._text(c) for c in child.children if c.type == "identifier"), None)
                if name:
                    variables.append(self._variable(name, child, self._value_of(child)))
                continue
            if child.type != "block":
                continue

            block_type = next((self._text(c) for c in child.children if c.type == "identifier"), None)
            if not block_type:
                continue
            labels = self._labels(child)
            body = self._body(child)
            attributes = self._attributes(body)

            if block_type == "locals":
                for name, attribute in attributes.items():
                    variables.append(self._variable(f"local.{name}", attribute, self._value_of(attribute)))
                continue

            if block_type in ("variable", "output"):
                prefix = "var" if block_type == "variable" else "output"
                value_attribute = attributes.get("default" if block_type == "variable" else "value")
                variables.append(self._variable(
                    f"{prefix}.{labels[0]}" if labels else prefix,
                    child,
                    self._value_of(value_attribute),
                    self._literal(attributes.get("description")),
                ))
                continue

            if block_type in _TYPE_AND_NAME_BLOCKS or labels:
                classes.append(self._block_node(child, block_type, labels, body))

            # A literal reference from one unit of code to another becomes an import edge.
            if block_type == "module":
                imports.append(self._import(self._literal(attributes.get("source")), child, path))
            path_attribute = _PATH_ATTRIBUTES.get(block_type)
            if path_attribute:
                imports.append(self._import(self._literal(attributes.get(path_attribute)), child, path))

        return self._result(path, classes, variables, [i for i in imports if i], is_dependency)

    def _result(self, path, classes, variables, imports, is_dependency) -> Dict[str, Any]:
        return {
            "path": str(path),
            "functions": [],
            "classes": classes,
            "variables": variables,
            "imports": imports,
            "function_calls": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }


def pre_scan_hcl(files: List[Path], parser_wrapper) -> dict:
    """No import-name resolution to pre-scan: an HCL source is a path or a registry URL, not a
    symbol that has to be found in another file."""
    return {}
