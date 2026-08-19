# src/codegraphcontext/tools/languages/csharp.py
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

CSHARP_QUERIES = {
    # Fields and locals share a shape: `variable_declaration` carries the type
    # and holds one `variable_declarator` per name. There was no `variables`
    # query at all and the key was hardcoded to [], so C# produced no Variable
    # nodes — and `resolution/calls.py` lost the local-variable declarations it
    # uses to infer a receiver's type, so `var s = new UserService(); s.Save();`
    # could not resolve Save to UserService.Save.
    "variables": """
        (field_declaration
            (variable_declaration) @decl
        ) @field_node

        (local_declaration_statement
            (variable_declaration) @decl
        ) @local_node
    """,
    "functions": """
        (method_declaration
            name: (identifier) @name
            parameters: (parameter_list) @params
        ) @function_node
        
        (constructor_declaration
            name: (identifier) @name
            parameters: (parameter_list) @params
        ) @function_node
        
        (local_function_statement
            name: (identifier) @name
            parameters: (parameter_list) @params
        ) @function_node
    """,
    "classes": """
        (class_declaration 
            name: (identifier) @name
            (base_list)? @bases
        ) @class
    """,
    "interfaces": """
        (interface_declaration 
            name: (identifier) @name
            (base_list)? @bases
        ) @interface
    """,
    "structs": """
        (struct_declaration 
            name: (identifier) @name
            (base_list)? @bases
        ) @struct
    """,
    "enums": """
        (enum_declaration 
            name: (identifier) @name
        ) @enum
    """,
    "records": """
        (record_declaration 
            name: (identifier) @name
            (base_list)? @bases
        ) @record
    """,
    "properties": """
        (property_declaration
            name: (identifier) @name
        ) @property
    """,
    "imports": """
        (using_directive) @import
    """,
    "calls": """
        (invocation_expression
            function: [
                (identifier) @name
                (member_access_expression
                    name: (identifier) @name
                ) @full_name
            ]
        )
        
        (object_creation_expression
            type: [
                (identifier) @name
                (qualified_name) @name
            ]
        )
    """,

}

class CSharpTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "c_sharp"
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
                    "interfaces": [],
                    "structs": [],
                    "enums": [],
                    "records": [],
                    "properties": [],
                    "variables": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            # Extract namespace declaration for package_name (e.g. "com.ea.nucleus.billing")
            namespace_match = re.search(r'\bnamespace\s+([\w.]+)', source_code)
            package_name = namespace_match.group(1) if namespace_match else None

            parsed_functions = []
            parsed_classes = []
            parsed_interfaces = []
            parsed_structs = []
            parsed_enums = []
            parsed_records = []
            parsed_properties = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []

            for capture_name, query_str in CSHARP_QUERIES.items():
                captures = execute_query(self.language, query_str, tree.root_node)

                if capture_name == "functions":
                    parsed_functions = self._parse_functions(captures, source_code, path, tree.root_node)
                elif capture_name == "classes":
                    parsed_classes = self._parse_type_declarations(captures, source_code, path, "Class")
                elif capture_name == "interfaces":
                    parsed_interfaces = self._parse_type_declarations(captures, source_code, path, "Interface")
                elif capture_name == "structs":
                    parsed_structs = self._parse_type_declarations(captures, source_code, path, "Struct")
                elif capture_name == "enums":
                    parsed_enums = self._parse_type_declarations(captures, source_code, path, "Enum")
                elif capture_name == "records":
                    parsed_records = self._parse_type_declarations(captures, source_code, path, "Record")
                elif capture_name == "properties":
                    parsed_properties = self._parse_properties(captures, source_code, path, tree.root_node)
                elif capture_name == "variables":
                    parsed_variables = self._parse_variables(captures)
                elif capture_name == "imports":
                    parsed_imports = self._parse_imports(captures, source_code)
                elif capture_name == "calls":
                    parsed_calls = self._parse_calls(captures, source_code)

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "interfaces": parsed_interfaces,
                "structs": parsed_structs,
                "enums": parsed_enums,
                "records": parsed_records,
                "properties": parsed_properties,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
                "package_name": package_name,
            }

        except Exception as e:
            error_logger(f"Error parsing C# file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "interfaces": [],
                "structs": [],
                "enums": [],
                "records": [],
                "properties": [],
                "variables": [],
                "imports": [],
                "function_calls": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

    def _parse_functions(self, captures: list, source_code: str, path: Path, root_node) -> list[Dict[str, Any]]:
        functions = []
        source_lines = source_code.splitlines()

        for node, capture_name in captures:
            if capture_name == "function_node":
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_captures = [
                        (n, cn) for n, cn in captures 
                        if cn == "name" and n.parent.id == node.id
                    ]
                    
                    if name_captures:
                        name_node = name_captures[0][0]
                        func_name = self._get_node_text(name_node)
                        
                        params_captures = [
                            (n, cn) for n, cn in captures 
                            if cn == "params" and n.parent.id == node.id
                        ]
                        
                        parameters = []
                        if params_captures:
                            params_node = params_captures[0][0]
                            parameters = self._extract_parameters(params_node)

                        # Extract attributes applied to this function
                        attributes = []
                        if node.parent and node.parent.type == "attribute_list":
                            attr_text = self._get_node_text(node.parent)
                            attributes.append(attr_text)

                        # Find containing class/struct/interface
                        class_context = self._find_containing_type(node, source_code)

                        source_text = self._get_node_text(node)
                        
                        func_data = {
                            "name": func_name,
                            "args": parameters,
                            "attributes": attributes,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                        }
                        
                        # Add class context if found
                        if class_context:
                            func_data["class_context"] = class_context

                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_type_declarations(self, captures: list, source_code: str, path: Path, type_label: str) -> list[Dict[str, Any]]:
        """Parse class, interface, struct, enum, or record declarations with inheritance info."""
        types = []
        
        # Map capture names based on type
        capture_map = {
            "Class": "class",
            "Interface": "interface",
            "Struct": "struct",
            "Enum": "enum",
            "Record": "record"
        }
        expected_capture = capture_map.get(type_label, "class")

        for node, capture_name in captures:
            if capture_name == expected_capture:
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_captures = [
                        (n, cn) for n, cn in captures 
                        if cn == "name" and n.parent.id == node.id
                    ]
                    
                    if name_captures:
                        name_node = name_captures[0][0]
                        type_name = self._get_node_text(name_node)
                        
                        # Extract base classes/interfaces
                        bases = []
                        bases_captures = [
                            (n, cn) for n, cn in captures 
                            if cn == "bases" and n.parent.id == node.id
                        ]
                        
                        if bases_captures:
                            bases_node = bases_captures[0][0]
                            bases_text = self._get_node_text(bases_node)
                            # Parse base list: ": BaseClass, IInterface1, IInterface2"
                            bases_text = bases_text.strip().lstrip(':').strip()
                            if bases_text:
                                # Split on TOP-LEVEL commas only: a naive split
                                # shredded multi-arg generics —
                                # `: Dictionary<string, int>` became two bases,
                                # 'Dictionary<string' and 'int>', creating
                                # INHERITS edges to nonexistent types (#1538).
                                raw_bases = []
                                depth = 0
                                current = []
                                for ch in bases_text:
                                    if ch in "<([":
                                        depth += 1
                                    elif ch in ">)]":
                                        depth = max(0, depth - 1)
                                    if ch == "," and depth == 0:
                                        raw_bases.append("".join(current).strip())
                                        current = []
                                    else:
                                        current.append(ch)
                                if current:
                                    raw_bases.append("".join(current).strip())
                                # records might have base calls like : Person(name, age)
                                # we want just Person
                                for rb in raw_bases:
                                    base_name = rb.split('(')[0].strip()
                                    if base_name:
                                        bases.append(base_name)
                        
                        source_text = self._get_node_text(node)
                        
                        type_data = {
                            "name": type_name,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "is_partial": bool(re.search(r"\bpartial\b", source_text)),
                        }
                        
                        # Add bases if found
                        if bases:
                            type_data["bases"] = bases

                        if self.index_source:
                            type_data["source"] = source_text
                        
                        types.append(type_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing {type_label} in {path}: {e}")
                    continue

        return types

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    import_text = self._get_node_text(node)
                    # Match: using System.Collections.Generic; or using static System.Math;
                    import_match = re.search(r'using\s+(?:static\s+)?([^;]+)', import_text)
                    if import_match:
                        import_path = import_match.group(1).strip()
                        
                        # Check for alias: using MyAlias = System.Collections.Generic.List<int>;
                        alias = None
                        if '=' in import_path:
                            parts = import_path.split('=')
                            alias = parts[0].strip()
                            import_path = parts[1].strip()
                        
                        import_data = {
                            "name": import_path,
                            "full_import_name": import_path,
                            "line_number": node.start_point[0] + 1,
                            "alias": alias,
                            "context": (None, None),
                            "lang": self.language_name,
                            "is_dependency": False,
                        }
                        imports.append(import_data)
                except Exception as e:
                    error_logger(f"Error parsing import: {e}")
                    continue

        return imports

    def _parse_variables(self, captures: list) -> list:
        """Fields and locals, from `variable_declaration` nodes.

        Both shapes nest identically — `variable_declaration` carries the type
        and holds one `variable_declarator` per declared name, so
        `int a = 1, b = 2;` yields two rows sharing a type.
        """
        variables = []
        seen = set()
        for node, capture_name in captures:
            if capture_name != "decl":
                continue
            type_node = node.child_by_field_name("type")
            var_type = self._get_node_text(type_node) if type_node is not None else None

            for declarator in node.children:
                if declarator.type != "variable_declarator":
                    continue
                name_node = declarator.child_by_field_name("name")
                if name_node is None:
                    name_node = next(
                        (c for c in declarator.children if c.type == "identifier"), None
                    )
                if name_node is None:
                    continue

                line_number = name_node.start_point[0] + 1
                name = self._get_node_text(name_node)
                if (name, line_number) in seen:
                    continue
                seen.add((name, line_number))

                # tree-sitter-c-sharp has no `equals_value_clause`: the
                # initialiser is a direct sibling following the `=` token.
                value = None
                seen_equals = False
                for child in declarator.children:
                    if child.type == "=":
                        seen_equals = True
                        continue
                    if seen_equals and child.is_named:
                        value = self._get_node_text(child)
                        break

                context, _ctx_type, _ctx_line = self._get_parent_context(
                    declarator, types=("method_declaration", "function_declaration")
                )
                class_context, _c_type, _c_line = self._get_parent_context(
                    declarator,
                    types=("class_declaration", "struct_declaration", "record_declaration"),
                )

                variables.append({
                    "name": name,
                    "line_number": line_number,
                    "value": value,
                    "type": var_type,
                    "context": context,
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return variables

    def _get_parent_context(self, node: Any, types: Tuple[str, ...] = ('class_declaration', 'struct_declaration', 'function_declaration', 'method_declaration')):
        """Find parent context for C# constructs."""
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name('name')
                if name_node:
                    return self._get_node_text(name_node), curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    def _parse_calls(self, captures: list, source_code: str) -> list[dict]:
        calls = []
        seen_calls = set()
        
        # Build a map of node id to its full_name text
        full_names = {}
        for node, capture_name in captures:
            if capture_name == "full_name":
                full_names[node.id] = self._get_node_text(node)

        for node, capture_name in captures:
            if capture_name == "name":
                try:
                    call_name = self._get_node_text(node)
                    line_number = node.start_point[0] + 1
                    
                    # Avoid duplicates at the same line for the same name
                    call_key = f"{call_name}_{line_number}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)
                    
                    # Check if this name is part of a member_access_expression
                    full_call_name = call_name
                    if node.parent and node.parent.id in full_names:
                        full_call_name = full_names[node.parent.id]
                    
                    # Get context
                    context_name, context_type, context_line = self._get_parent_context(node)
                    # A call's first enclosing declaration is its METHOD, so
                    # `'class' in context_type` was always false and every
                    # call's class_context was None (#1538). Walk again for
                    # class-like ancestors only, cpp-style.
                    cls_name, _cls_type, cls_line = self._get_parent_context(
                        node,
                        types=("class_declaration", "struct_declaration",
                               "record_declaration", "interface_declaration"),
                    )
                    class_context = (cls_name, cls_line) if cls_name else None

                    call_data = {
                        "name": call_name,
                        "full_name": full_call_name,
                        "line_number": line_number,
                        "args": [],
                        "inferred_obj_type": None,
                        "context": (context_name, context_type, context_line),
                        "class_context": class_context,
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    calls.append(call_data)
                except Exception as e:
                    error_logger(f"Error parsing call: {e}")
                    continue

        return calls

    

    def _extract_parameters(self, params_node) -> list[str]:
        params = []
        if not params_node:
            return params
            
        # Iterate over parameter nodes in the parameter list
        for child in params_node.children:
            if child.type == "parameter":
                # find the identifier
                name_node = child.child_by_field_name("name")
                if name_node:
                     params.append(self._get_node_text(name_node))
                else:
                    # Fallback: scan children for identifier if field name not present in this grammar version
                    for sub in child.children:
                        if sub.type == "identifier":
                            params.append(self._get_node_text(sub))
                            break
        return params

    def _find_containing_type(self, node, source_code):
        """Find the containing class, struct, interface, or record for a given node."""
        current = node.parent
        while current:
            if current.type in ['class_declaration', 'struct_declaration', 'interface_declaration', 'record_declaration']:
                # Find the name of this type
                for child in current.children:
                    if child.type == 'identifier':
                        return self._get_node_text(child)
            current = current.parent
        return None

    def _parse_properties(self, captures: list, source_code: str, path: Path, root_node) -> list[Dict[str, Any]]:
        """Parse C# properties."""
        properties = []
        
        for node, capture_name in captures:
            if capture_name == "property":
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_captures = [
                        (n, cn) for n, cn in captures 
                        if cn == "name" and n.parent == node
                    ]
                    
                    if name_captures:
                        name_node = name_captures[0][0]
                        prop_name = self._get_node_text(name_node)
                        
                        # Get property type from node children
                        prop_type = None
                        for child in node.children:
                            if child.type in ['predefined_type', 'identifier', 'generic_name', 'nullable_type', 'array_type']:
                                prop_type = self._get_node_text(child)
                                break
                        
                        
                        # Find containing class/struct
                        class_context = self._find_containing_type(node, source_code)
                        
                        source_text = self._get_node_text(node)
                        
                        prop_data = {
                            "name": prop_name,
                            "type": prop_type,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                        }
                        
                        if class_context:
                            prop_data["class_context"] = class_context
                            
                        if self.index_source:
                            prop_data["source"] = source_text
                        
                        properties.append(prop_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing property in {path}: {e}")
                    continue
        
        return properties



def pre_scan_csharp(files: list[Path], parser_wrapper) -> dict:
    """Pre-scan C# files to build a name-to-files mapping."""
    name_to_files = {}
    
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Match class declarations
            class_matches = re.finditer(
                r'\b(?:public\s+|private\s+|protected\s+|internal\s+)?(?:static\s+)?(?:abstract\s+)?(?:sealed\s+)?(?:partial\s+)?class\s+(\w+)',
                content
            )
            for match in class_matches:
                class_name = match.group(1)
                if class_name not in name_to_files:
                    name_to_files[class_name] = []
                name_to_files[class_name].append(str(path))
            
            # Match interface declarations
            interface_matches = re.finditer(
                r'\b(?:public\s+|private\s+|protected\s+|internal\s+)?(?:partial\s+)?interface\s+(\w+)',
                content
            )
            for match in interface_matches:
                interface_name = match.group(1)
                if interface_name not in name_to_files:
                    name_to_files[interface_name] = []
                name_to_files[interface_name].append(str(path))
            
            # Match struct declarations
            struct_matches = re.finditer(
                r'\b(?:public\s+|private\s+|protected\s+|internal\s+)?(?:readonly\s+)?(?:partial\s+)?struct\s+(\w+)',
                content
            )
            for match in struct_matches:
                struct_name = match.group(1)
                if struct_name not in name_to_files:
                    name_to_files[struct_name] = []
                name_to_files[struct_name].append(str(path))
            
            # Match record declarations
            record_matches = re.finditer(
                r'\b(?:public\s+|private\s+|protected\s+|internal\s+)?(?:sealed\s+)?record\s+(?:class\s+)?(\w+)',
                content
            )
            for match in record_matches:
                record_name = match.group(1)
                if record_name not in name_to_files:
                    name_to_files[record_name] = []
                name_to_files[record_name].append(str(path))
                
        except Exception as e:
            error_logger(f"Error pre-scanning C# file {path}: {e}")
            
    return name_to_files
