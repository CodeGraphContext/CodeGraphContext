# CodeGraphContext Docker Guide 🐳

Running CodeGraphContext via Docker is the easiest way to use the tool without setting up a Python environment. This guide covers everything from quick start commands to advanced database configurations.

---

## 1. Quick Start

Pull the latest image from Docker Hub:
```bash
docker pull codegraphcontext/codegraphcontext:latest
```

Index your current directory:
```bash
docker run --rm \
  -v "$(pwd):/workspace" \
  -v cgc-data:/home/cgc/.codegraphcontext \
  codegraphcontext/codegraphcontext cgc index .
```

*Note: The `-v cgc-data:/home/cgc/.codegraphcontext` volume is crucial as it persists the graph database across runs.*

---

## 2. Helper Script

For convenience, a helper script is included in the repository.

```bash
# Clone the repository
git clone https://github.com/CodeGraphContext/CodeGraphContext.git
cd CodeGraphContext

# Index a repo
./scripts/docker-run.sh index /path/to/my-repo

# Run an interactive shell
./scripts/docker-run.sh shell

# Start the visualization server
./scripts/docker-run.sh viz
```

---

## 3. Docker Compose Profiles

The repository includes a production-ready `docker-compose.yml` with several profiles depending on your needs.

### Default Profile (Embedded Database)
Runs CGC using the embedded FalkorDB Lite or KuzuDB backend.

```bash
# Index current directory
docker compose run --rm cgc index .

# Analyze callers
docker compose run --rm cgc analyze callers my_function
```

### `falkordb` Profile
Runs CGC alongside a dedicated FalkorDB container. Recommended for large projects or ARM64 architectures where FalkorDB Lite might not be fully supported.

```bash
# Start FalkorDB in the background
docker compose --profile falkordb up -d

# Now run CGC commands (it will auto-detect the separate database container)
docker compose run --rm cgc index .
```

### `viz` Profile
Starts the Visualization UI server, allowing you to explore the graph in your browser.

```bash
# Start the viz server
docker compose --profile viz up -d

# Visit http://localhost:8080 in your browser
```

### `neo4j` Profile
If you prefer Neo4j, this profile starts a local Neo4j 5.x container.

```bash
# Start Neo4j
docker compose --profile neo4j up -d

# The docker-compose.yml already configures CGC to connect to this Neo4j container.
docker compose run --rm cgc index .
```

---

## 4. MCP Server Mode

You can run CodeGraphContext as an MCP (Model Context Protocol) server inside Docker to connect it to AI assistants like Claude Desktop, Cursor, or Windsurf.

```bash
docker run -i --rm \
  -v "/path/to/your/codebase:/workspace" \
  -v cgc-data:/home/cgc/.codegraphcontext \
  -e CGC_MODE=mcp \
  codegraphcontext/codegraphcontext
```

**Important Notes for MCP in Docker**:
1. You MUST use the `-i` (interactive) flag to keep `stdin` open for the JSON-RPC protocol.
2. Do NOT use the `-t` (tty) flag, as it will corrupt the JSON output.
3. You must mount your local codebase to `/workspace` inside the container so the MCP server can read the files.

### Client Configuration Example (e.g., Claude Desktop)
```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/Users/myname/projects:/workspace",
        "-v",
        "cgc-data:/home/cgc/.codegraphcontext",
        "-e",
        "CGC_MODE=mcp",
        "codegraphcontext/codegraphcontext:latest"
      ]
    }
  }
}
```

---

## 5. Volume Mounts

| Volume Mount | Description |
|---|---|
| `-v "$(pwd):/workspace"` | Mounts your local code into the container so CGC can index it. |
| `-v cgc-data:/home/cgc/.codegraphcontext` | Persists the databases, configuration, and index state. |

**Permissions**: The Docker image runs as a non-root user `cgc` (UID 1000). Ensure the mounted `cgc-data` volume has correct permissions.

---

## 6. Image Variants & Architecture

The `codegraphcontext/codegraphcontext` image is multi-architecture, supporting:
- `linux/amd64` (Standard Intel/AMD x86_64 PCs & Servers)
- `linux/arm64` (Apple Silicon M1/M2/M3, AWS Graviton, Raspberry Pi)

Docker will automatically pull the correct variant for your architecture.

### Available Tags

| Tag | Usage |
|---|---|
| `latest` | The most recent stable release. Recommended for most users. |
| `edge` | Built automatically from the `main` branch. Contains the latest features but may be unstable. |
| `0.4.19` | Specific semantic version. |

---

## 7. Kubernetes Deployment

Manifests are provided in the `k8s/` directory for deploying to a Kubernetes cluster.

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

*Note: You may need to adjust the PersistentVolumeClaim (`pvc.yaml`) storage class to match your cluster environment.*
