#!/bin/bash
set -e

# Signal handling for graceful shutdown
trap 'echo "Shutting down CGC..."; kill -TERM $PID; wait $PID' SIGTERM SIGINT

# If the first argument is a cgc subcommand, prepend 'cgc'
if cgc "$1" --help &>/dev/null 2>&1; then
    set -- cgc "$@"
fi

# Mode-based startup via CGC_MODE env var
case "${CGC_MODE:-cli}" in
    mcp)
        echo "Starting CGC MCP Server..."
        exec cgc mcp start "$@"
        ;;
    viz)
        echo "Starting CGC Visualization Server on :8080..."
        exec cgc viz serve --host 0.0.0.0 --port 8080 "$@"
        ;;
    shell)
        exec /bin/bash
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
