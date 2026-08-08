#!/usr/bin/env bash
#
# Build the visualizer frontend and sync it into the Python package so the
# wheel actually contains it.
#
# pyproject.toml already declares:
#     [tool.setuptools.package-data]
#     codegraphcontext = ["viz/dist/**/*"]
# and MANIFEST.in already has:
#     recursive-include src/codegraphcontext/viz/dist *
#
# ...but src/codegraphcontext/viz/dist is never produced, so every published
# wheel shipped without it and `cgc visualize`, `-V/--visual` and the MCP
# visualize_graph_query tool all failed. The CLI error message pointed users
# at this script, which did not exist.
#
# Run this before `python -m build`, or from the release workflow.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${REPO_ROOT}/website"
BUILD_OUTPUT="${FRONTEND_DIR}/dist"
TARGET_DIR="${REPO_ROOT}/src/codegraphcontext/viz/dist"

if [[ ! -f "${FRONTEND_DIR}/package.json" ]]; then
    echo "error: no frontend source at ${FRONTEND_DIR}" >&2
    exit 1
fi

echo "==> Building visualizer frontend in ${FRONTEND_DIR}"
cd "${FRONTEND_DIR}"
if [[ -f package-lock.json ]]; then
    npm ci
else
    npm install
fi
npm run build

if [[ ! -f "${BUILD_OUTPUT}/index.html" ]]; then
    echo "error: build produced no ${BUILD_OUTPUT}/index.html" >&2
    exit 1
fi

echo "==> Syncing ${BUILD_OUTPUT} -> ${TARGET_DIR}"
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
cp -R "${BUILD_OUTPUT}/." "${TARGET_DIR}/"

echo "==> Done. $(find "${TARGET_DIR}" -type f | wc -l) file(s) staged for packaging."
echo "    Verify with: python -m build && unzip -l dist/*.whl | grep viz/dist"
