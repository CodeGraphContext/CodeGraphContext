# Portable CGC Bundles & Registries

CodeGraphContext (CGC) supports **Portable Graph Bundles** (`.cgc` files)—serialized snapshots of an indexed codebase. Bundles allow teams to distribute pre-parsed code structures so that other developers or CI runners can load them without re-parsing the original source code.

---

## 1. Exporting a Graph Bundle

To package your current database graph into a single `.cgc` file, use the `bundle export` command:

```bash
# Export the entire active database graph
cgc bundle export my-app-v1.cgc

# Export only a specific repository path from the database
cgc bundle export my-app-v1.cgc --repo /path/to/project
```

The exported file contains compressed serialization of all nodes, relationships, and ingestion metadata.

---

## 2. Importing a Graph Bundle

To import a local `.cgc` bundle file into your active database context:

```bash
# Append bundle contents into the current database
cgc bundle import ./my-app-v1.cgc

# Clear existing data in the active context before importing
cgc bundle import ./my-app-v1.cgc --clear
```

The database is populated immediately and is ready for CLI query operations or MCP server sessions.

---

## 3. The Public Bundle Registry

CGC hosts a remote repository of pre-indexed graph bundles for popular libraries and frameworks, allowing developers to query third-party code structures.

### Searching the Registry
Search for public graph packages matching a specific keyword (e.g., `flask`):

```bash
cgc registry search flask
```

### Loading Registry Bundles
To download and load a package from the registry directly into your local database:

```bash
cgc bundle load flask
```

If the package is not found locally, the engine contacts the remote registry API, downloads the matching version, and runs the import process automatically.

### Registry Command Suite
- **List All Available Registry Packages**:
  ```bash
  cgc registry list
  ```
- **Request On-Demand Generation**: If a specific library is missing, submit a request for the registry build server to generate a bundle from a public GitHub repository URL:
  ```bash
  cgc registry request https://github.com/pallets/click --wait
  ```
