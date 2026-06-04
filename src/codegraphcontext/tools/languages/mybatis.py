# src/codegraphcontext/tools/languages/mybatis.py
"""MyBatis XML mapper parser — extracts READS/WRITES operations from *Mapper.xml files.

Each mapper file has the form:
    <mapper namespace="com.example.FooMapper">
        <select id="findAll">SELECT ... FROM foo_table ...</select>
        <insert id="insert">INSERT INTO foo_table ...</insert>
        <update id="update">UPDATE foo_table ...</update>
        <delete id="delete">DELETE FROM foo_table ...</delete>
    </mapper>

The ``id`` attribute matches the Java interface method name.
Table names are extracted from the SQL text; when SQL is absent the mapper
class name is converted to a snake_case table name as a heuristic
(e.g. ``MailHistoryMapper`` → ``mail_history``).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from codegraphcontext.utils.debug_log import error_logger, info_logger

# Tags that represent write operations
_WRITE_TAGS = frozenset({"insert", "update", "delete"})
_READ_TAGS = frozenset({"select"})
_ALL_OP_TAGS = _WRITE_TAGS | _READ_TAGS


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case (e.g. MailHistory → mail_history)."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _class_name_to_table(class_name: str) -> Optional[str]:
    """Derive a table name heuristic from a mapper class name.

    ``MailHistoryMapper`` → ``mail_history``
    ``UserMapper`` → ``user``
    Returns *None* when the input is empty or only ``Mapper``.
    """
    stem = re.sub(r"Mapper$", "", class_name).strip()
    if not stem:
        return None
    return _camel_to_snake(stem)


def _extract_sql(element: ET.Element) -> str:
    """Return the concatenated text content of an XML element (handles CDATA)."""
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    if element.tail:
        parts.append(element.tail)
    return " ".join(parts)


def _parse_sql_tables(sql: str) -> List[str]:
    """Extract table names from a SQL string (best-effort, no full parser)."""
    sql_upper = sql.upper()
    tables: List[str] = []
    for kw in ("FROM", "JOIN", "INTO", "UPDATE", "TABLE"):
        for m in re.finditer(rf"\b{kw}\s+[`'\"]?([\w.]+)[`'\"]?", sql_upper):
            raw = m.group(1)
            # Strip schema prefix: schema.table → table
            tables.append(raw.split(".")[-1].lower())
    # Deduplicate, preserving order
    seen: set = set()
    result: List[str] = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def parse_mybatis_mapper(file_path: Path) -> List[Dict[str, Any]]:
    """Parse a single MyBatis XML mapper file and return operation records.

    Each record has:
        method_name  – Java interface method name (= XML ``id`` attribute)
        class_name   – Short name of the mapper interface (e.g. ``MailHistoryMapper``)
        db_tables    – List of table names touched
        operation    – ``"READS"`` or ``"WRITES"``
        mapper_path  – Absolute path of the XML file (for diagnostics)
    """
    records: List[Dict[str, Any]] = []
    try:
        tree = ET.parse(str(file_path))
        root = tree.getroot()

        # Root must be <mapper namespace="...">
        if root.tag != "mapper":
            return records

        namespace = root.get("namespace", "")
        # class_name = last segment of the namespace FQCN
        class_name = namespace.split(".")[-1] if namespace else file_path.stem

        for child in root:
            tag = child.tag.lower() if child.tag else ""
            if tag not in _ALL_OP_TAGS:
                continue

            method_id = child.get("id", "")
            if not method_id:
                continue

            operation = "READS" if tag in _READ_TAGS else "WRITES"

            sql_text = _extract_sql(child)
            tables = _parse_sql_tables(sql_text)

            # Fallback: infer table from mapper class name
            if not tables:
                inferred = _class_name_to_table(class_name)
                if inferred:
                    tables = [inferred]

            if not tables:
                # Still nothing — skip (no useful edge to write)
                continue

            records.append({
                "method_name": method_id,
                "class_name": class_name,
                "db_tables": tables,
                "operation": operation,
                "mapper_path": str(file_path),
            })

    except ET.ParseError as e:
        error_logger(f"[MYBATIS] XML parse error in {file_path}: {e}")
    except Exception as e:
        error_logger(f"[MYBATIS] Error parsing {file_path}: {e}")

    return records


def find_and_parse_mybatis_mappers(repo_path: Path) -> List[Dict[str, Any]]:
    """Walk *repo_path* for MyBatis mapper XML files and return all operation records.

    A file is treated as a mapper when it matches ``*Mapper.xml`` *or* when its
    root element is ``<mapper>``.  Target directories (``target/``, ``build/``,
    ``out/``) are skipped to avoid duplicates from compiled artefacts.
    """
    skip_dirs = {"target", "build", "out", ".git", "node_modules", "__pycache__"}
    all_records: List[Dict[str, Any]] = []
    file_count = 0

    for xml_file in repo_path.rglob("*.xml"):
        # Skip build output directories
        if any(part in skip_dirs for part in xml_file.parts):
            continue

        is_mapper_by_name = xml_file.name.endswith("Mapper.xml")

        if not is_mapper_by_name:
            # Quick pre-screen: check for '<mapper' in first 512 bytes
            try:
                with open(xml_file, "rb") as fh:
                    header = fh.read(512).decode("utf-8", errors="ignore")
                if "<mapper" not in header:
                    continue
            except Exception:
                continue

        records = parse_mybatis_mapper(xml_file)
        if records:
            all_records.extend(records)
            file_count += 1

    info_logger(
        f"[MYBATIS] Parsed {file_count} mapper files, "
        f"{len(all_records)} operation records found"
    )
    return all_records
