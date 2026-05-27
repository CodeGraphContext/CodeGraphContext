# src/codegraphcontext/tools/datasources/mysql_ingester.py
"""Aurora MySQL schema ingester (#843).

Pulls table + column metadata from information_schema and writes
Datasource / DbTable / DbColumn nodes with HAS_COLUMN and STORED_IN edges.

Requires: pip install PyMySQL  (or mysql-connector-python)
Connection URI:  mysql://user:pass@host:3306/database
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _connect(host: str, port: int, user: str, password: str, database: str) -> Any:
    """Return a DB-API 2.0 connection. Tries PyMySQL then mysql-connector-python."""
    try:
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=user, password=password, database=database,
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
        )
    except ImportError:
        pass
    try:
        import mysql.connector
        return mysql.connector.connect(
            host=host, port=port, user=user, password=password, database=database,
            connection_timeout=10,
        )
    except ImportError:
        raise ImportError(
            "MySQL driver not found. Install with: pip install PyMySQL"
        )


def ingest(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    name: Optional[str] = None,
    env: str = "production",
) -> Dict[str, Any]:
    """Fetch schema from Aurora MySQL and return a datasource graph dict.

    Returns:
        {
            datasource: {name, kind, host, env, database},
            tables:     [{name, fqn, datasource_name}],
            columns:    [{name, type, nullable, table_fqn, datasource_name}],
        }
    """
    datasource_name = name or f"mysql-{database}"
    conn = _connect(host, port, user, password, database)

    try:
        tables: List[Dict[str, Any]] = []
        columns: List[Dict[str, Any]] = []

        with conn.cursor() as cur:
            # Tables
            cur.execute(
                """
                SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS, TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME
                """,
                (database,),
            )
            for row in cur.fetchall():
                fqn = f"{database}.{row['TABLE_NAME']}"
                tables.append({
                    "name": row["TABLE_NAME"],
                    "fqn": fqn,
                    "datasource_name": datasource_name,
                    "table_type": row.get("TABLE_TYPE", "BASE TABLE"),
                    "estimated_rows": row.get("TABLE_ROWS"),
                    "comment": row.get("TABLE_COMMENT", ""),
                })

            # Columns
            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                       COLUMN_DEFAULT, COLUMN_COMMENT, COLUMN_KEY
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                (database,),
            )
            for row in cur.fetchall():
                table_fqn = f"{database}.{row['TABLE_NAME']}"
                columns.append({
                    "name": row["COLUMN_NAME"],
                    "type": row["DATA_TYPE"],
                    "nullable": row["IS_NULLABLE"] == "YES",
                    "table_fqn": table_fqn,
                    "datasource_name": datasource_name,
                    "is_primary_key": row.get("COLUMN_KEY") == "PRI",
                    "comment": row.get("COLUMN_COMMENT", ""),
                })

    finally:
        conn.close()

    return {
        "datasource": {
            "name": datasource_name,
            "kind": "mysql",
            "host": host,
            "env": env,
            "database": database,
        },
        "tables": tables,
        "columns": columns,
    }
