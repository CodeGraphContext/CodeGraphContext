from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

KOTLIN_QUERIES = {
    "functions": """
        (function_declaration
            (simple_identifier) @name
            (function_value_parameters) @params
        ) @function_node
    """,
    "classes": """
        [
            (class_declaration (type_identifier) @name)
            (object_declaration (type_identifier) @name)
            (companion_object (type_identifier)? @name)
        ] @class
    """,
    "imports": """
        (import_header) @import
    """,
    "calls": """
        (call_expression) @call_node
    """,
    "variables": """
        (property_declaration
            (variable_declaration
                (simple_identifier) @name
            )
        ) @variable
    """,
}

class KotlinTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "kotlin"
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
                    "variables": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            parsed_functions = []
            parsed_classes = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []

            # Parse Variables first to populate for inference
            if 'variables' in KOTLIN_QUERIES:
                 results = execute_query(self.language, KOTLIN_QUERIES['variables'], tree.root_node)
                 parsed_variables = self._parse_variables(results, source_code, path)

            for capture_name, query in KOTLIN_QUERIES.items():
                if capture_name == 'variables': continue # Already done
                results = execute_query(self.language, query, tree.root_node)

                if capture_name == "functions":
                    parsed_functions.extend(self._parse_functions(results, source_code, path))
                elif capture_name == "classes":
                    parsed_classes.extend(self._parse_classes(results, source_code, path))
                elif capture_name == "imports":
                    parsed_imports.extend(self._parse_imports(results, source_code))
                elif capture_name == "calls":
                    parsed_calls.extend(self._parse_calls(results, source_code, path, parsed_variables))

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

        except Exception as e:
            error_logger(f"Error parsing Kotlin file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "variables": [],
                "imports": [],
                "function_calls": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

    def _get_parent_context(self, node: Any) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in ("function_declaration",):
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
            if curr.type in ("class_declaration", "object_declaration"):
                for child in curr.children:
                    if child.type in ("simple_identifier", "type_identifier"):
                         return (
                            self._get_node_text(child),
                            curr.type,
                            curr.start_point[0] + 1,
                        )
                # Check for secondary constructors
                if curr.type == "secondary_constructor":
                    return (
                        "constructor",
                        curr.type,
                        curr.start_point[0] + 1
                    )
                    
            if curr.type == "companion_object":
                 name = "Companion"
                 for child in curr.children:
                     if child.type in ("simple_identifier", "type_identifier"): 
                         name = self._get_node_text(child)
                         break
                 return (
                    name,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            
            # Handle anonymous objects (object_literal)
            if curr.type == "object_literal":
                 # checking if it is assigned to a variable to get a name?
                 # or simply "AnonymousObject"
                 # It's usually hard to name them without variable context.
                 # We can check if parent is property/variable declaration
                 name = "AnonymousObject"
                 return (
                    name,
                    curr.type,
                    curr.start_point[0] + 1
                 )

            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    def _parse_functions(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        functions = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "function_node":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Manual child lookup
                    name_node = None
                    for child in node.children:
                        if child.type == "simple_identifier":
                            name_node = child
                            break
                            
                    if name_node:
                        func_name = self._get_node_text(name_node)
                        
                        params_node = None
                        for child in node.children:
                            if child.type == "function_value_parameters":
                                params_node = child
                                break
                                
                        parameters = []
                        if params_node:
                            params_text = self._get_node_text(params_node)
                            parameters = self._extract_parameter_names(params_text)

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
                            "class_context": context_name if context_type and ("class" in context_type or "object" in context_type) else None
                        }
                        
                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        classes = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "class":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Find name child (type_identifier or simple_identifier)
                    class_name = "Anonymous"
                    if node.type == "companion_object":
                        class_name = "Companion" # Default name
                    
                    for child in node.children:
                        if child.type in ("type_identifier", "simple_identifier"):
                            class_name = self._get_node_text(child)
                            break
                            
                    source_text = self._get_node_text(node)
                    
                    bases = []
                    # Check for delegation specifiers
                    # class_declaration -> delegation_specifier
                    
                    for child in node.children:
                        if child.type == "delegation_specifier":
                             # children: constructor_invocation or user_type
                             for specifier in child.children:
                                 # constructor_invocation -> user_type -> type_identifier
                                 # user_type -> type_identifier
                                 
                                 # We want the text of the type
                                 if specifier.type == "constructor_invocation":
                                     # child 0 is typically user_type
                                      for sub in specifier.children:
                                          if sub.type == "user_type":
                                              bases.append(self._get_node_text(sub))
                                              break
                                 elif specifier.type == "user_type":
                                     bases.append(self._get_node_text(specifier))
                                 elif specifier.type == "explicit_delegation":
                                     # Not handling simple yet, uses 'by'
                                     pass


                    class_data = {
                        "name": class_name,
                        "line_number": start_line,
                        "end_line": end_line,
                        "bases": bases,
                        "path": str(path),
                        "lang": self.language_name,
                    }

                    if self.index_source:
                        class_data["source"] = source_text
                    
                    classes.append(class_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing class in {path}: {e}")
                    continue

        return classes

    def _parse_variables(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name == "variable":
                try:
                    start_line = node.start_point[0] + 1
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                    # Destructuring declaration
                    if "destructuring" in node.type:
                        pass

                    # Regular property/variable
                    var_name = "unknown"
                    var_type = "Unknown"
                    
                    var_decl = None
                    for child in node.children:
                        if child.type == "variable_declaration":
                            var_decl = child
                            break
                    
                    if var_decl:
                        # Check for name and type in variable_declaration
                        for child in var_decl.children:
                            if child.type == "simple_identifier":
                                var_name = self._get_node_text(child)
                            
                            if child.type == "user_type":
                                var_type = self._get_node_text(child)

                    # Attempt inference from initializer if type is unknown
                    if var_type == "Unknown":
                        # property_declaration -> expression (e.g. call_expression)
                        for child in node.children:
                            if child.type == "call_expression":
                                # call_expression -> simple_identifier (constructor)
                                for sub in child.children:
                                    if sub.type == "simple_identifier":
                                        var_type = self._get_node_text(sub)
                                        break
                                if var_type != "Unknown": break

                    if var_name != "unknown":
                        variables.append({
                            "name": var_name,
                            "type": var_type,
                            "line_number": start_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": ctx_name,
                            "class_context": ctx_name if ctx_type and ("class" in ctx_type or "object" in ctx_type) else None
                        })
                except Exception as e:
                    continue

        return variables

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    # import_header -> "import" identifier (import_alias)?
                    text = self._get_node_text(node)
                    # remove 'import '
                    path = text.replace('import ', '').strip().split(' as ')[0].strip()
                    alias = None
                    if ' as ' in text:
                        alias = text.split(' as ')[1].strip()

                    imports.append({
                        "name": path,
                        "full_import_name": path,
                        "line_number": node.start_point[0] + 1,
                        "alias": alias,
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
        
        # Index variables for fast lookup: (name, context) -> type
        var_map = {}
        for v in variables:
            key = (v['name'], v['context'])
            var_map[key] = v['type']
            # Fallback for null context or partial match could be added
            # For class props: (name, class_context) might work if local lookup fails?

        for node, capture_name in captures:
            if capture_name == "call_node":
                try:
                    # navigation_expression check
                    
                    start_line = node.start_point[0] + 1
                    
                    call_name = "unknown"
                    base_obj = None
                    
                    # call_expression usually has children:
                    # simple_identifier (func name)
                    # or navigation_expression (obj.method)
                    
                    # Heuristic for base object:
                    # If navigation_expression -> child[0] is base, child[1] is suffix (method)
                    
                    # We need to look deeper into the call_expression structure.
                    # call_expression -> (simple_identifier)
                    # OR call_expression -> (navigation_expression (simple_identifier) (navigation_suffix (simple_identifier) ...))
                    # OR call_expression -> (navigation_expression (call_expression) ...)  (chained)

                    # Simplified traversal to find the "function name" and "receiver"
                    
                    # If it's a direct call: foo()
                    # If it's a method call: x.foo()
                    
                    # Tree-sitter struct:
                    # (call_expression (simple_identifier) (call_suffix ...))  -> name = simple_identifier
                    # (call_expression (navigation_expression (simple_identifier) (navigation_suffix (simple_identifier))) (call_suffix))
                    #  -> name = 2nd simple_identifier, base = 1st simple_identifier
                    
                    # Let's verify children
                    children = node.children
                    first_child = children[0]
                    
                    if first_child.type == "simple_identifier":
                        call_name = self._get_node_text(first_child)
                        # No explicit base object
                    elif first_child.type == "navigation_expression":
                        # x.foo
                        # children: operand (x), operator (.), suffix (foo)
                        # Usually 3 children?
                        # Let's inspect nav expression children
                        nav_children = first_child.children
                        if len(nav_children) >= 2:
                             # operand is 0
                             operand = nav_children[0]
                             # last one is suffix?
                             suffix = nav_children[-1]
                             
                             # Suffix usually contains the method name in a navigation_suffix node or directly?
                             # Suffix is (navigation_suffix (simple_identifier)) usually.
                             
                             if suffix.type == "navigation_suffix":
                                 # (navigation_suffix (simple_identifier))
                                 for c in suffix.children:
                                     if c.type == "simple_identifier":
                                         call_name = self._get_node_text(c)
                                         break
                             elif suffix.type == "simple_identifier":
                                 call_name = self._get_node_text(suffix)
                                 
                             # Base object
                             base_obj = self._get_node_text(operand)
                    
                    if call_name == "unknown":
                        continue
                        
                    full_name = f"{base_obj}.{call_name}" if base_obj else call_name
                    
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    
                    # Inference
                    inferred_type = None
                    if base_obj:
                        # Lookup base_obj in variables
                        # Try exact context
                        inferred_type = var_map.get((base_obj, ctx_name))
                        if not inferred_type:
                            # Try class context if we are in a method
                             # This logic is approximate.
                             # If we are in method 'foo' of 'ClassA', and 'base_obj' refers to a property of 'ClassA',
                             # var_map entry would have context 'ClassA'.
                             # But our 'variables' parsing puts context as 'ClassA' for props.
                             # But 'ctx_name' here is 'foo'.
                             # We need to know 'foo' is in 'ClassA'.
                             # 'get_parent_context' returns immediate parent.
                             pass
                             # Fallback: check global/file scope (context=None)
                             if not inferred_type:
                                 inferred_type = var_map.get((base_obj, None))
                             
                             # Fallback: check if any variable named base_obj exists (loose match)
                             if not inferred_type:
                                 for (vname, vctx), vtype in var_map.items():
                                     if vname == base_obj:
                                         inferred_type = vtype
                                         break


                    calls.append({
                        "name": call_name,
                        "full_name": full_name,
                        "line_number": start_line,
                        "args": [], # Simplified
                        "inferred_obj_type": inferred_type,
                        "context": [None, ctx_type, ctx_line], # Keeping format compatible
                        "class_context": [None, None],
                        "lang": self.language_name,
                        "is_dependency": False
                    })
                except Exception as e:
                    continue
        return calls

    def _extract_parameter_names(self, params_text: str) -> list[str]:
        """
        Extracts parameter names from a Kotlin parameter list string.
        Handles nested generics like Map<String, Int>.
        
        Args:
            params_text (str): The text content of function_value_parameters node, e.g. "(a: Int, b: Map<String, Int>)"
            
        Returns:
            list[str]: List of parameter names.
        """
        params = []
        if not params_text: return params
        
        # Remove outer parentheses
        clean = params_text.strip()
        if clean.startswith('(') and clean.endswith(')'):
            clean = clean[1:-1]
        
        if not clean.strip(): return params
        
        # Robust splitting by comma, respecting brackets <>, (), [], {}
        current_param = []
        depth_angle = 0 # < >
        depth_round = 0 # ( )
        depth_square = 0 # [ ]
        depth_curly = 0 # { }
        
        raw_params = []
        
        for char in clean:
            if char == '<': depth_angle += 1
            elif char == '>': depth_angle -= 1
            elif char == '(': depth_round += 1
            elif char == ')': depth_round -= 1
            elif char == '[': depth_square += 1
            elif char == ']': depth_square -= 1
            elif char == '{': depth_curly += 1
            elif char == '}': depth_curly -= 1
            
            if char == ',' and depth_angle == 0 and depth_round == 0 and depth_square == 0 and depth_curly == 0:
                raw_params.append("".join(current_param).strip())
                current_param = []
            else:
                current_param.append(char)
                
        if current_param:
            raw_params.append("".join(current_param).strip())
            
        # Process each raw parameter string to extract name
        # Format: "val x: Int", "override var y: String", "@Ann z: Int", "a: Int = 5"
        for p in raw_params:
            if not p: continue
            
            # Remove default value if present
            # Be careful with '=' inside strings or generic defaults, but usually param defaults are at top level
            # A simple split by '=' might be risky if default value has '=', but for name extraction it's usually safe
            # as the name is on the LHS.
            # But wait, "val x: Type = ..." -> name is before ':'
            
            # Split by ':' to separate name/modifiers from Type
            # Using the first ':' usually works, assuming name doesn't contain ':'
            colon_index = p.find(':')
            if colon_index != -1:
                lhs = p[:colon_index].strip()
            else:
                # Could be a parameter without type? (not common in Kotlin unless lambda destructuring)
                # Or "var x = 5" (unlikely in func params)
                # Just take the whole string if no colon?
                lhs = p.strip()
                
            # LHS contains keywords (val, var), annotations (@Foo), modifiers (crossinline, noinline, vararg)
            # and the parameter name. The parameter name is usually the LAST identifier.
            
            if not lhs: continue
            
            tokens = lhs.split()
            if tokens:
                # The name is the last token
                params.append(tokens[-1])
                
        return params

def pre_scan_kotlin(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 1. Extract package
            # package com.example.project
            package_name = ""
            pkg_match = re.search(r'^\s*package\s+([\w\.]+)', content, re.MULTILINE)
            if pkg_match:
                package_name = pkg_match.group(1)
            
            # 2. Extract classes/objects/interfaces/typealiases
            matches = re.finditer(r'\b(class|interface|object|typealias)\s+(\w+)', content)
            
            for match in matches:
                name = match.group(2)
                # Map simple name
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(str(path))
                
                # If package exists, map FQN
                if package_name:
                    fqn = f"{package_name}.{name}"
                    if fqn not in name_to_files:
                        name_to_files[fqn] = []
                    name_to_files[fqn].append(str(path))
                    
        except Exception:
            pass
    return name_to_files
