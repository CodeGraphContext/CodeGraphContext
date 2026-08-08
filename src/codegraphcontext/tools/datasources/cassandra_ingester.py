# src/codegraphcontext/tools/datasources/cassandra_ingester.py
"""Cassandra schema ingester (#843).

Pulls keyspace + table + column metadata from system_schema and writes
Datasource / DbTable / DbColumn nodes.

Requires: pip install cassandra-driver
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def ingest(
    hosts: List[str],
    port: int,
    keyspace: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    name: Optional[str] = None,
    env: str = "production",
) -> Dict[str, Any]:
    """Fetch schema from Cassandra system_schema and return a datasource graph dict.

    Returns:
        {
            datasource: {name, kind, host, env, keyspace},
            tables:     [{name, fqn, datasource_name}],
            columns:    [{name, type, nullable, table_fqn, datasource_name}],
        }
    """
    try:
        from cassandra.cluster import Cluster
        from cassandra.auth import PlainTextAuthProvider
    except ImportError:
        raise ImportError(
            "Cassandra driver not found. Install with: pip install cassandra-driver"
        )

    datasource_name = name or f"cassandra-{keyspace}"

    auth_provider = None
    if username and password:
        auth_provider = PlainTextAuthProvider(username=username, password=password)

    cluster = Cluster(hosts, port=port, auth_provider=auth_provider)
    session = cluster.connect()

    try:
        tables: List[Dict[str, Any]] = []
        columns: List[Dict[str, Any]] = []

        # Tables from system_schema
        rows = session.execute(
            "SELECT table_name, comment FROM system_schema.tables WHERE keyspace_name = %s",
            (keyspace,),
        )
        for row in rows:
            fqn = f"{keyspace}.{row.table_name}"
            tables.append({
                "name": row.table_name,
                "fqn": fqn,
                "datasource_name": datasource_name,
                "comment": getattr(row, "comment", ""),
            })

        # Columns from system_schema
        rows = session.execute(
            """SELECT table_name, column_name, type, kind
               FROM system_schema.columns
               WHERE keyspace_name = %s""",
            (keyspace,),
        )
        for row in rows:
            table_fqn = f"{keyspace}.{row.table_name}"
            columns.append({
                "name": row.column_name,
                "type": row.type,
                "nullable": True,  # Cassandra columns are always nullable except PK
                "table_fqn": table_fqn,
                "datasource_name": datasource_name,
                "is_primary_key": row.kind in ("partition_key", "clustering"),
            })

    finally:
        session.shutdown()
        cluster.shutdown()

    return {
        "datasource": {
            "name": datasource_name,
            "kind": "cassandra",
            "host": hosts[0],
            "env": env,
            "keyspace": keyspace,
        },
        "tables": tables,
        "columns": columns,
    }
