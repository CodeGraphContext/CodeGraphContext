# Portable CGC Bundles & Registries

CodeGraphContext (CGC) supports **Portable Graph Bundles** (`.cgc` files)—serialized snapshots of an indexed codebase. Bundles allow teams to distribute pre-parsed code structures so that other developers or CI runners can load them without re-parsing the original source code.

## 🎯 What are .cgc Bundles?

`.cgc` (CodeGraphContext Bundle) files are **portable, pre-indexed graph snapshots** that can be distributed and loaded instantly without re-indexing. Think of them as "npm packages for code knowledge graphs."

### Key Benefits

- ⚡ **Instant Loading** - Load in seconds instead of minutes/hours of indexing
- 🎯 **Pre-analyzed** - All code relationships already computed
- 🔍 **Query Ready** - Start using with AI assistants immediately
- 📦 **Portable** - Works across any CodeGraphContext installation
- 🌐 **Shareable** - Distribute pre-indexed knowledge easily

---

## 📦 Bundle Structure

A `.cgc` file is a ZIP archive containing:

```
numpy.cgc
├── metadata.json       # Repository and indexing metadata
├── schema.json         # Graph schema definition
├── nodes.jsonl         # All nodes (one JSON per line)
├── edges.jsonl         # All relationships (one JSON per line)
├── stats.json          # Graph statistics
└── README.md           # Human-readable description
```

### File Formats

#### metadata.json
```json
{
  "cgc_version": "0.5.0",
  "exported_at": "2026-01-13T22:00:00",
  "repo": "numpy/numpy",
  "commit": "a1b2c3d4",
  "languages": ["python", "c"],
  "format_version": "1.0"
}
```

#### nodes.jsonl (excerpt)
```jsonl
{"_id": "4:abc123", "_labels": ["Function"], "name": "array", "path": "/numpy/core/array.py", "line_number": 42}
{"_id": "4:def456", "_labels": ["Class"], "name": "ndarray", "path": "/numpy/core/multiarray.py", "line_number": 100}
```

#### edges.jsonl (excerpt)
```jsonl
{"from": "4:abc123", "to": "4:def456", "type": "CALLS", "properties": {}}
{"from": "4:xyz789", "to": "4:def456", "type": "INHERITS", "properties": {}}
```

---

## 🚀 Quick Start

### Creating Bundles

```bash
# Export current indexed repository
cgc bundle export my-project.cgc --repo /path/to/project

# Export all indexed repositories
cgc bundle export all-repos.cgc

# Export without statistics (faster)
cgc bundle export quick.cgc --repo /path/to/project --no-stats

# Shortcut
cgc export my-project.cgc --repo /path/to/project
```

### Loading Bundles

```bash
# Load a bundle (adds to existing graph)
cgc bundle import numpy.cgc

# Load and clear existing data (interactive confirmation)
cgc bundle import numpy.cgc --clear

# Non-interactive / CI: skip confirmation when clearing
cgc bundle import numpy.cgc --clear --yes
cgc bundle load numpy --clear -y

# Shortcut
cgc load numpy.cgc
```

### Using Pre-indexed Bundles

```bash
# Download from GitHub Releases
wget https://github.com/CodeGraphContext/CodeGraphContext/releases/download/bundles-20260113/numpy-1.26.4-a1b2c3d.cgc

# Load it
cgc load numpy-1.26.4-a1b2c3d.cgc

# Start querying immediately
cgc find name linalg
cgc analyze deps numpy.linalg
```

---

## 📚 Available Pre-indexed Bundles

We provide weekly-updated bundles for popular repositories:

### Tier 1 - Python Core Libraries

| Repository | Description | Size | Download |
|------------|-------------|------|----------|
| **numpy** | Scientific computing | ~50MB | [Latest](https://github.com/CodeGraphContext/CodeGraphContext/releases/latest) |
| **pandas** | Data analysis | ~80MB | [Latest](https://github.com/CodeGraphContext/CodeGraphContext/releases/latest) |
| **fastapi** | Modern web framework | ~15MB | [Latest](https://github.com/CodeGraphContext/CodeGraphContext/releases/latest) |
| **requests** | HTTP library | ~10MB | [Latest](https://github.com/CodeGraphContext/CodeGraphContext/releases/latest) |
| **flask** | Web framework | ~12MB | [Latest](https://github.com/CodeGraphContext/CodeGraphContext/releases/latest) |

### Coming Soon

- **scikit-learn** - Machine learning
- **django** - Web framework
- **pytorch** - Deep learning (subset)
- **kubernetes** - Container orchestration (Go)
- **redis** - In-memory database

---

## 🔧 Advanced Usage

### Bundle Versioning

Bundles follow this naming convention:
```
<repo-name>-<version>-<commit>.cgc
```

Examples:
- `numpy-1.26.4-a1b2c3d.cgc`
- `pandas-2.1.0-xyz789.cgc`
- `fastapi-0.109.0-abc123.cgc`

### Combining Bundles

```bash
# Load multiple bundles into the same graph
cgc load numpy.cgc
cgc load pandas.cgc
cgc load scikit-learn.cgc

# Now query across all three
cgc find name fit --type function
```

### Exporting Specific Repositories

```bash
# Index multiple repos
cgc index /path/to/numpy
cgc index /path/to/pandas

# Export each separately
cgc export numpy.cgc --repo /path/to/numpy
cgc export pandas.cgc --repo /path/to/pandas

# Or export everything
cgc export all-my-projects.cgc
```

---

## 🏗️ Creating Your Own Bundle Registry

### 1. Index Your Repositories

```bash
# Clone and index
git clone https://github.com/your-org/your-repo
cd your-repo
cgc index .
```

### 2. Export to Bundle

```bash
# Get commit info
COMMIT=$(git rev-parse --short HEAD)
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "main")

# Export with version info
cgc export "your-repo-${TAG}-${COMMIT}.cgc" --repo .
```

### 3. Distribute

#### Option A: GitHub Releases

```bash
# Create a release
gh release create bundles-$(date +%Y%m%d) \
  your-repo-*.cgc \
  --title "Pre-indexed Bundles - $(date +%Y-%m-%d)" \
  --notes "Pre-indexed code graphs for instant loading"
```

#### Option B: Object Storage (S3, R2, GCS)

```bash
# Upload to S3
aws s3 cp your-repo-*.cgc s3://your-bucket/bundles/

# Make public or use signed URLs
aws s3 presign s3://your-bucket/bundles/your-repo-*.cgc
```

#### Option C: Hugging Face Datasets

```bash
# Install huggingface_hub
pip install huggingface_hub

# Upload
huggingface-cli upload your-org/cgc-bundles your-repo-*.cgc
```

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

---

## 🔍 Bundle Inspection

### View Bundle Contents

```bash
# Extract and view
unzip -l numpy.cgc

# View metadata
unzip -p numpy.cgc metadata.json | jq

# View statistics
unzip -p numpy.cgc stats.json | jq

# Read README
unzip -p numpy.cgc README.md
```

### Validate Bundle

```bash
# Check bundle integrity
cgc bundle validate numpy.cgc  # (future feature)
```

---

## 🎓 Use Cases

### 1. AI Assistant Context

```bash
# AI can now query structure instantly
# "Show me all functions that use numpy.linalg"
```

### 2. Code Analysis Pipelines

```bash
# CI/CD: Load pre-indexed dependencies
cgc load fastapi.cgc
cgc load sqlalchemy.cgc

# Analyze your code against them
cgc index ./my-api
cgc analyze deps my_api
```

### 3. Educational Resources

```bash
# Students can explore famous codebases
cgc load django.cgc
cgc find name authenticate
cgc analyze chain authenticate
```

### 4. Research & Documentation

```bash
# Researchers can analyze code evolution
cgc load numpy-1.25.0.cgc
cgc load numpy-1.26.0.cgc

# Compare structures (future feature)
cgc diff numpy-1.25.0.cgc numpy-1.26.0.cgc
```

---

## 🔐 Security Considerations

### Bundle Verification

Always verify bundles from untrusted sources:

```bash
# Check metadata
unzip -p bundle.cgc metadata.json

# Verify source repository
# Ensure commit hash matches official repo
```

### Sandboxing

Bundles only contain graph data, not executable code. However:
- Review metadata before loading
- Use `--clear` cautiously (it deletes existing data)
- Keep backups of your graph database

---

## 🛠️ Troubleshooting

### Bundle Import Fails

```bash
# Check bundle integrity
unzip -t bundle.cgc

# Verify format version
unzip -p bundle.cgc metadata.json | jq .cgc_version

# Try with --clear flag
cgc load bundle.cgc --clear
```

### Large Bundle Performance

```bash
# For very large bundles, increase batch size
# (future configuration option)
export CGC_IMPORT_BATCH_SIZE=5000
cgc load large-bundle.cgc
```

### Version Mismatch

```bash
# Check your CGC version
cgc --version

# Update if needed
pip install --upgrade codegraphcontext

# Check bundle version
unzip -p bundle.cgc metadata.json | jq .cgc_version
```

---

## 📖 API Reference

### Python API

```python
from codegraphcontext.core.cgc_bundle import CGCBundle
from codegraphcontext.core.database import DatabaseManager

# Initialize
db_manager = DatabaseManager()
bundle = CGCBundle(db_manager)

# Export
success, message = bundle.export_to_bundle(
    output_path=Path("my-bundle.cgc"),
    repo_path=Path("/path/to/repo"),
    include_stats=True
)

# Import
success, message = bundle.import_from_bundle(
    bundle_path=Path("my-bundle.cgc"),
    clear_existing=False
)
```

---

## 🗺️ Roadmap

### v0.2.0 - Bundle Registry
- [ ] Central bundle registry
- [ ] `cgc registry search` command
- [ ] Automatic download from registry
- [ ] Bundle versioning and updates

### v0.3.0 - Advanced Features
- [ ] Delta bundles (incremental updates)
- [ ] Bundle compression options
- [ ] Encrypted bundles
- [ ] Bundle signing and verification

### v0.4.0 - Collaboration
- [ ] Bundle merging
- [ ] Conflict resolution
- [ ] Multi-repository bundles
- [ ] Bundle diff and comparison

---

## 🤝 Contributing

### Creating Bundles for Popular Repos

We welcome contributions of pre-indexed bundles! See [CONTRIBUTING.md](../docs/contributing.md) for guidelines.

### Improving Bundle Format

The bundle format is versioned and extensible. Propose improvements via GitHub issues.

---

## 📄 License

Bundle format specification: MIT License
Pre-indexed bundles: Subject to source repository licenses
