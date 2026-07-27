#!/bin/bash
set -e

# If the first arg starts with '-' or is a known cgc subcommand, prepend 'cgc'
if [ "${1#-}" != "$1" ]; then
    set -- cgc "$@"
else
    case "$1" in
        index|update|clean|stats|setup-scip|delete|report|visualize|list|add-package|watch|unwatch|watching|query|help|version|mcp|neo4j|context|config|bundle|hook|registry|api|find|analyze|datasource|m|n|i|ls|rm|v|w|export|load)
            set -- cgc "$@"
            ;;
    esac
fi

# Mode-based startup via CGC_MODE env var
case "${CGC_MODE:-cli}" in
    mcp)
        echo "Starting CGC MCP Server..."
        exec cgc mcp start "$@"
        ;;
    viz)
        echo "Starting CGC Visualization Server on :8080..."
        exec cgc visualize --host 0.0.0.0 --port 8080 "$@"
        ;;
    shell)
        exec /bin/bash "$@"
        ;;
    cli|*)
        # Pass through to cgc CLI or whatever command was given
        if [ $# -eq 0 ]; then
            exec cgc help
        else
            exec "$@"
        fi
        ;;
esac
