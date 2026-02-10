#!/usr/bin/env python3
"""
Script to update all language parsers to use the new tree-sitter 0.25+ API.

This script:
1. Adds import for execute_query
2. Removes query dictionary initialization
3. Replaces query.captures() with execute_query()
"""

import re
from pathlib import Path

# Language files to update
LANGUAGE_FILES = [
    "javascript.py",
    "typescript.py",
    "go.py",
    "rust.py",
    "c.py",
    "cpp.py",
    "java.py",
    "ruby.py",
    "csharp.py",
]

LANGUAGES_DIR = Path(__file__).resolve().parent.parent / "src" / "codegraphcontext" / "tools" / "languages"


def update_imports(content: str) -> str:
    """Add execute_query import if not present."""
    if "from codegraphcontext.utils.tree_sitter_manager import execute_query" in content:
        return content
    
    # Find the last import statement
    import_pattern = r"(from codegraphcontext\.utils\.debug_log import[^\n]+)"
    match = re.search(import_pattern, content)
    
    if match:
        # Add our import after the debug_log import
        new_import = match.group(1) + "\nfrom codegraphcontext.utils.tree_sitter_manager import execute_query"
        content = content.replace(match.group(1), new_import)
    
    return content


def remove_query_dict_init(content: str) -> str:
    """Remove self.queries dictionary initialization."""
    # Pattern to match the queries dictionary initialization
    pattern = r"\s+self\.queries\s*=\s*\{[^}]+\}\s*"
    content = re.sub(pattern, "\n", content, flags=re.DOTALL)
    return content


def replace_query_usage(content: str, query_dict_name: str) -> str:
    """Replace query.captures() with execute_query()."""
    
    # Pattern 1: self.queries.get('name') or self.queries['name']
    # Replace: query = self.queries.get('lambda_assignments')
    # With: query_str = LANG_QUERIES.get('lambda_assignments')
    content = re.sub(
        r"query\s*=\s*self\.queries\.get\('([^']+)'\)",
        r"query_str = " + query_dict_name + ".get('\\1')",
        content
    )
    content = re.sub(
        r"query\s*=\s*self\.queries\['([^']+)'\]",
        r"query_str = " + query_dict_name + "['\\1']",
        content
    )
    
    # Pattern 2: if not query: return []
    # Replace with: if not query_str: return []
    content = content.replace("if not query:", "if not query_str:")
    
    # Pattern 3: query.captures(node)
    # Replace with: execute_query(self.language, query_str, node)
    content = re.sub(
        r"query\.captures\(([^)]+)\)",
        r"execute_query(self.language, query_str, \1)",
        content
    )
    
    # Pattern 4: In pre_scan functions, replace parser_wrapper.language.query(query_str)
    content = re.sub(
        r"query\s*=\s*parser_wrapper\.language\.query\(query_str\)",
        "",
        content
    )
    
    # Pattern 5: In pre_scan functions, replace query.captures with execute_query
    content = re.sub(
        r"for\s+([^,]+),\s+([^)]+)\s+in\s+query\.captures\(tree\.root_node\):",
        r"for \1, \2 in execute_query(parser_wrapper.language, query_str, tree.root_node):",
        content
    )
    content = re.sub(
        r"for\s+([^,]+),\s+([^)]+)\s+in\s+query\.captures\(([^)]+)\):",
        r"for \1, \2 in execute_query(parser_wrapper.language, query_str, \3):",
        content
    )
    
    return content


def get_query_dict_name(content: str) -> str:
    """Detect the query dictionary name (e.g., PY_QUERIES, JS_QUERIES, etc.)."""
    match = re.search(r"([A-Z_]+QUERIES)\s*=\s*\{", content)
    if match:
        return match.group(1)
    return "QUERIES"


def update_language_file(path: Path):
    """Update a single language file."""
    print(f"Updating {path.name}...")
    
    content = path.read_text()
    original_content = content
    
    # Detect query dictionary name
    query_dict_name = get_query_dict_name(content)
    print(f"  Query dict name: {query_dict_name}")
    
    # Apply transformations
    content = update_imports(content)
    content = remove_query_dict_init(content)
    content = replace_query_usage(content, query_dict_name)
    
    # Write back if changed
    if content != original_content:
        path.write_text(content)
        print(f"  ✓ Updated {path.name}")
    else:
        print(f"  - No changes needed for {path.name}")


def main():
    """Update all language parser files."""
    print("Updating language parsers for tree-sitter 0.25+ compatibility\n")
    
    for lang_file in LANGUAGE_FILES:
        path = LANGUAGES_DIR / lang_file
        if path.exists():
            try:
                update_language_file(path)
            except Exception as e:
                print(f"  ✗ Error updating {lang_file}: {e}")
        else:
            print(f"  ✗ File not found: {lang_file}")
    
    print("\n✓ All language parsers updated!")


if __name__ == "__main__":
    main()
