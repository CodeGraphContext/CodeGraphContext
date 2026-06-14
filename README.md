# CodeGraphContext (CGC)

**Turn code repositories into a queryable graph for AI agents.**

CodeGraphContext is an MCP server and CLI toolkit that indexes local code into a graph database. Use it to inspect relationships across a repository, run code-quality queries, generate visualizations, or give AI assistants structured context about your codebase.

<p align="center">
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI Downloads">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP Compatible">
  <a href="https://discord.gg/VCwUdCnn">
    <img src="https://img.shields.io/discord/1421769154507309150?label=Discord&logo=discord&logoColor=white&style=flat-square" alt="Discord">
  </a>
  <br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers">
    <img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Stars">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/network/members">
    <img src="https://img.shields.io/github/forks/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Forks">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/issues">
    <img src="https://img.shields.io/github/issues-raw/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Issues">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/pulls">
    <img src="https://img.shields.io/github/issues-pr/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="PRs">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Contributors">
  </a>
  <br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E Tests">
  </a>
  <a href="https://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="Website">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube Demo">
  </a>
</p>

## Translations

- [English](README.md)
- [Chinese](docs/translations/README.zh-CN.md)
- [Korean](docs/translations/README.kor.md)
- [Ukrainian](docs/translations/README.uk.md)
- [Russian](docs/translations/README.ru-RU.md)
- [Japanese](docs/translations/README.ja.md)

Want to add another language? Open an issue or pull request on [GitHub](https://github.com/CodeGraphContext/CodeGraphContext/issues).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [MCP Server](#mcp-server)
- [Configuration](#configuration)
- [Supported Languages](#supported-languages)
- [Database Backends](#database-backends)
- [SCIP Indexing](#scip-indexing)
- [Contributing](#contributing)
- [License](#license)

## Overview

CodeGraphContext builds a code graph from a local repository and exposes it through two main workflows:

- **CLI toolkit**: index repositories, query symbols, analyze relationships, detect dead code, and generate visual graph reports.
- **MCP server**: connect the same graph context to AI IDEs and assistants so they can answer codebase questions with repository-aware context.

Typical use cases include impact analysis, call-chain exploration, AI-assisted code understanding, onboarding to unfamiliar repositories, and local code-quality checks.

## Features

- **Code indexing**: Parse source files and build a searchable graph of functions, classes, methods, imports, calls, parameters, and inheritance.
- **Relationship analysis**: Query callers, callees, class trees, dependency paths, complexity, and dead code.
- **MCP integration**: Run an MCP server for VS Code, Cursor, Windsurf, Zed, Claude, Gemini CLI, ChatGPT Codex, Cline, RooCode, Amazon Q Developer, Kiro, Goose, and OpenCode.
- **Pre-indexed bundles**: Load `.cgc` bundles for known repositories without re-indexing from source.
- **Live watching**: Keep the graph synchronized with file changes by running `codegraphcontext watch`.
- **Interactive visualization**: Generate standalone HTML graph views with searchable nodes and relationship panels.
- **Multi-language support**: Analyze 23 programming languages with Tree-sitter, with optional SCIP support for richer C, C++, and C# indexing.
- **Flexible storage**: Use FalkorDB Lite, KuzuDB, LadybugDB, FalkorDB Remote, Nornic DB, or Neo4j.

## Experience CGC

### Installation and CLI

Install the package and start querying a repository from your terminal.

![Install and unlock the CLI instantly](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)

### Indexing in Seconds

Build a code graph from a local repository.

![Indexing using an MCP client](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### Powering Your AI Assistant

Use natural language through an MCP client to inspect code relationships.

![Using the MCP server](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

## Tech Stack

| Area | Technology |
| --- | --- |
| Runtime | Python 3.10-3.14 |
| CLI | Typer, Rich, InquirerPy |
| Parsing | Tree-sitter, tree-sitter-language-pack, optional SCIP indexers |
| MCP and API | MCP, FastAPI, Uvicorn |
| Graph backends | FalkorDB Lite, KuzuDB, LadybugDB, FalkorDB Remote, Nornic DB, Neo4j |
| Packaging | PyPI package with `codegraphcontext` and `cgc` console scripts |

## Installation

### Prerequisites

- Python 3.10 or later
- `pip`
- Git, if you want to clone repositories before indexing them

Verify Python is available:

```bash
python --version
```

### Install from PyPI

```bash
pip install codegraphcontext
```

Confirm the CLI is installed:

```bash
codegraphcontext --help
```

The short alias is also available:

```bash
cgc --help
```

If your shell cannot find the command after installation, run the post-install path helper:

```bash
curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
```

## Usage

### Quick Start

```bash
# Index the current repository
codegraphcontext index .

# List indexed repositories
codegraphcontext list

# Find dead code
codegraphcontext analyze dead-code
```

If `codegraphcontext list` shows your indexed repository, the local setup is ready.

### Common CLI Commands

```bash
# Index a repository
codegraphcontext index /path/to/repo

# Watch a repository and update the graph after file changes
codegraphcontext watch /path/to/repo

# Analyze who calls a function
codegraphcontext analyze callers my_function

# Find complex code
codegraphcontext analyze complexity --threshold 10

# Generate an interactive visualization
codegraphcontext analyze calls my_function --viz

# Explore class hierarchies
codegraphcontext analyze tree MyClass --viz

# Search symbols or content
codegraphcontext find pattern "Auth"
```

See the [complete CLI reference](docs/CLI_COMPLETE_REFERENCE.md) for all commands and options.

### Visualization

Visualization commands create standalone HTML reports that can be opened in a browser. They include searchable graph nodes, detailed side panels, and layouts for call graphs, class trees, and search results.

```bash
codegraphcontext analyze calls my_function --viz
codegraphcontext analyze tree MyClass --viz
codegraphcontext find pattern "Auth" --viz
```

## MCP Server

Use the MCP setup wizard to configure supported editors and AI assistants:

```bash
codegraphcontext mcp setup
```

The wizard can configure VS Code, Cursor, Windsurf, Zed, Claude, Gemini CLI, ChatGPT Codex, Cline, RooCode, Amazon Q Developer, Kiro, Goose, and OpenCode. It writes the MCP configuration and stores database settings in `~/.codegraphcontext/.env`.

Start the MCP server:

```bash
codegraphcontext mcp start
```

### Manual MCP Configuration

If your client is not configured automatically, add this server entry to your MCP client settings:

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "codegraphcontext",
      "args": ["mcp", "start"],
      "env": {
        "NEO4J_URI": "YOUR_NEO4J_URI",
        "NEO4J_USERNAME": "YOUR_NEO4J_USERNAME",
        "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD"
      },
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

For `pipx` installs, use `pipx run`:

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "pipx",
      "args": ["run", "codegraphcontext", "mcp", "start"],
      "env": {
        "NEO4J_URI": "YOUR_NEO4J_URI",
        "NEO4J_USERNAME": "YOUR_NEO4J_USERNAME",
        "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD"
      },
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

OpenCode users can also follow the [OpenCode MCP guide](https://opencode.ai/docs/ko/mcp-servers/#_top).

### Example Prompts

After indexing a repository and starting the MCP server, ask your assistant questions such as:

- "Where is the `process_payment` function?"
- "What calls `get_user_by_id`?"
- "If I change `calculate_tax`, what files might be affected?"
- "Show the inheritance hierarchy for `BaseController`."
- "Find all implementations of `render`."
- "Trace the call chain from `main` to `process_data`."
- "Which files import `requests`?"
- "Is there any dead or unused code?"

## Configuration

### Ignoring Files

Create a `.cgcignore` file in the repository root to skip files and directories during indexing. The syntax matches `.gitignore`.

```gitignore
# Ignore build artifacts
/build/
/dist/

# Ignore dependencies
/node_modules/
/vendor/

# Ignore logs
*.log
```

### Database Setup

CodeGraphContext uses an embedded graph database by default. Most users can install the package and run `codegraphcontext index .` without additional database setup.

For an external Neo4j server, run:

```bash
codegraphcontext neo4j setup
```

## Supported Languages

CodeGraphContext parses and analyzes these languages:

| Language | Language | Language |
| --- | --- | --- |
| Python | JavaScript | TypeScript |
| Java | C | C++ |
| C# | Go | Rust |
| Ruby | PHP | Swift |
| Kotlin | Dart | Perl |
| Lua | Scala | Haskell |
| Elixir | Emacs Lisp | HTML |
| CSS | TSX | |

## Database Backends

| Feature | KuzuDB | LadybugDB | FalkorDB Lite | Neo4j / Nornic DB |
| --- | --- | --- | --- | --- |
| Typical use | Cross-platform embedded backend | Optional embedded backend | Unix local development | External or cloud graph database |
| Setup | Zero-config | Zero-config | Zero-config / in-process | Docker, native server, or hosted service |
| Platform | Windows, macOS, Linux | Windows, macOS, Linux | Linux, macOS, WSL | Windows, macOS, Linux |
| Requirement | `pip install kuzu` | `pip install ladybug` | `pip install falkordblite` | Neo4j Server, Docker, or Nornic Cloud |
| Persistence | Disk-backed | Disk-backed | Disk-backed | Server-backed |

## SCIP Indexing

Set `SCIP_INDEXER=true` in `~/.codegraphcontext/.env` to enable external SCIP indexers for languages where they provide more accurate calls and inheritance than Tree-sitter heuristics alone.

- **C and C++** use `scip-clang` and require a `compile_commands.json` compilation database. Generate one with CMake (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`) or tools such as [Bear](https://github.com/rizsotto/Bear).
- **C#** uses `scip-dotnet` and requires a normal `.csproj` or `.sln` with a successful restore.

SCIP works independently of the selected graph backend.

## Project Links

- Website: [codegraphcontext.vercel.app](https://codegraphcontext.vercel.app/)
- CLI reference: [docs/CLI_COMPLETE_REFERENCE.md](docs/CLI_COMPLETE_REFERENCE.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Bundles: [docs/BUNDLES.md](docs/BUNDLES.md)
- Roadmap: [ROADMAP.md](ROADMAP.md)
- Security policy: [.github/SECURITY.md](.github/SECURITY.md)

## Contributing

Contributions are welcome. Read [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) for setup, development, and pull request guidelines.

Useful local checks include:

```bash
python -m pytest
python -m black --check .
python -m ruff check .
```

For documentation changes, keep examples copyable and verify that referenced files and links exist.

## Used By

CodeGraphContext is being explored for static code analysis in AI assistants, graph-based project visualization, dead-code detection, complexity analysis, and repository onboarding.

If you use CodeGraphContext in your project, open a pull request and add it here.

## Maintainer

CodeGraphContext is created and maintained by [Shashank Shekhar Singh](https://github.com/Shashankss1205).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

## License

CodeGraphContext is released under the [MIT License](LICENSE).
