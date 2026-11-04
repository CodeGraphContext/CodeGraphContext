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


def _extract_sql(element: ET.Element, fragments=None, seen=frozenset()) -> str:
    """Read nested dynamic SQL and expand known includes without cycling."""
    if element.tag == 'include':
        fragment = (fragments or {}).get(element.get('refid', ''))
        if fragment is None or id(fragment) in seen:
            return ''
        return _extract_sql(fragment, fragments, seen | {id(fragment)})
    parts = [element.text or '']
    for child in element:
        parts.append(_extract_sql(child, fragments, seen))
        parts.append(child.tail or '')
    return ' '.join(parts)


def _mask_sql_literals_and_comments(sql: str) -> str:
    parts = []
    index = 0
    while index < len(sql):
        if sql.startswith('--', index):
            end = sql.find('\n', index + 2)
            index = len(sql) if end < 0 else end
            parts.append(' ')
        elif sql.startswith('/*', index):
            depth = 1
            index += 2
            while index < len(sql) and depth:
                if sql.startswith('/*', index):
                    depth += 1
                    index += 2
                elif sql.startswith('*/', index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            parts.append(' ')
        elif sql[index] == "'":
            index += 1
            while index < len(sql):
                if sql.startswith("''", index):
                    index += 2
                elif sql[index] == "'":
                    index += 1
                    break
                elif sql[index] == '\\':
                    index += 2
                else:
                    index += 1
            parts.append(' ')
        elif sql[index] in ('"', '`', '['):
            start = index
            end_quote = ']' if sql[index] == '[' else sql[index]
            index += 1
            while index < len(sql):
                if sql.startswith(end_quote * 2, index):
                    index += 2
                elif sql[index] == end_quote:
                    index += 1
                    break
                else:
                    index += 1
            parts.append(sql[start:index])
        else:
            tag = re.match(r'\$(?:[A-Za-z_]\w*)?\$', sql[index:])
            if tag:
                end = sql.find(tag.group(), index + len(tag.group()))
                index = len(sql) if end < 0 else end + len(tag.group())
                parts.append(' ')
            else:
                parts.append(sql[index])
                index += 1
    return ''.join(parts)


def _parse_sql_tables(sql: str) -> List[str]:
    """Extract table names from a SQL string (best-effort, no full parser)."""
    sql_upper = _mask_sql_literals_and_comments(sql).upper()
    tables: List[str] = []
    identifier = r'(?:`[^`]+`|"[^"]+"|\[[^\]]+\]|[A-Z_][\w$]*)'
    pattern = rf'\b(FROM|JOIN|INTO|UPDATE|TABLE)\s+(?:ONLY\s+)?(?:IF\s+(?:NOT\s+)?EXISTS\s+)?({identifier}(?:\s*\.\s*{identifier})*)'
    for match in re.finditer(pattern, sql_upper):
        if match.group(1) == 'UPDATE' and re.search(r'ON\s+DUPLICATE\s+KEY\s*$', sql_upper[:match.start()]):
            continue
        raw = re.findall(identifier, match.group(2))[-1].strip('`"[]').lower()
        if raw not in {'set', 'select', 'values', 'if', 'not', 'exists'}:
            tables.append(raw)
    # Deduplicate, preserving order
    seen: set = set()
    result: List[str] = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def parse_mybatis_mapper(file_path: Path, sql_fragments=None) -> List[Dict[str, Any]]:
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

        namespace = root.get("namespace", "").strip()
        fragments = dict(sql_fragments or {})
        for fragment in root.findall('sql'):
            fragment_id = fragment.get('id')
            if fragment_id:
                fragments[fragment_id] = fragment
                if namespace:
                    fragments[namespace + '.' + fragment_id] = fragment
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

            sql_text = _extract_sql(child, fragments)
            tables = _parse_sql_tables(sql_text)

            # Fallback: infer table from mapper class name
            if not tables and not sql_text.strip() and not any(n.tag == 'include' for n in child.iter()):
                inferred = _class_name_to_table(class_name)
                if inferred:
                    tables = [inferred]

            if not tables:
                # Still nothing — skip (no useful edge to write)
                continue

            records.append({
                "method_name": method_id,
                "class_name": class_name,
                "mapper_namespace": namespace,
                "db_tables": tables,
                "operation": operation,
                "mapper_path": str(file_path),
            })

    except ET.ParseError as e:
        error_logger(f"[MYBATIS] XML parse error in {file_path}: {e}")
    except Exception as e:
        error_logger(f"[MYBATIS] Error parsing {file_path}: {e}")

    return records


def resolve_mybatis_sources(
    records: List[Dict[str, Any]], java_file_data: List[Dict[str, Any]], repo_path: Path,
) -> List[Dict[str, Any]]:
    """Resolve namespaces against unique Java declarations already parsed for this repo.

    Never guess by basename: two packages (or modules) may define UserMapper.
    The path also lets the writer match SCIP functions lacking class_context.
    """
    repo_root = repo_path.resolve()
    sources: Dict[str, set[str]] = {}
    for file_data in java_file_data:
        source = Path(file_data["path"]).resolve()
        if source.suffix.lower() != ".java" or not source.is_relative_to(repo_root):
            continue
        package = file_data.get("package_name")
        for declaration in file_data.get("classes", []) + file_data.get("interfaces", []):
            name = declaration.get("name")
            qualified = declaration.get("qualified_name") or (f"{package}.{name}" if package else name)
            if qualified:
                sources.setdefault(qualified, set()).add(source.as_posix())

    resolved = []
    for record in records:
        namespace = record.get("mapper_namespace") or record.get("class_name")
        candidates = sources.get(namespace, set())
        resolved.append({**record, "method_path": next(iter(candidates)) if len(candidates) == 1 else None})
    return resolved


def find_and_parse_mybatis_mappers(
    repo_path: Path, java_file_data: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Walk *repo_path* for MyBatis mapper XML files and return all operation records.

    A file is treated as a mapper when it matches ``*Mapper.xml`` *or* when its
    root element is ``<mapper>``.  Target directories (``target/``, ``build/``,
    ``out/``) are skipped to avoid duplicates from compiled artefacts.
    """
    skip_dirs = {"target", "build", "out", ".git", "node_modules", "__pycache__"}
    all_records: List[Dict[str, Any]] = []
    file_count = 0

    mapper_files = []
    fragments = {}
    for xml_file in sorted(repo_path.rglob('*.xml')):
        if any(part in skip_dirs for part in xml_file.relative_to(repo_path).parts):
            continue
        try:
            root = ET.parse(xml_file).getroot()
        except (ET.ParseError, OSError):
            continue
        if root.tag != 'mapper':
            continue
        mapper_files.append(xml_file)
        namespace = root.get('namespace', '').strip()
        for fragment in root.findall('sql'):
            name = fragment.get('id')
            if name and namespace:
                key = namespace + '.' + name
                fragments[key] = None if key in fragments else fragment

    for xml_file in mapper_files:
        records = parse_mybatis_mapper(xml_file, fragments)
        if records:
            all_records.extend(records)
            file_count += 1

    info_logger(
        f"[MYBATIS] Parsed {file_count} mapper files, "
        f"{len(all_records)} operation records found"
    )
    return resolve_mybatis_sources(all_records, java_file_data or [], repo_path)
