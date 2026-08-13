# CodeGraphContext Bundles

> **📖 Comprehensive Documentation:** For complete information about bundles, including detailed guides, examples, advanced usage, and troubleshooting, please see the [Bundle Guide](./docs/guides/bundles.md) in the documentation.

## Quick Overview

CodeGraphContext Bundles (`.cgc` files) are **portable, pre-indexed graph snapshots** that enable instant loading of code structures without re-parsing. They work like "npm packages for code knowledge graphs."

### Core Commands

**Export** (package your indexed code):
```bash
cgc bundle export my-project.cgc --repo /path/to/project
```

**Import** (load a bundle):
```bash
cgc bundle import my-project.cgc
```

**Registry** (access pre-indexed bundles):
```bash
cgc registry search flask    # Search for available packages
cgc bundle load flask         # Download and load
cgc registry list             # View all available
cgc registry request <url>    # Request on-demand builds
```

### Key Benefits

- ⚡ **Instant Loading** - Load in seconds instead of hours
- 🎯 **Pre-analyzed** - All code relationships already computed
- 📦 **Portable** - Works across any CodeGraphContext installation
- 🔍 **AI Ready** - Integrate with AI assistants immediately

### Use Cases

- **AI Assistant Context** - Load libraries for AI-powered development
- **CI/CD Pipelines** - Pre-index dependencies for analysis
- **Education** - Share pre-indexed famous codebases
- **Research** - Compare code structure evolution
- **Team Collaboration** - Distribute code graphs across teams

---

## Learn More

👉 **[Read the Full Bundle Guide →](./docs/guides/bundles.md)**

The guide includes:
- Detailed bundle structure and file formats
- Step-by-step creation and import procedures
- Available pre-indexed public bundles
- Advanced usage patterns (combining, versioning, custom registries)
- Bundle inspection and validation
- Security considerations and best practices
- Troubleshooting and common issues
- Python API reference
- Roadmap and future features
