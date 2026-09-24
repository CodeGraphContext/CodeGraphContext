#!/bin/bash
# Quick-start script for running CGC via Docker
# Usage:
#   ./scripts/docker-run.sh index /path/to/repo
#   ./scripts/docker-run.sh analyze callers my_function
#   ./scripts/docker-run.sh mcp start
#   ./scripts/docker-run.sh shell
#   ./scripts/docker-run.sh viz

IMAGE="${CGC_DOCKER_IMAGE:-codegraphcontext/codegraphcontext:latest}"

case "$1" in
    shell)
        docker run -it --rm \
            -v "$(pwd):/workspace" \
            -v cgc-data:/home/cgc/.codegraphcontext \
            "$IMAGE" bash
        ;;
    mcp)
        shift
        docker run -i --rm \
            -v "$(pwd):/workspace" \
            -v cgc-data:/home/cgc/.codegraphcontext \
            -e CGC_MODE=mcp \
            "$IMAGE" "$@"
        ;;
    viz)
        docker run -d --rm \
            -v "$(pwd):/workspace" \
            -v cgc-data:/home/cgc/.codegraphcontext \
            -p 8080:8080 \
            -e CGC_MODE=viz \
            --name cgc-viz \
            "$IMAGE"
        echo "Viz server running at http://localhost:8080"
        ;;
    *)
        docker run -it --rm \
            -v "$(pwd):/workspace" \
            -v cgc-data:/home/cgc/.codegraphcontext \
            "$IMAGE" cgc "$@"
        ;;
esac
