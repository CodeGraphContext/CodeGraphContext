# Migrate an Indexed Graph Between Backends

Use `cgc bundle migrate` to copy an existing indexed graph into an empty
database without re-indexing the source code. Migration exports all repositories
and their relationships into a portable `.cgc` bundle, then imports it through
the selected target backend. The bundle is retained as a recovery checkpoint.

This works independently of backend maintenance policy. KuzuDB remains a runtime
backend; migration does not retire a backend or change your configured default.

## Prepare the Source and Target

Stop CGC servers, watchers, and other writers using either database. Back up the
source with the engine's normal backup procedure before starting. Opening the
source through CGC can apply normal schema compatibility updates.

Install CGC and the relevant database drivers. For an embedded backend
(`kuzudb`, `ladybugdb`, or `falkordb`), supply the exact source and target paths.
The source must exist, and the paths must be separate, including through
symlinks. Storage formats are engine-specific: pointing LadybugDB at an existing
KuzuDB store does not migrate it.

For remote backends, configure their connection settings as described in
[Database Backends](../concepts/backends.md). The migration command loads CGC's
configured credentials and inherits environment variables. It refuses to proceed
if the factory falls back to a different backend.

The target must be empty and dedicated to this migration. Keep other writers
stopped throughout export, import, and verification; the empty check does not
lock out external clients.

## Copy the Graph

For example, copy KuzuDB into a new LadybugDB database:

```bash
cgc bundle migrate ./graph-migration.cgc \
  --from kuzudb --source-path /data/cgc/kuzudb \
  --to ladybugdb --target-path /data/cgc/ladybugdb
```

The same command supports other backend pairs. For example, with Neo4j
credentials already configured:

```bash
cgc bundle migrate ./graph-to-neo4j.cgc \
  --from ladybugdb --source-path /data/cgc/ladybugdb \
  --to neo4j
```

The output must be a new `.cgc` file outside both embedded database paths. An
existing bundle is never overwritten. Migration copies the complete graph and
preserves stored repository paths. Source export and target import run in
separate processes, which keeps Kuzu and Ladybug native modules isolated.

If the source driver requires another Python version, create a compatible
environment with CGC and that driver installed, then pass its executable:

```bash
cgc bundle migrate ./graph-migration.cgc \
  --from kuzudb --source-path /data/cgc/kuzudb \
  --source-python /opt/cgc-source/bin/python \
  --to ladybugdb --target-path /data/cgc/ladybugdb
```

Use the same CGC version in both interpreters so the bundle format and schema
contracts agree. For endpoints requiring different credentials for the same
backend, run `cgc bundle export` and `cgc bundle import` separately with each
endpoint's environment instead.

## Verify and Switch Explicitly

Inspect the retained bundle, then query the target before changing your default
or pointing an MCP context at it:

```bash
cgc bundle inspect ./graph-migration.cgc
cgc --database ladybugdb --db-path /data/cgc/ladybugdb list
cgc --database ladybugdb --db-path /data/cgc/ladybugdb stats
cgc --database ladybugdb --db-path /data/cgc/ladybugdb cypher \
  'MATCH ()-[r]->() RETURN count(r) AS relationships'
```

Compare repositories, node and relationship counts, and representative code
queries with the source. Migration retains the source graph and leaves backend
configuration unchanged so you can continue using it until the target is verified.

Import is not transactional across the entire graph. If it fails, the target may
contain a partial import; the completed export is retained. Inspect the failure,
then use a fresh empty target and the retained bundle with `cgc bundle import`.
The migration command never clears a populated target or automatically deletes
the source. Keep the source backup and bundle until verification is complete.
