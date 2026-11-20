# Migrating Legacy KuzuDB Data in CodeGraphContext

KuzuDB is archived upstream, so CGC treats it as a legacy backend with an exit path rather than a maintained default.
LadybugDB is the maintained embedded implementation for the same CGC use cases. The storage formats are not
interchangeable, which means pointing LadybugDB at a Kuzu directory can fail before any data is available.

CGC migrates the graph through a `.cgc` bundle:

1. A separate Python process opens the Kuzu store and exports a temporary bundle.
2. The normal CGC process imports that bundle through the selected target manager.
3. CGC leaves the source store untouched and refuses to import unless it can confirm that the target is empty.

The process boundary matters because Kuzu and Ladybug expose conflicting native pybind types. They must not be loaded
in the same interpreter.

## Back up first (the boring part that saves the day)

Create a writable backup of the Kuzu directory before opening it with migration tooling. Kuzu may create lock or
metadata files even when the intended operation is read-only.

```bash
cp -a ~/.codegraphcontext/global/db/kuzudb ~/kuzudb-migration-backup
```

Set the source explicitly so discovery does not depend on an old config file:

```bash
export KUZUDB_PATH="$HOME/kuzudb-migration-backup"
```

## Use a separate compatible interpreter

The normal CGC install does not include Kuzu. If Python 3.12 is available, create a small environment containing only
the final archived driver and point the exporter at it:

```bash
uv venv --python 3.12 "$HOME/.cache/cgc-kuzu-migration"
uv pip install --python "$HOME/.cache/cgc-kuzu-migration/bin/python" "kuzu==0.11.3"
export CGC_KUZU_MIGRATION_PYTHON="$HOME/.cache/cgc-kuzu-migration/bin/python"
```

Select Ladybug and a new target path. Starting any command that initializes the database triggers the one-time probe
for that target path:

```bash
cgc --db ladybugdb --db-path "$HOME/.codegraphcontext/global/db/ladybugdb" list
```

A successful run reports the source, target backend, and imported node and edge counts. If the target contains data or
CGC cannot prove that it is empty, migration stops without merging the graphs.

## Docker or nerdctl remains the fallback

Use a Python 3.12 container when no compatible local interpreter is available. Mount a writable source backup and a
persistent target directory (otherwise the migrated database disappears with the container):

```bash
docker run --rm -it \
  -v "$HOME/kuzudb-migration-backup:/migration/source" \
  -v "$HOME/.codegraphcontext/global/db:/migration/target" \
  python:3.12-slim \
  sh -lc 'pip install "codegraphcontext[ladybug,kuzu]" && \
    KUZUDB_PATH=/migration/source \
    cgc --db ladybugdb --db-path /migration/target/ladybugdb list'
```

`nerdctl run` accepts the same image, mounts, and command when containerd is the local runtime.

## Legacy runtime compatibility

An existing deployment can still install `codegraphcontext[kuzu]` and explicitly select `kuzudb` during the migration
window. CGC warns on that path and never selects Kuzu implicitly. This compatibility is not a promise of future engine
support: Kuzu 0.11.3 is the final release, and its wheel availability already differs by Python version and platform.

The migration tool remains the durable compatibility boundary because the current CGC process only needs to understand
the bundle format. The archived native driver can stay isolated in an older interpreter or container.
