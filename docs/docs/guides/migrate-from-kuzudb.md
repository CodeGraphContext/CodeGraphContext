# Migrating From KuzuDB

KuzuDB support was removed because the upstream project is archived and the
Python package cannot be installed on newer Python versions such as Python 3.14.
If you already have a KuzuDB graph, you can still migrate it by running CGC in a
Docker container that uses an older Python image, installing `kuzu` only inside
that temporary container, and pointing CGC at your new target database.

On Python 3.14, `pip install kuzu` downloads the source distribution because no
compatible wheel is available. The install then goes through the
`pyproject.toml`/setuptools build backend and fails with:

```text
ERROR: Failed building wheel for kuzu
Failed to build kuzu
error: failed-wheel-build-for-install
```

The migration is automatic: when CGC starts, it detects a legacy KuzuDB path,
exports it to a temporary `.cgc` bundle, and imports that bundle into the
database backend you selected.

## Before You Start

Back up the legacy database directory first. KuzuDB may create lock or metadata
files when it opens the store, so keep a backup even if you plan to mount the
database read-only.

```bash
cp -a ~/.codegraphcontext/global/db/kuzudb ~/kuzudb-backup
```

The target database should be empty. CGC skips automatic migration when the
target already contains graph data because merging old and new graphs can create
duplicates or mixed schema state.

## 1. Pick the Target Backend

Choose one target and configure only that target for the migration run.

| Target | Use when | Configuration |
| :--- | :--- | :--- |
| `falkordb` | You want the current local default on Linux or macOS. | `DEFAULT_DATABASE=falkordb`, optional `FALKORDB_PATH`. |
| `ladybugdb` | You want a local embedded fallback. | `DEFAULT_DATABASE=ladybugdb`, optional `LADYBUGDB_PATH`. |
| `falkordb-remote` | You already run a FalkorDB server. | `DEFAULT_DATABASE=falkordb-remote`, `FALKORDB_HOST`, `FALKORDB_PORT`. |
| `neo4j` | You want to migrate into Neo4j. | `DEFAULT_DATABASE=neo4j`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`. |
| `nornic` | You want to migrate into Nornic. | `DEFAULT_DATABASE=nornic`, `NORNIC_URI`, `NORNIC_USERNAME`, `NORNIC_PASSWORD`. |

If you do not set `DEFAULT_DATABASE`, CGC resolves its normal default and
migrates into that backend. On a typical Linux or macOS install with FalkorDB
Lite available, that means `falkordb`.

## 2. Set Paths on the Host

Set the source path to your existing KuzuDB directory. The default legacy path is
shown below.

```bash
export KUZUDB_PATH="$HOME/.codegraphcontext/global/db/kuzudb"
```

For an embedded target, also choose where the new database should be written on
the host.

```bash
export CGC_TARGET_DB_ROOT="$HOME/.codegraphcontext/global/db"
```

Mounting the target root matters because the Docker container has its own home
directory. Without the mount, the migration would succeed inside the container
and disappear when the container exits.

## 3. Run the Migration Container

Use a Python image older than Python 3.14 so `kuzu` can use a published wheel
instead of the failing setuptools build path. Python 3.12 is a safe default for
this migration because it also matches FalkorDB Lite's supported range.

### Embedded Target: FalkorDB Lite

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  -v "$CGC_TARGET_DB_ROOT:/root/.codegraphcontext/global/db" \
  -e KUZUDB_PATH=/legacy-kuzudb \
  -e DEFAULT_DATABASE=falkordb \
  python:3.12-slim bash
```

Inside the container:

```bash
python -m pip install --upgrade pip
python -m pip install codegraphcontext kuzu falkordblite
python - <<'PY'
from codegraphcontext.core import get_database_manager

manager = get_database_manager()
print(f"Migration target: {manager.get_backend_type()}")
PY
```

The Python snippet initializes the selected backend. That startup path is what
detects the KuzuDB source and runs the migration.

### Embedded Target: LadybugDB

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  -v "$CGC_TARGET_DB_ROOT:/root/.codegraphcontext/global/db" \
  -e KUZUDB_PATH=/legacy-kuzudb \
  -e DEFAULT_DATABASE=ladybugdb \
  python:3.12-slim bash
```

Inside the container:

```bash
python -m pip install --upgrade pip
python -m pip install codegraphcontext kuzu ladybug
python - <<'PY'
from codegraphcontext.core import get_database_manager

manager = get_database_manager()
print(f"Migration target: {manager.get_backend_type()}")
PY
```

### Remote Target: FalkorDB Remote

Start or identify your FalkorDB server first. Then run the migration container
with the remote connection settings.

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  -e KUZUDB_PATH=/legacy-kuzudb \
  -e DEFAULT_DATABASE=falkordb-remote \
  -e FALKORDB_HOST=host.docker.internal \
  -e FALKORDB_PORT=6379 \
  python:3.12-slim bash
```

Inside the container:

```bash
python -m pip install --upgrade pip
python -m pip install codegraphcontext kuzu falkordb
python - <<'PY'
from codegraphcontext.core import get_database_manager

manager = get_database_manager()
print(f"Migration target: {manager.get_backend_type()}")
PY
```

On Linux, `host.docker.internal` may not resolve by default. Use
`--network host` and `FALKORDB_HOST=127.0.0.1`, or add an explicit host mapping
for your Docker setup.

### Remote Target: Neo4j

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  -e KUZUDB_PATH=/legacy-kuzudb \
  -e DEFAULT_DATABASE=neo4j \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USERNAME=neo4j \
  -e NEO4J_PASSWORD=password \
  python:3.12-slim bash
```

Inside the container:

```bash
python -m pip install --upgrade pip
python -m pip install codegraphcontext kuzu neo4j
python - <<'PY'
from codegraphcontext.core import get_database_manager

manager = get_database_manager()
print(f"Migration target: {manager.get_backend_type()}")
PY
```

### Remote Target: Nornic

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  -e KUZUDB_PATH=/legacy-kuzudb \
  -e DEFAULT_DATABASE=nornic \
  -e NORNIC_URI="$NORNIC_URI" \
  -e NORNIC_USERNAME="$NORNIC_USERNAME" \
  -e NORNIC_PASSWORD="$NORNIC_PASSWORD" \
  python:3.12-slim bash
```

Inside the container:

```bash
python -m pip install --upgrade pip
python -m pip install codegraphcontext kuzu neo4j
python - <<'PY'
from codegraphcontext.core import get_database_manager

manager = get_database_manager()
print(f"Migration target: {manager.get_backend_type()}")
PY
```

## 4. Verify the Target

After the container exits, use your normal CGC installation with the same target
configuration.

```bash
cgc config db falkordb
cgc stats
cgc list
```

For remote backends, keep the same connection variables configured in your host
environment or CGC config file before running verification commands.

## Troubleshooting

### `kuzu` cannot be installed

Use an older image, for example `python:3.12-slim`. On Python 3.14+, pip falls
back to the `pyproject.toml`/setuptools build path and fails with
`Failed building wheel for kuzu`. The reason for using Docker is to keep that
older Python isolated from your normal Python 3.14+ environment.

### Migration says no legacy KuzuDB store was found

Check the mounted source path:

```bash
docker run --rm -it \
  -v "$KUZUDB_PATH:/legacy-kuzudb" \
  python:3.12-slim \
  ls -la /legacy-kuzudb
```

If your KuzuDB directory is not at the default path, set `KUZUDB_PATH` to the
actual host path before starting the migration container.

### Migration says the target already contains data

The automatic migration refuses to merge into a non-empty target. Point the
target settings at an empty database, or export the existing target data first
and decide how you want to merge the two graphs manually.

### The target was created inside Docker but not on the host

For embedded targets, make sure you mounted the host target root:

```bash
-v "$CGC_TARGET_DB_ROOT:/root/.codegraphcontext/global/db"
```

Without that mount, Docker writes the new database into the container filesystem.
