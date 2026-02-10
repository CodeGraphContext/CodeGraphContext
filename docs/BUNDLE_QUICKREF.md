# CGC Bundle Quick Reference

## 🚀 Quick Start

```bash
# Load a pre-indexed bundle
cgc load numpy.cgc

# Export your project
cgc export my-project.cgc --repo /path/to/project

# Import a bundle
cgc bundle import bundle.cgc --clear
```

## 📦 Bundle Commands

### Export
```bash
# Export specific repository
cgc bundle export OUTPUT.cgc --repo /path/to/repo

# Export all indexed repositories
cgc bundle export all-repos.cgc

# Export without statistics (faster)
cgc bundle export quick.cgc --repo /path/to/repo --no-stats

# Shortcut
cgc export OUTPUT.cgc --repo /path/to/repo
```

### Import
```bash
# Import bundle (add to existing graph)
cgc bundle import BUNDLE.cgc

# Import and clear existing data
cgc bundle import BUNDLE.cgc --clear
```

### Load
```bash
# Load bundle (convenience command)
cgc load BUNDLE.cgc

# Load and clear existing data
cgc load BUNDLE.cgc --clear

# Future: Download from registry
cgc load numpy  # Will download numpy.cgc
```

## 🌐 Download Pre-indexed Bundles

```bash
# From GitHub Releases
wget https://github.com/Shashankss1205/CodeGraphContext/releases/latest/download/numpy-1.26.4.cgc

# Load it
cgc load numpy-1.26.4.cgc

# Start using
cgc find name linalg
```

## 🛠️ Create Your Own Bundle

### Method 1: From Existing Index
```bash
# Index your project
cgc index /path/to/project

# Export to bundle
cgc export my-project.cgc --repo /path/to/project
```

### Method 2: Using Helper Script
```bash
# Clone, index, and export in one go
./scripts/create-bundle.sh owner/repo [output-name]

# Example
./scripts/create-bundle.sh numpy/numpy
```

### Method 3: Manual Process
```bash
# Clone repository
git clone https://github.com/owner/repo
cd repo

# Index it
cgc index .

# Get version info
COMMIT=$(git rev-parse --short HEAD)
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "main")

# Export with version
cgc export "repo-${TAG}-${COMMIT}.cgc" --repo .
```

## 📊 Inspect Bundles

```bash
# List contents
unzip -l bundle.cgc

# View metadata
unzip -p bundle.cgc metadata.json | jq

# View statistics
unzip -p bundle.cgc stats.json | jq

# Read README
unzip -p bundle.cgc README.md

# Extract bundle
unzip bundle.cgc -d extracted/
```

## 🔄 Common Workflows

### Workflow 1: Load Famous Library
```bash
# Download
wget https://github.com/.../numpy.cgc

# Load
cgc load numpy.cgc

# Query
cgc find name array
cgc analyze deps numpy.linalg
```

### Workflow 2: Share Team Project
```bash
# Developer A: Create bundle
cgc index /path/to/company-api
cgc export company-api.cgc --repo /path/to/company-api

# Share file (email, S3, GitHub, etc.)

# Developer B: Load bundle
cgc load company-api.cgc

# Start working
cgc find name authenticate
```

### Workflow 3: CI/CD Analysis
```bash
# Load pre-indexed dependencies
cgc load fastapi.cgc
cgc load sqlalchemy.cgc

# Index your code
cgc index ./my-api

# Analyze
cgc analyze deps my_api
cgc analyze complexity --threshold 10
```

### Workflow 4: Educational Exploration
```bash
# Load famous codebase
cgc load django.cgc

# Explore
cgc find name authenticate
cgc analyze callers authenticate
cgc analyze chain login authenticate --depth 10
```

## 🎯 Bundle Naming Convention

```
<repo-name>-<version>-<commit>.cgc
```

Examples:
- `numpy-1.26.4-a1b2c3d.cgc`
- `pandas-2.1.0-xyz789.cgc`
- `my-project-v1.0.0-abc123.cgc`

## 📈 Bundle Statistics

After export, check stats:
```bash
unzip -p bundle.cgc stats.json | jq
```

Output:
```json
{
  "total_nodes": 15234,
  "total_edges": 42156,
  "files": 1342,
  "nodes_by_type": {
    "Function": 8211,
    "Class": 942,
    "File": 1342,
    "Module": 156
  },
  "edges_by_type": {
    "CALLS": 25432,
    "INHERITS": 1234,
    "IMPORTS": 5678
  }
}
```

## 🔐 Security Best Practices

```bash
# Always verify bundle source
unzip -p bundle.cgc metadata.json | jq .repo

# Check commit hash matches official repo
unzip -p bundle.cgc metadata.json | jq .commit

# Use --clear cautiously (deletes existing data)
cgc load bundle.cgc --clear  # Only if you're sure!

# Keep backups before importing
cgc export backup.cgc  # Backup current state
cgc load new-bundle.cgc  # Then load new bundle
```

## 🐛 Troubleshooting

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
# For very large bundles, be patient
# Import happens in batches of 1000 nodes

# Monitor progress in logs
cgc load large-bundle.cgc 2>&1 | tee import.log
```

### Version Mismatch
```bash
# Check your CGC version
cgc --version

# Check bundle version
unzip -p bundle.cgc metadata.json | jq .cgc_version

# Update if needed
pip install --upgrade codegraphcontext
```

## 📚 Available Pre-indexed Bundles

| Repository | Description | Typical Size |
|------------|-------------|--------------|
| **numpy** | Scientific computing | ~50MB |
| **pandas** | Data analysis | ~80MB |
| **fastapi** | Web framework | ~15MB |
| **requests** | HTTP library | ~10MB |
| **flask** | Web framework | ~12MB |

Download from: [GitHub Releases](https://github.com/Shashankss1205/CodeGraphContext/releases)

## 🔗 Related Commands

```bash
# Index management
cgc index .              # Index current directory
cgc list                 # List indexed repos
cgc delete /path/to/repo # Delete indexed repo
cgc stats                # Show statistics

# Database management
cgc config db neo4j      # Switch to Neo4j
cgc config db falkordb   # Switch to FalkorDB
cgc clean                # Clean orphaned nodes

# Analysis
cgc find name <name>     # Find by name
cgc analyze callers <fn> # Find callers
cgc analyze deps <mod>   # Analyze dependencies
```

## 💡 Pro Tips

1. **Use bundles for onboarding** - New team members get instant context
2. **Create bundles before major refactors** - Easy rollback if needed
3. **Share bundles instead of indexing instructions** - Consistent results
4. **Use version tags in bundle names** - Track what version you're analyzing
5. **Combine multiple bundles** - Load numpy, pandas, scikit-learn together

## 📖 Documentation

- **Full Guide:** `docs/BUNDLES.md`
- **Architecture:** `docs/BUNDLE_ARCHITECTURE.md`
- **Implementation:** `docs/BUNDLE_IMPLEMENTATION.md`
- **CLI Reference:** `CLI_Commands.md`

---

**Questions?** Open an issue on [GitHub](https://github.com/Shashankss1205/CodeGraphContext/issues)
