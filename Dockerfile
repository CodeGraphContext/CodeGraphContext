# Stage 1: Build the website frontend
FROM node:20-slim AS web-builder

WORKDIR /app/website

# Install dependencies first for better caching
COPY website/package.json website/package-lock.json* ./
RUN npm ci || npm install

# Copy website source and build
COPY website/ ./
RUN npm run build

# Stage 2: Python builder
FROM python:3.12-slim AS python-builder

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Stage 3: Production environment
FROM python:3.12-slim

# OCI Annotations
ARG CGC_VERSION=0.4.19
LABEL org.opencontainers.image.title="CodeGraphContext"
LABEL org.opencontainers.image.description="Turn code repositories into a queryable graph for AI agents"
LABEL org.opencontainers.image.url="https://github.com/CodeGraphContext/CodeGraphContext"
LABEL org.opencontainers.image.source="https://github.com/CodeGraphContext/CodeGraphContext"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="${CGC_VERSION}"

# Install runtime dependencies (git for code fetching, curl for healthchecks/tools)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd -r cgc && useradd -r -g cgc -u 1000 cgc

# Set working directories and permissions
RUN mkdir -p /workspace /home/cgc/.codegraphcontext && \
    chown -R cgc:cgc /workspace /home/cgc

# Copy built python packages and executables
COPY --from=python-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=python-builder /usr/local/bin/cgc /usr/local/bin/cgc
COPY --from=python-builder /usr/local/bin/codegraphcontext /usr/local/bin/codegraphcontext

# Copy source code (this contains the mcp server files, etc)
COPY --from=python-builder /app/src /app/src

# Copy built website into the viz/dist directory
COPY --from=web-builder /app/website/dist /app/src/codegraphcontext/viz/dist

# Set permissions for source code
RUN chown -R cgc:cgc /app/src

# Copy entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER cgc

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CGC_HOME=/home/cgc/.codegraphcontext
ENV PYTHONPATH=/app/src

# Expose port for the visualization server
EXPOSE 8080

# Default working directory for user code
WORKDIR /workspace

# Health check to verify CLI runs correctly
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["cgc", "--version"]

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["cgc", "help"]
