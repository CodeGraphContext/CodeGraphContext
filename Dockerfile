# Multi-stage build for CodeGraphContext
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building
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

# Production stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/cgc /usr/local/bin/cgc
COPY --from=builder /usr/local/bin/codegraphcontext /usr/local/bin/codegraphcontext

# Copy source code
COPY --from=builder /app/src /app/src

# Create directory for code to be indexed
RUN mkdir -p /workspace

# Create directory for database and config
RUN mkdir -p /root/.codegraphcontext

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CGC_HOME=/root/.codegraphcontext

# Expose port for potential web interface (future use)
EXPOSE 8080

# Default working directory for user code
WORKDIR /workspace

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD cgc --version || exit 1

# Default command - show help
CMD ["cgc", "help"]
