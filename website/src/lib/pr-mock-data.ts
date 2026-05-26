export interface PRNode {
  id: string;
  name: string;
  type: string;
  file: string;
  prZone: 'direct' | 'primary' | 'secondary' | 'none';
  status: 'modified' | 'added' | 'deleted' | 'unchanged' | 'orphaned';
  complexityDelta?: number;
  fileChurn?: number;
  layer?: 'UI' | 'Business Logic' | 'Data Access' | 'DevOps / Configuration';
  isOrphan?: boolean;
  signatureChanged?: boolean;
  prevSignature?: string;
  newSignature?: string;
  affectedCallers?: number;
  gitDiff?: string;
  line_number?: number;
  val: number;
}

export interface PRLink {
  id: string;
  source: string;
  target: string;
  type: string;
  isViolation?: boolean;
  violationMessage?: string;
}

export interface PRGraphData {
  nodes: PRNode[];
  links: PRLink[];
  files: string[];
  fileContents: Record<string, string>;
  metadata: {
    prTitle: string;
    prNumber: number;
    author: string;
    sourceBranch: string;
    targetBranch: string;
    repo: string;
    commit: string;
    timestamp: string;
    directChanges: number;
    impactedCount: number;
    violationsCount: number;
    orphansCount: number;
  };
}

export const prMockData: PRGraphData = {
  metadata: {
    prTitle: "initial tests for docker setup",
    prNumber: 453,
    author: "Shashankss1205",
    sourceBranch: "docker-setup",
    targetBranch: "main",
    repo: "sktime/sktime-mcp",
    commit: "61f5f35e",
    timestamp: "2026-05-11T12:00:00Z",
    directChanges: 5,
    impactedCount: 2,
    violationsCount: 0,
    orphansCount: 0
  },
  files: [
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "Makefile",
    "README.md"
  ],
  fileContents: {
    "Dockerfile": `# Stage 1: Builder\nFROM python:3.12-slim AS builder\nENV DEBIAN_FRONTEND=noninteractive\nRUN apt-get update && apt-get install -y --no-install-recommends \\\n        build-essential \\\n        gfortran \\\n        libopenblas-dev \\\n    && rm -rf /var/lib/apt/lists/*\nWORKDIR /build\nCOPY pyproject.toml README.md LICENSE ./\nCOPY src/ src/\nRUN pip install --no-cache-dir --prefix=/install .\n\n# Stage 2: Runtime\nFROM python:3.12-slim AS runtime\nRUN apt-get update && apt-get install -y --no-install-recommends \\\n        libopenblas0 \\\n    && rm -rf /var/lib/apt/lists/*\nCOPY --from=builder /install /usr/local\nRUN useradd --create-home --shell /bin/bash mcp\nUSER mcp\nWORKDIR /home/mcp\nENV SKTIME_MCP_LOG_LEVEL=WARNING\nENV PYTHONUNBUFFERED=1\nHEALTHCHECK --interval=30s --timeout=5s --retries=3 \\\n    CMD python -c "import sktime_mcp; print('ok')" || exit 1\nENTRYPOINT ["sktime-mcp"]`,
    
    "docker-compose.yml": `services:\n  sktime-mcp:\n    build:\n      context: .\n      dockerfile: Dockerfile\n    image: sktime-mcp:latest\n    container_name: sktime-mcp\n    stdin_open: true\n    tty: false\n    environment:\n      - SKTIME_MCP_LOG_LEVEL=\${SKTIME_MCP_LOG_LEVEL:-WARNING}\n      - SKTIME_MCP_AUTO_FORMAT=\${SKTIME_MCP_AUTO_FORMAT:-true}\n      - SKTIME_MCP_JOB_MAX_AGE_HOURS=\${SKTIME_MCP_JOB_MAX_AGE_HOURS:-24}\n      - SKTIME_MCP_JOB_CLEANUP_INTERVAL=\${SKTIME_MCP_JOB_CLEANUP_INTERVAL:-3600}\n    volumes:\n      - sktime-models:/home/mcp/models\n\nvolumes:\n  sktime-models:\n    driver: local`,
    
    ".dockerignore": `# Version control\n.git\n.github\n# Python caches\n__pycache__\n*.pyc\n*.pyo\n# Virtual environments\n.venv\nvenv\nenv\n# Docker\nDockerfile\ndocker-compose.yml\n.dockerignore`,
    
    "Makefile": `docker-build:\n\tdocker build -t sktime-mcp .\n\ndocker-run: docker-build\n\tdocker run -i --rm sktime-mcp`,
    
    "README.md": `### 🐳 Docker\nRun without installing anything locally:\n\`\`\`bash\ndocker build -t sktime-mcp .\ndocker run -i sktime-mcp\n\`\`\``
  },
  nodes: [
    {
      id: "1",
      name: ".dockerignore",
      type: "File",
      file: ".dockerignore",
      prZone: "direct",
      status: "added",
      layer: "DevOps / Configuration",
      gitDiff: `@@ -0,0 +1,42 @@\n+# Version control\n+.git\n+.github\n+\n+# Python caches\n+__pycache__\n+*.pyc\n+*.pyo\n+.pytest_cache\n+.ruff_cache\n+\n+# Virtual environments\n+.venv\n+venv\n+env\n+\n+# IDE / editor\n+.vscode\n+.idea\n+*.swp\n+*.swo\n+\n+# Build artifacts\n+dist/\n+*.egg-info\n+build/\n+\n+# Documentation\n+docs/_build/\n+docs/build/\n+\n+# Project-specific ignores\n+mcp_server.log\n+.ignore/\n+TODO.md\n+.pre-commit-config.yaml\n+.readthedocs.yaml\n+\n+# Docker (prevent recursive context)\n+Dockerfile\n+docker-compose.yml\n+.dockerignore`,
      val: 3
    },
    {
      id: "2",
      name: "Dockerfile",
      type: "File",
      file: "Dockerfile",
      prZone: "direct",
      status: "added",
      layer: "DevOps / Configuration",
      gitDiff: `@@ -0,0 +1,65 @@\n+# Stage 1: Builder\n+FROM python:3.12-slim AS builder\n+ENV DEBIAN_FRONTEND=noninteractive\n+RUN apt-get update && apt-get install -y --no-install-recommends \\\n+        build-essential \\\n+        gfortran \\\n+        libopenblas-dev \\\n+    && rm -rf /var/lib/apt/lists/*\n+WORKDIR /build\n+COPY pyproject.toml README.md LICENSE ./\n+COPY src/ src/\n+RUN pip install --no-cache-dir --prefix=/install .\n+\n+# Stage 2: Runtime\n+FROM python:3.12-slim AS runtime\n+RUN apt-get update && apt-get install -y --no-install-recommends \\\n+        libopenblas0 \\\n+    && rm -rf /var/lib/apt/lists/*\n+COPY --from=builder /install /usr/local\n+RUN useradd --create-home --shell /bin/bash mcp\n+USER mcp\n+WORKDIR /home/mcp\n+ENV SKTIME_MCP_LOG_LEVEL=WARNING\n+ENV PYTHONUNBUFFERED=1\n+HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\\n+    CMD python -c "import sktime_mcp; print('ok')" || exit 1\n+ENTRYPOINT ["sktime-mcp"]`,
      val: 5
    },
    {
      id: "3",
      name: "docker-compose.yml",
      type: "File",
      file: "docker-compose.yml",
      prZone: "direct",
      status: "added",
      layer: "DevOps / Configuration",
      gitDiff: `@@ -0,0 +1,38 @@\n+services:\n+  sktime-mcp:\n+    build:\n+      context: .\n+      dockerfile: Dockerfile\n+    image: sktime-mcp:latest\n+    container_name: sktime-mcp\n+    stdin_open: true\n+    tty: false\n+    environment:\n+      - SKTIME_MCP_LOG_LEVEL=\${SKTIME_MCP_LOG_LEVEL:-WARNING}\n+      - SKTIME_MCP_AUTO_FORMAT=\${SKTIME_MCP_AUTO_FORMAT:-true}\n+      - SKTIME_MCP_JOB_MAX_AGE_HOURS=\${SKTIME_MCP_JOB_MAX_AGE_HOURS:-24}\n+      - SKTIME_MCP_JOB_CLEANUP_INTERVAL=\${SKTIME_MCP_JOB_CLEANUP_INTERVAL:-3600}\n+    volumes:\n+      - sktime-models:/home/mcp/models\n+\n+volumes:\n+  sktime-models:\n+    driver: local`,
      val: 4
    },
    {
      id: "4",
      name: "Makefile",
      type: "File",
      file: "Makefile",
      prZone: "direct",
      status: "modified",
      layer: "DevOps / Configuration",
      gitDiff: `@@ -1,12 +1,14 @@\n-.PHONY: check test lint format help format-fix install-hooks\n+.PHONY: check test lint format help format-fix install-hooks docker-build docker-run\n \n help:\n \t@echo "Available commands:"\n-\t@echo "  make check      - Run all CI checks (format check, lint, test)"\n-\t@echo "  make lint       - Run ruff linter"\n-\t@echo "  make format     - Run ruff format checker (check only)"\n-\t@echo "  make test       - Run pytest"\n-\t@echo "  make format-fix - Auto-fix formatting and fixable lint issues"\n+\t@echo "  make check        - Run all CI checks (format check, lint, test)"\n+\t@echo "  make lint         - Run ruff linter"\n+\t@echo "  make format       - Run ruff format checker (check only)"\n+\t@echo "  make test         - Run pytest"\n+\t@echo "  make format-fix   - Auto-fix formatting and fixable lint issues"\n+\t@echo "  make docker-build - Build the Docker image"\n+\t@echo "  make docker-run   - Run the MCP server in Docker (stdio)"\n \n check: format lint test\n \n@@ -26,3 +28,9 @@ format-fix:\n install-hooks:\n \tpip install pre-commit\n \tpre-commit install\n+\n+docker-build:\n+\tdocker build -t sktime-mcp .\n+\n+docker-run: docker-build\n+\tdocker run -i --rm sktime-mcp`,
      val: 3
    },
    {
      id: "5",
      name: "README.md",
      type: "File",
      file: "README.md",
      prZone: "direct",
      status: "modified",
      layer: "DevOps / Configuration",
      gitDiff: `@@ -57,6 +57,44 @@ For development (editable install from source):\n pip install -e ".[dev]"\n \`\`\`\n \n+### 🐳 Docker\n+\n+Run without installing anything locally (only Docker required):\n+\n+\`\`\`bash\n+# Build the image\n+docker build -t sktime-mcp .\n+\n+# Run the MCP server (stdio transport)\n+docker run -i sktime-mcp\n+\`\`\`\n+\n+Or use Docker Compose:\n+\n+\`\`\`bash\n+docker compose build\n+docker compose run sktime-mcp\n+\`\`\`\n+\n+**Claude Desktop** — use Docker as the MCP server command:\n+\n+\`\`\`json\n+{\n+  "mcpServers": {\n+    "sktime": {\n+      "command": "docker",\n+      "args": ["run", "-i", "--rm", "sktime-mcp"]\n+    }\n+  }\n+}\n+\`\`\`\n+\n+Environment variables can be passed at runtime:\n+\n+\`\`\`bash\n+docker run -i -e SKTIME_MCP_LOG_LEVEL=DEBUG sktime-mcp\n+\`\`\`\n+\n For a more detailed first-time setup flow, including MCP server verification and troubleshooting, see [Beginner Setup](#-beginner-setup-firsttime-users).\n \n ## 🧭 Beginner Setup (First‑Time Users)\n@@ -527,7 +565,10 @@ sktime-mcp/\n │   └── tools/              # MCP tool implementations\n ├── docs/                   # Sphinx documentation source\n ├── examples/               # Usage examples\n-└── tests/                  # Test suite\n+├── tests/                  # Test suite\n+├── Dockerfile              # Multi-stage container build\n+├── docker-compose.yml      # Compose service definition\n+└── .dockerignore           # Docker build context filter\n \`\`\`\n \n ## 🧪 Running Tests`,
      val: 4
    },
    {
      id: "6",
      name: "sktime-mcp (Entrypoint)",
      type: "Function",
      file: "pyproject.toml",
      prZone: "primary",
      status: "unchanged",
      layer: "Business Logic",
      val: 4
    },
    {
      id: "7",
      name: "MCPServer",
      type: "Class",
      file: "src/sktime_mcp/server.py",
      prZone: "secondary",
      status: "unchanged",
      layer: "Business Logic",
      val: 4
    }
  ],
  links: [
    {
      id: "e1",
      source: "3",
      target: "2",
      type: "BUILDS"
    },
    {
      id: "e2",
      source: "2",
      target: "6",
      type: "RUNS"
    },
    {
      id: "e3",
      source: "6",
      target: "7",
      type: "CALLS"
    },
    {
      id: "e4",
      source: "4",
      target: "2",
      type: "TRIGGERS"
    },
    {
      id: "e5",
      source: "5",
      target: "3",
      type: "DOCUMENTS"
    }
  ]
};
