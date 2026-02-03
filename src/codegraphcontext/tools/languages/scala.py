from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

SCALA_QUERIES = {
    "functions": """
        (function_definition
            name: (identifier) @name
            parameters: (parameters) @params
        ) @function_node
    """,
    "classes": """
        [
            (class_definition name: (identifier) @name)
            (object_definition name: (identifier) @name)
            (trait_definition name: (identifier) @name)
        ] @class
    """,
    "imports": """
        (import_declaration) @import
    """,
    "calls": """
        (call_expression) @call_node
        (generic_function
             function: (identifier) @name
        ) @call_node
    """,
    "variables": """
        (val_definition
            pattern: (identifier) @name
        ) @variable
        
        (var_definition
            pattern: (identifier) @name
        ) @variable
    """,
}

class ScalaTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "scala"
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

            # Parse variables first for inference
            if "variables" in SCALA_QUERIES:
                 try:
                     results = execute_query(self.language, SCALA_QUERIES["variables"], tree.root_node)
                     parsed_variables.extend(self._parse_variables(results, source_code, path))
                 except Exception as e:
                     error_logger(f"Error parsing Scala variables in {path}: {e}")

            for capture_name, query in SCALA_QUERIES.items():
                if capture_name == "variables": continue 
                
                try:
                    results = execute_query(self.language, query, tree.root_node)

                    if capture_name == "functions":
                        parsed_functions.extend(self._parse_functions(results, source_code, path))
                    elif capture_name == "classes":
                        parsed_classes.extend(self._parse_classes(results, source_code, path))
                    elif capture_name == "imports":
                        parsed_imports.extend(self._parse_imports(results, source_code))
                    elif capture_name == "calls":
                        parsed_calls.extend(self._parse_calls(results, source_code, path, parsed_variables))
                except Exception as e:
                    # Some queries might fail if the grammar differs slightly, catch and log
                    error_logger(f"Error executing Scala query '{capture_name}' in {path}: {e}")

            # Separate classes, traits, objects
            final_classes = []
            final_traits = []
            
            for item in parsed_classes:
                item_type = item.get('type', 'class')
                if item_type == 'trait':
                     final_traits.append(item)
                elif item_type == 'object':
                     item['is_object'] = True
                     final_classes.append(item)
                else:
                     final_classes.append(item)

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": final_classes,
                "traits": final_traits,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

        except Exception as e:
            error_logger(f"Error parsing Scala file {path}: {e}")
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
            if curr.type == "function_definition":
                name_node = curr.child_by_field_name("name")
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            if curr.type in ("class_definition", "object_definition", "trait_definition"):
                name_node = curr.child_by_field_name("name")
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    def _parse_functions(self, captures: list, source_code: str, path: Path) -> List[Dict[str, Any]]:
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
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        func_name = self._get_node_text(name_node)
                        
                        params_node = node.child_by_field_name("parameters")
                        parameters = []
                        if params_node:
                            params_text = self._get_node_text(params_node)
                            parameters = self._extract_parameter_names(params_text)

                        source_text = self._get_node_text(node)
                        
                        context_name, context_type, context_line = self._get_parent_context(node)

                        func_data = {
                            "name": func_name,
                            "parameters": parameters,
                            "args": parameters, # 'args' is sometimes used instead of 'parameters'
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": context_name,
                            "class_context": context_name if context_type and "class" in str(context_type) or "object" in str(context_type) or "trait" in str(context_type) else None
                        }

                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path) -> List[Dict[str, Any]]:
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
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_name = self._get_node_text(name_node)
                        source_text = self._get_node_text(node)
                        
                        bases = []
                        # Look for extends clause (extends_clause)
                        # class_definition -> extends_clause -> template_body
                        extends_clause = None
                        for child in node.children:
                            if child.type == "extends_clause": # Might vary by grammar version: 'extends' keyword + types
                                extends_clause = child
                                break
                        
                        if extends_clause:
                             for child in extends_clause.children:
                                 if child.type == "type_identifier" or child.type == "user_type": # specific to scala grammar
                                     bases.append(self._get_node_text(child))
                                 elif child.type == "template_invocation":
                                      # template_invocation -> user_type
                                      pass 

                        # Note: parsing bases in Scala can be complex (mixins with 'with' keyword).
                        # Using text based regex backup might be safer for now if tree query is hard.
                        
                        class_data = {
                            "name": class_name,
                            "line_number": start_line,
                            "end_line": end_line,
                            "bases": bases,
                            "path": str(path),
                            "lang": self.language_name,
                            "type": node.type.replace("_definition", "") # class, object, trait
                        }

                        if self.index_source:
                            class_data["source"] = source_text
                        
                        classes.append(class_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing class in {path}: {e}")
                    continue

        return classes

    def _parse_variables(self, captures: list, source_code: str, path: Path) -> List[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name == "variable":
                # The capture is on the whole definition (val/var_definition)
                # But we have @name on the identifier inside pattern.
                pass
            if capture_name == "name":
                # Check parent context
                if node.parent.type in ("val_definition", "var_definition"):
                     definition = node.parent
                     var_name = self._get_node_text(node)
                     start_line = node.start_point[0] + 1
                     
                     start_byte = node.start_byte
                     if start_byte in seen_vars:
                         continue
                     seen_vars.add(start_byte)
                     
                     ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                     
                     # Type extraction: look for type_identifier in definition
                     var_type = "Unknown"
                     type_node = definition.child_by_field_name("type")
                     if type_node:
                         var_type = self._get_node_text(type_node)
                     else:
                         # Attempt inference from value
                         val_node = definition.child_by_field_name("value")
                         if val_node:
                             if val_node.type == "instance_expression" or val_node.type == "new_expression":
                                 # new Calculator() 
                                 # instance_expression -> new, type_identifier, arguments
                                 for child in val_node.children:
                                     if child.type in ("type_identifier", "simple_type", "user_type", "generic_type"):
                                         var_type = self._get_node_text(child)
                                         break
                                     elif child.type == "template_call": # sometimes nested
                                          for sub in child.children:
                                              if sub.type in ("type_identifier", "simple_type", "user_type"):
                                                  var_type = self._get_node_text(sub)
                                                  break
                             elif val_node.type == "call_expression":
                                 # Circle(5.0)
                                 # wrapper -> function(identifier)
                                 func = val_node.child_by_field_name("function")
                                 if func:
                                     var_type = self._get_node_text(func)
                                     
                     variables.append({
                        "name": var_name,
                        "type": var_type,
                        "line_number": start_line,
                        "path": str(path),
                        "lang": self.language_name,
                        "context": ctx_name,
                        "class_context": ctx_name if ctx_type and ("class" in str(ctx_type) or "object" in str(ctx_type)) else None
                     })

        return variables

    def _parse_imports(self, captures: list, source_code: str) -> List[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    # Scala imports can be complex: import java.util.{Date, List} or import java.util._
                    # We will try to extract the base path.
                    import_text = self._get_node_text(node)
                    # Simple heuristic: remove 'import ' and handle one level
                    clean_text = import_text.replace("import ", "").strip()
                    
                    # Split logic for multiple imports in one line not handled perfectly here yet
                    # Just storing the whole text as name for now is better than crashing
                    
                    path = clean_text
                    
                    imports.append({
                        "name": path,
                        "full_import_name": path,
                        "line_number": node.start_point[0] + 1,
                        "alias": None,
                        "context": (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    })
                except Exception as e:
                    error_logger(f"Error parsing import: {e}")
                    continue

        return imports

    def _parse_calls(self, captures: list, source_code: str, path: Path, variables: List[Dict] = []) -> List[Dict]:
        calls = []
        seen_calls = set()
        
        for node, capture_name in captures:
            if capture_name == "call_node":
                try:
                    start_line = node.start_point[0] + 1
                    
                    # Heuristic to find name
                    call_name = "unknown"
                    full_name = "unknown"
                    
                    if node.type == "call_expression":
                         # function (child 0) arguments (child 1)
                         func_node = node.child_by_field_name("function")
                         if func_node:
                             if func_node.type == "field_expression": # obj.method
                                 call_name = self._get_node_text(func_node.child_by_field_name("field")) # or name?
                                 full_name = self._get_node_text(func_node)
                             elif func_node.type == "identifier":
                                 call_name = self._get_node_text(func_node)
                                 full_name = call_name
                             elif func_node.type == "generic_function":
                                 # generic_function -> function
                                 inner = func_node.child_by_field_name("function")
                                 if inner:
                                     full_name = self._get_node_text(inner)
                                     call_name = full_name # simplified

                    if call_name == "unknown":
                         # Falback to text if simple
                         # call_name = self._get_node_text(node).split('(')[0]
                         continue

                    # Avoid duplicates
                    call_key = f"{call_name}_{start_line}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)
                    
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                    # Inference from variables
                    inferred_type = None
                    if "." in full_name:
                        base_obj = full_name.split(".")[0]
                        # search for base_obj in variables
                        # Prefer variables in local context (ctx_name)
                        
                        # Simple search: exact name match in same file
                        # We could improve by checking scope/context, but for now filtering by name is a good start
                        candidate = None
                        for v in variables:
                            if v["name"] == base_obj:
                                # Check if context matches or is strictly enclosing? 
                                # For now, just take the first match or last match? 
                                # Usually last match (closest definition)
                                candidate = v
                                if v["context"] == ctx_name:
                                    break
                        
                        if candidate:
                            inferred_type = candidate["type"]
                    elif call_name in variables: # Usually not happening as variables is list of dicts
                         pass

                    calls.append({
                        "name": call_name,
                        "full_name": full_name,
                        "line_number": start_line,
                        "args": [],
                        "inferred_obj_type": inferred_type,
                        "context": (ctx_name, ctx_type, ctx_line),
                        "class_context": (ctx_name, ctx_line) if ctx_type and ("class" in str(ctx_type) or "object" in str(ctx_type)) else (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    })
                except Exception as e:
                    error_logger(f"Error parsing call: {e}")
                    continue

        return calls
    

    def _extract_parameter_names(self, params_text: str) -> List[str]:
        # Simple extraction for Scala: (a: Int, b: String)
        params = []
        if not params_text: return params
        clean = params_text.strip("()")
        if not clean: return params
        
        # Split by comma, respecting generics []
        # Scala generics use []
        
        # TODO: Reuse regex/parsing logic from other parsers or write simple one
        # For now, simplistic split
        parts = clean.split(',')
        for p in parts:
            # removing type: 'name: Type'
            if ':' in p:
                name = p.split(':')[0].strip()
                # Remove modifiers like 'implicit', 'override', etc.
                tokens = name.split()
                if tokens:
                    params.append(tokens[-1])
            else:
                 # maybe just name?
                 params.append(p.strip())
        return params


def pre_scan_scala(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # package matches
            package_name = ""
            pkg_match = re.search(r'^\s*package\s+([\w\.]+)', content, re.MULTILINE)
            if pkg_match:
                package_name = pkg_match.group(1)
            
            # class/object/trait matches
            class_matches = re.finditer(r'\b(class|object|trait)\s+(\w+)', content)
            for match in class_matches:
                name = match.group(2)
                type_ = match.group(1)
                
                # Simple mapping
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(str(path))
                
                # FQN mapping
                if package_name:
                    fqn = f"{package_name}.{name}"
                    if fqn not in name_to_files:
                        name_to_files[fqn] = []
                    name_to_files[fqn].append(str(path))
                
        except Exception as e:
            error_logger(f"Error pre-scanning Scala file {path}: {e}")
            
    return name_to_files
