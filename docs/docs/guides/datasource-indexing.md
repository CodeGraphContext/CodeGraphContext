# Ingesting Database & Cache Schemas

CodeGraphContext (CGC) goes beyond parsing code syntax—it allows developers to ingest database and cache schemas. By linking code functions to database columns or cache keys, CGC maps dependencies from the API layer down to the storage tables.

---

## 1. Supported Datasources

CGC provides ingestion connectors for three primary database models:

1. **Aurora MySQL / Relational Schemas**: Ingests tables, columns, primary/foreign keys, and SQL constraints.
2. **Apache Cassandra / Column-Family Schemas**: Ingests keyspaces, column families (tables), columns, and cluster keys.
3. **Redis / NoSQL Cache Stores**: Ingests logical key namespace patterns and cache structure types.

---

## 2. Ingesting Schemas via CLI

Use the `cgc datasource` command group to configure and ingest datasource metadata.

### A. Ingesting MySQL Schemas
Connect to a MySQL database to extract table metadata and column datatypes:

```bash
cgc datasource mysql --host 127.0.0.1 --port 3306 --user app_user --password secure_pass --database main_db
```

This populates the active context with `DbTable` and `DbColumn` nodes, linking tables to columns via `CONTAINS` edges.

### B. Ingesting Cassandra Schemas
Connect to a Cassandra cluster to extract keyspace schemas:

```bash
cgc datasource cassandra --host 127.0.0.1 --port 9042 --keyspace production_keyspace
```

This populates the context with keyspace tables and columns.

### C. Ingesting Redis Key Patterns
Analyze active Redis databases to extract key schemas:

```bash
cgc datasource redis --host 127.0.0.1 --port 6379 --db 0
```

This command runs key scans, resolves namespaces (e.g., `user:*:profile` or `session:*`), and populates `RedisKeyPattern` nodes.

---

## 3. Resolving Code-to-Database Relationships

After ingesting both your codebase (via `cgc index`) and your database schemas (via `cgc datasource`), CGC runs static query analysis.

It parses SQL query strings and Redis command invocations inside your code functions (e.g., `SELECT user_id FROM users` or `redis.get(f"user:{user_id}:profile")`) and resolves target nodes.

### Resulting Edges:
- **`READS`**: Ingested when a function queries database tables, reads columns, or fetches Redis key patterns.
- **`WRITES`**: Ingested when a function writes data to tables (INSERT, UPDATE, DELETE) or modifies cache keys.

---

## 4. Querying Datasource Relationships

Once the unified graph is created, you can query relationships using Cypher:

### Example A: Trace Functions Modifying a Table
```cypher
MATCH (fn:Function)-[:WRITES]->(table:DbTable {name: 'orders'})
RETURN fn.name, fn.path
```

### Example B: Identify Functions Interfacing with Cache Patterns
```cypher
MATCH (fn:Function)-[:READS]->(cache:RedisKeyPattern)
WHERE cache.pattern CONTAINS 'session'
RETURN fn.name, cache.pattern
```
