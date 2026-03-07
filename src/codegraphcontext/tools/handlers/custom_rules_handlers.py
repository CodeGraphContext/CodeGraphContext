import re
import json
import os
from typing import Dict, Any, List
from pathlib import Path
from ...utils.debug_log import debug_log


CUSTOM_RULES_FILE = os.path.join(
    os.path.expanduser("~"), ".codegraphcontext", "custom_rules.json"
)


def _load_custom_rules() -> List[Dict[str, Any]]:
    """Load custom rules from file."""
    rules = []

    try:
        rules_path = Path(CUSTOM_RULES_FILE)
        if rules_path.exists():
            with open(rules_path, "r") as f:
                rules = json.load(f)
    except Exception as e:
        debug_log(f"Error loading custom rules: {str(e)}")

    return rules


def _save_custom_rules(rules: List[Dict[str, Any]]) -> bool:
    """Save custom rules to file."""
    try:
        rules_path = Path(CUSTOM_RULES_FILE)
        rules_path.parent.mkdir(parents=True, exist_ok=True)

        with open(rules_path, "w") as f:
            json.dump(rules, f, indent=2)

        return True
    except Exception as e:
        debug_log(f"Error saving custom rules: {str(e)}")
        return False


def define_custom_rule(**args) -> Dict[str, Any]:
    """Define a custom linting rule for code analysis."""
    rule_name = args.get("rule_name")
    pattern = args.get("pattern")
    severity = args.get("severity", "warning")
    description = args.get("description", "")

    if not rule_name or not pattern:
        return {"error": "Rule name and pattern are required"}

    if severity not in ["error", "warning", "info"]:
        return {"error": "Severity must be one of: error, warning, info"}

    try:
        re.compile(pattern)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {str(e)}"}

    rules = _load_custom_rules()

    existing_rule = next((r for r in rules if r["name"] == rule_name), None)
    if existing_rule:
        existing_rule.update(
            {"pattern": pattern, "severity": severity, "description": description}
        )
    else:
        rules.append(
            {
                "name": rule_name,
                "pattern": pattern,
                "severity": severity,
                "description": description,
            }
        )

    if _save_custom_rules(rules):
        debug_log(f"Custom rule defined: {rule_name}")
        return {
            "success": True,
            "rule": {
                "name": rule_name,
                "pattern": pattern,
                "severity": severity,
                "description": description,
            },
            "message": f"Custom rule '{rule_name}' has been defined",
        }
    else:
        return {"error": "Failed to save custom rule"}


def list_custom_rules(**args) -> Dict[str, Any]:
    """List all defined custom linting rules."""
    rules = _load_custom_rules()

    return {"success": True, "rules_count": len(rules), "rules": rules}


def apply_custom_rules(code_finder, **args) -> Dict[str, Any]:
    """Apply custom linting rules to the codebase and report violations."""
    repo_path = args.get("repo_path")
    rule_names = args.get("rule_names")

    rules = _load_custom_rules()

    if not rules:
        return {"success": True, "violations": [], "message": "No custom rules defined"}

    if rule_names:
        rules = [r for r in rules if r["name"] in rule_names]

    if not rules:
        return {"error": "No matching custom rules found"}

    try:
        violations = _apply_rules_to_codebase(code_finder, rules, repo_path)

        result = {
            "success": True,
            "rules_applied": len(rules),
            "violations_found": len(violations),
            "violations": violations[:100],
        }

        debug_log(
            f"Applied {len(rules)} custom rules: {len(violations)} violations found"
        )

        return result

    except Exception as e:
        debug_log(f"Error applying custom rules: {str(e)}")
        return {"error": f"Failed to apply custom rules: {str(e)}"}


def _apply_rules_to_codebase(
    code_finder, rules: List[Dict[str, Any]], repo_path: str = None
) -> List[Dict[str, Any]]:
    """Apply custom rules to the codebase."""
    violations = []

    query = """
    MATCH (f:File)
    WHERE f.source IS NOT NULL AND f.source <> ''
    RETURN f.path, f.source
    """

    try:
        results = code_finder.execute_cypher_query(query)

        if results.get("success"):
            for record in results.get("results", []):
                file_path = record.get("f.path", "")
                source = record.get("f.source", "")

                if repo_path and repo_path not in file_path:
                    continue

                for rule in rules:
                    pattern = rule.get("pattern")
                    rule_name = rule.get("name")
                    severity = rule.get("severity")

                    try:
                        matches = re.finditer(pattern, source)
                        for match in matches:
                            line_num = source[: match.start()].count("\n") + 1
                            violations.append(
                                {
                                    "rule": rule_name,
                                    "severity": severity,
                                    "file": file_path,
                                    "line": line_num,
                                    "match": match.group(0)[:200]
                                    if len(match.group(0)) > 200
                                    else match.group(0),
                                    "description": rule.get("description", ""),
                                }
                            )
                    except re.error:
                        debug_log(f"Invalid regex pattern in rule: {rule_name}")

    except Exception as e:
        debug_log(f"Error applying rules to codebase: {str(e)}")

    return violations


def delete_custom_rule(**args) -> Dict[str, Any]:
    """Delete a custom rule by name."""
    rule_name = args.get("rule_name")

    if not rule_name:
        return {"error": "Rule name is required"}

    rules = _load_custom_rules()

    original_count = len(rules)
    rules = [r for r in rules if r["name"] != rule_name]

    if len(rules) == original_count:
        return {"error": f"Rule '{rule_name}' not found"}

    if _save_custom_rules(rules):
        debug_log(f"Custom rule deleted: {rule_name}")
        return {
            "success": True,
            "message": f"Custom rule '{rule_name}' has been deleted",
        }
    else:
        return {"error": "Failed to delete custom rule"}


def share_custom_rules(**args) -> Dict[str, Any]:
    """Export custom rules as JSON for sharing."""
    rules = _load_custom_rules()

    if not rules:
        return {"error": "No custom rules to share"}

    return {"success": True, "rules": rules, "export_format": "json"}


def import_custom_rules(**args) -> Dict[str, Any]:
    """Import custom rules from JSON."""
    rules_data = args.get("rules")

    if not rules_data:
        return {"error": "Rules data is required"}

    try:
        if isinstance(rules_data, str):
            imported_rules = json.loads(rules_data)
        else:
            imported_rules = rules_data

        if not isinstance(imported_rules, list):
            return {"error": "Rules must be a list of rule objects"}

        existing_rules = _load_custom_rules()

        imported_count = 0
        for rule in imported_rules:
            if not isinstance(rule, dict):
                continue

            if "name" not in rule or "pattern" not in rule:
                continue

            existing_rule = next(
                (r for r in existing_rules if r["name"] == rule["name"]), None
            )
            if existing_rule:
                continue

            existing_rules.append(
                {
                    "name": rule.get("name"),
                    "pattern": rule.get("pattern"),
                    "severity": rule.get("severity", "warning"),
                    "description": rule.get("description", ""),
                }
            )
            imported_count += 1

        if _save_custom_rules(existing_rules):
            debug_log(f"Imported {imported_count} custom rules")
            return {
                "success": True,
                "imported_count": imported_count,
                "message": f"Successfully imported {imported_count} custom rules",
            }
        else:
            return {"error": "Failed to save imported rules"}

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON format: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to import rules: {str(e)}"}
