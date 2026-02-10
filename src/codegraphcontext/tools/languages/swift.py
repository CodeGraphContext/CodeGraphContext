from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

SWIFT_QUERIES = {
    "functions": """
        [
            (function_declaration
                name: (simple_identifier) @name
                parameters: (parameter)* @params
            ) @function_node
            (init_declaration
                parameters: (parameter)* @params
            ) @init_node
        ]
    """,
    "classes": """
        [
            (class_declaration
                name: (type_identifier) @name
            ) @class
            (struct_declaration
                name: (type_identifier) @name
            ) @struct
            (enum_declaration
                name: (type_identifier) @name
            ) @enum
            (protocol_declaration
                name: (type_identifier) @name
            ) @protocol
        ]
    """,
    "imports": """
        (import_declaration) @import
    """,
    "calls": """
        (call_expression) @call_node
    """,
    "variables": """
        [
            (property_declaration
                (pattern) @pattern
            ) @variable
            (constant_declaration
                (pattern_binding
                    pattern: (simple_identifier) @name
                )
            ) @constant
        ]
    """,
}

class SwiftTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "swift"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        try:
            self.index_source = index_source
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            if not source_code.strip():
                warning_logger(f"Empty or whitespace-only file: {path}")
                return {
                    "path": str(path),
                    "functions": [],
                    "classes": [],
                    "structs": [],
                    "enums": [],
                    "protocols": [],
                    "variables": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            parsed_functions = []
            parsed_classes = []
            parsed_structs = []
            parsed_enums = []
            parsed_protocols = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []

            # Parse Variables first to populate for inference
            if 'variables' in SWIFT_QUERIES:
                results = execute_query(self.language, SWIFT_QUERIES['variables'], tree.root_node)
                parsed_variables = self._parse_variables(results, source_code, path)

            for capture_name, query in SWIFT_QUERIES.items():
                if capture_name == 'variables': continue  # Already done
                results = execute_query(self.language, query, tree.root_node)

                if capture_name == "functions":
                    parsed_functions.extend(self._parse_functions(results, source_code, path))
                elif capture_name == "classes":
                    classes, structs, enums, protocols = self._parse_classes(results, source_code, path)
                    parsed_classes.extend(classes)
                    parsed_structs.extend(structs)
                    parsed_enums.extend(enums)
                    parsed_protocols.extend(protocols)
                elif capture_name == "imports":
                    parsed_imports.extend(self._parse_imports(results, source_code))
                elif capture_name == "calls":
                    parsed_calls.extend(self._parse_calls(results, source_code, path, parsed_variables))

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "structs": parsed_structs,
                "enums": parsed_enums,
                "protocols": parsed_protocols,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

        except Exception as e:
            error_logger(f"Error parsing Swift file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "structs": [],
                "enums": [],
                "protocols": [],
                "variables": [],
                "imports": [],
                "function_calls": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

    def _get_parent_context(self, node: Any) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type == "function_declaration":
                name_node = None
                for child in curr.children:
                    if child.type == "simple_identifier":
                        name_node = child
                        break
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            if curr.type in ("class_declaration", "struct_declaration", "enum_declaration", "protocol_declaration"):
                for child in curr.children:
                    if child.type == "type_identifier":
                        return (
                            self._get_node_text(child),
                            curr.type,
                            curr.start_point[0] + 1,
                        )
            if curr.type == "init_declaration":
                # For initializers, return the parent class/struct name
                parent = curr.parent
                if parent and parent.type in ("class_body", "struct_body"):
                    grandparent = parent.parent
                    if grandparent:
                        for child in grandparent.children:
                            if child.type == "type_identifier":
                                return (
                                    self._get_node_text(child),
                                    grandparent.type,
                                    grandparent.start_point[0] + 1,
                                )
                return ("init", curr.type, curr.start_point[0] + 1)
            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    def _parse_functions(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        functions = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name in ("function_node", "init_node"):
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Get function name
                    func_name = "init" if capture_name == "init_node" else None
                    if capture_name == "function_node":
                        for child in node.children:
                            if child.type == "simple_identifier":
                                func_name = self._get_node_text(child)
                                break
                    
                    if not func_name:
                        continue
                    
                    # Extract parameters
                    parameters = []
                    for child in node.children:
                        if child.type == "parameter":
                            param_name = self._extract_parameter_name(child)
                            if param_name:
                                parameters.append(param_name)
                    
                    source_text = self._get_node_text(node)
                    context_name, context_type, context_line = self._get_parent_context(node)

                    func_data = {
                        "name": func_name,
                        "args": parameters,
                        "line_number": start_line,
                        "end_line": end_line,
                        "path": str(path),
                        "lang": self.language_name,
                        "context": context_name,
                        "class_context": context_name if context_type and ("class" in context_type or "struct" in context_type) else None
                    }
                    
                    if self.index_source:
                         func_data["source"] = source_text

                    functions.append(func_data)
                    
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path) -> Tuple[list, list, list, list]:
        classes = []
        structs = []
        enums = []
        protocols = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name in ("class", "struct", "enum", "protocol"):
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Find name
                    type_name = "Anonymous"
                    for child in node.children:
                        if child.type == "type_identifier":
                            type_name = self._get_node_text(child)
                            break
                    
                    source_text = self._get_node_text(node)
                    
                    # Extract inheritance/protocol conformance
                    bases = []
                    for child in node.children:
                        if child.type == "type_inheritance_clause":
                            for subchild in child.children:
                                if subchild.type == "type_identifier":
                                    bases.append(self._get_node_text(subchild))
                    
                    type_data = {
                        "name": type_name,
                        "line_number": start_line,
                        "end_line": end_line,
                        "bases": bases,
                        "path": str(path),
                        "lang": self.language_name,
                    }

                    if self.index_source:
                        type_data["source"] = source_text
                    
                    if capture_name == "class":
                        classes.append(type_data)
                    elif capture_name == "struct":
                        structs.append(type_data)
                    elif capture_name == "enum":
                        enums.append(type_data)
                    elif capture_name == "protocol":
                        protocols.append(type_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing type in {path}: {e}")
                    continue

        return classes, structs, enums, protocols

    def _parse_variables(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name in ("variable", "constant", "pattern"):
                try:
                    start_line = node.start_point[0] + 1
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                    var_name = "unknown"
                    var_type = "Unknown"
                    
                    # Try to extract variable name
                    if capture_name == "pattern":
                        var_name = self._get_node_text(node)
                    else:
                        for child in node.children:
                            if child.type == "simple_identifier":
                                var_name = self._get_node_text(child)
                                break
                            elif child.type == "pattern_binding":
                                for subchild in child.children:
                                    if subchild.type == "simple_identifier":
                                        var_name = self._get_node_text(subchild)
                                        break
                    
                    # Try to extract type annotation
                    for child in node.children:
                        if child.type == "type_annotation":
                            for subchild in child.children:
                                if subchild.type == "type_identifier":
                                    var_type = self._get_node_text(subchild)
                                    break

                    if var_name != "unknown":
                        var_key = (var_name, start_line)
                        if var_key not in seen_vars:
                            seen_vars.add(var_key)
                            variables.append({
                                "name": var_name,
                                "type": var_type,
                                "line_number": start_line,
                                "path": str(path),
                                "lang": self.language_name,
                                "context": ctx_name,
                                "class_context": ctx_name if ctx_type and ("class" in ctx_type or "struct" in ctx_type) else None
                            })
                except Exception as e:
                    continue

        return variables

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    text = self._get_node_text(node)
                    # import Foundation
                    # import UIKit
                    parts = text.replace('import ', '').strip().split()
                    module_name = parts[0] if parts else ""
                    
                    if module_name:
                        imports.append({
                            "name": module_name,
                            "full_import_name": module_name,
                            "line_number": node.start_point[0] + 1,
                            "alias": None,
                            "context": (None, None),
                            "lang": self.language_name,
                            "is_dependency": False,
                        })
                except Exception as e:
                    continue

        return imports

    def _parse_calls(self, captures: list, source_code: str, path: Path, variables: list[Dict[str, Any]] = []) -> list[Dict[str, Any]]:
        calls = []
        seen_calls = set()
        
        # Index variables for fast lookup
        var_map = {}
        for v in variables:
            key = (v['name'], v['context'])
            var_map[key] = v['type']

        for node, capture_name in captures:
            if capture_name == "call_node":
                try:
                    start_line = node.start_point[0] + 1
                    
                    call_name = "unknown"
                    base_obj = None
                    
                    # Extract function name from call expression
                    # call_expression can have various structures
                    first_child = node.children[0] if node.children else None
                    
                    if first_child:
                        if first_child.type == "simple_identifier":
                            call_name = self._get_node_text(first_child)
                        elif first_child.type == "navigation_expression":
                            # obj.method() pattern
                            for child in first_child.children:
                                if child.type == "simple_identifier":
                                    if not base_obj:
                                        base_obj = self._get_node_text(child)
                                    else:
                                        call_name = self._get_node_text(child)
                    
                    if call_name == "unknown":
                        continue
                    
                    full_name = f"{base_obj}.{call_name}" if base_obj else call_name
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    
                    # Type inference
                    inferred_type = None
                    if base_obj:
                        inferred_type = var_map.get((base_obj, ctx_name))
                        if not inferred_type:
                            inferred_type = var_map.get((base_obj, None))
                        if not inferred_type:
                            for (vname, vctx), vtype in var_map.items():
                                if vname == base_obj:
                                    inferred_type = vtype
                                    break

                    calls.append({
                        "name": call_name,
                        "full_name": full_name,
                        "line_number": start_line,
                        "args": [],
                        "inferred_obj_type": inferred_type,
                        "context": [None, ctx_type, ctx_line],
                        "class_context": [None, None],
                        "lang": self.language_name,
                        "is_dependency": False
                    })
                except Exception as e:
                    continue
        return calls

    def _extract_parameter_name(self, param_node: Any) -> Optional[str]:
        """Extract parameter name from a parameter node."""
        # Swift parameters can have external and internal names
        # parameter: external_name? internal_name: type
        for child in param_node.children:
            if child.type == "simple_identifier":
                return self._get_node_text(child)
        return None

def pre_scan_swift(files: list[Path], parser_wrapper) -> dict:
    """Pre-scan Swift files to build a map of class/struct/enum/protocol names to file paths."""
    name_to_files = {}
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extract classes, structs, enums, protocols
            matches = re.finditer(r'\b(class|struct|enum|protocol)\s+(\w+)', content)
            
            for match in matches:
                name = match.group(2)
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(str(path))
                    
        except Exception:
            pass
    return name_to_files
