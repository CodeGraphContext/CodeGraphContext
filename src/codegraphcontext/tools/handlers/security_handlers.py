import re
from typing import Dict, Any, List
from ...utils.debug_log import debug_log


SECRET_PATTERNS = {
    "api_key": r'(?i)(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']',
    "aws_access_key": r'(?i)(aws[_-]?access[_-]?key[_-]?id)["\']?\s*[:=]\s*["\']([A-Z0-9]{20})["\']',
    "aws_secret": r'(?i)(aws[_-]?secret[_-]?access[_-]?key)["\']?\s*[:=]\s*["\']([a-zA-Z0-9/+=]{40})["\']',
    "password": r'(?i)(password|passwd)["\']?\s*[:=]\s*["\']([^\s"\']{6,})["\']',
    "token": r'(?i)(token|bearer)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-\.]{20,})["\']',
    "private_key": r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
    "database_url": r'(?i)(database[_-]?url|db[_-]?url)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]+://[^\s"\']+)["\']',
}


VULNERABILITY_PATTERNS = {
    "sql_injection": r'(?i)(execute|executemany|cursor\.execute)\s*\(\s*["\'][^"\']*\+[^"\']*["\']',
    "hardcoded_credentials": r'(?i)(username|password|api_key|secret)\s*=\s*["\'][^"\']{4,}["\']',
    "insecure_deserialization": r"(?i)(pickle\.loads|cPickle\.loads|marshal\.loads)\s*\(",
    "eval_usage": r"(?i)\beval\s*\(",
    "shell_injection": r"(?i)(os\.system|subprocess\.(call|run|Popen))\s*\(\s*[^)]*\+",
    "weak_crypto": r"(?i)(md5|sha1)\.new\s*\(",
    "temp_file_race": r"(?i)(tempfile\.mktemp|os\.mktemp)\s*\(",
    "unverified_ssl": r"(?i)ssl\._create_unverified_context|verify\s*=\s*False",
}


def scan_security_vulnerabilities(code_finder, **args) -> Dict[str, Any]:
    """Scan the codebase for security vulnerabilities."""
    repo_path = args.get("repo_path")
    scan_type = args.get("scan_type", "all")

    try:
        vulnerabilities = []
        secrets = []

        if scan_type in ["all", "secrets"]:
            secrets = _scan_for_secrets(code_finder, repo_path)

        if scan_type in ["all", "vulnerabilities"]:
            vulnerabilities = _scan_for_vulnerabilities(code_finder, repo_path)

        result = {
            "success": True,
            "scan_type": scan_type,
            "secrets_found": len(secrets),
            "vulnerabilities_found": len(vulnerabilities),
            "secrets": secrets[:50] if secrets else [],
            "vulnerabilities": vulnerabilities[:50] if vulnerabilities else [],
        }

        debug_log(
            f"Security scan completed: {len(secrets)} secrets, {len(vulnerabilities)} vulnerabilities"
        )

        return result

    except Exception as e:
        debug_log(f"Error during security scan: {str(e)}")
        return {"error": f"Failed to scan for security vulnerabilities: {str(e)}"}


def _scan_for_secrets(code_finder, repo_path: str) -> List[Dict[str, Any]]:
    """Scan for hardcoded secrets in the codebase."""
    secrets = []

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

                for secret_type, pattern in SECRET_PATTERNS.items():
                    matches = re.finditer(pattern, source)
                    for match in matches:
                        line_num = source[: match.start()].count("\n") + 1
                        secrets.append(
                            {
                                "type": secret_type,
                                "file": file_path,
                                "line": line_num,
                                "match": match.group(0)[:100]
                                if len(match.group(0)) > 100
                                else match.group(0),
                            }
                        )

    except Exception as e:
        debug_log(f"Error scanning for secrets: {str(e)}")

    return secrets


def _scan_for_vulnerabilities(code_finder, repo_path: str) -> List[Dict[str, Any]]:
    """Scan for code vulnerabilities."""
    vulnerabilities = []

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

                for vuln_type, pattern in VULNERABILITY_PATTERNS.items():
                    matches = re.finditer(pattern, source)
                    for match in matches:
                        line_num = source[: match.start()].count("\n") + 1
                        vulnerabilities.append(
                            {
                                "type": vuln_type,
                                "severity": _get_severity(vuln_type),
                                "file": file_path,
                                "line": line_num,
                                "match": match.group(0)[:100]
                                if len(match.group(0)) > 100
                                else match.group(0),
                            }
                        )

    except Exception as e:
        debug_log(f"Error scanning for vulnerabilities: {str(e)}")

    return vulnerabilities


def _get_severity(vuln_type: str) -> str:
    """Get severity level for a vulnerability type."""
    high_severity = [
        "sql_injection",
        "hardcoded_credentials",
        "insecure_deserialization",
        "shell_injection",
    ]
    medium_severity = ["eval_usage", "weak_crypto", "unverified_ssl"]

    if vuln_type in high_severity:
        return "high"
    elif vuln_type in medium_severity:
        return "medium"
    else:
        return "low"


def scan_dependencies(code_finder, **args) -> Dict[str, Any]:
    """Scan project dependencies for known vulnerabilities."""
    repo_path = args.get("repo_path")
    language = args.get("language", "python")

    try:
        vulnerable_packages = _check_vulnerable_dependencies(
            code_finder, repo_path, language
        )

        result = {
            "success": True,
            "language": language,
            "vulnerable_packages_found": len(vulnerable_packages),
            "packages": vulnerable_packages,
        }

        debug_log(
            f"Dependency scan completed: {len(vulnerable_packages)} vulnerable packages"
        )

        return result

    except Exception as e:
        debug_log(f"Error during dependency scan: {str(e)}")
        return {"error": f"Failed to scan dependencies: {str(e)}"}


def _check_vulnerable_dependencies(
    code_finder, repo_path: str, language: str
) -> List[Dict[str, Any]]:
    """Check for known vulnerable dependencies."""
    vulnerable_packages = []

    known_vulnerabilities = {
        "python": {
            "requests": {"below_version": "2.32.0", "cve": "CVE-2023-32681"},
            "flask": {"below_version": "2.3.0", "cve": "CVE-2023-30861"},
            "jinja2": {"below_version": "3.1.2", "cve": "CVE-2021-42519"},
        },
        "javascript": {
            "axios": {"below_version": "1.6.0", "cve": "CVE-2023-45857"},
            "express": {"below_version": "4.18.2", "cve": "CVE-2022-24999"},
        },
    }

    lang_vulns = known_vulnerabilities.get(language, {})

    query = """
    MATCH (f:File)
    WHERE f.path CONTAINS 'requirements.txt' OR f.path CONTAINS 'package.json'
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

                for package, vuln_info in lang_vulns.items():
                    if package in source.lower():
                        vulnerable_packages.append(
                            {
                                "package": package,
                                "file": file_path,
                                "cve": vuln_info["cve"],
                                "recommended_version": vuln_info["below_version"],
                                "severity": "high",
                            }
                        )

    except Exception as e:
        debug_log(f"Error checking vulnerable dependencies: {str(e)}")

    return vulnerable_packages
