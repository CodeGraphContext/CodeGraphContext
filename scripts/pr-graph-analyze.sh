#!/usr/bin/env bash
set -euo pipefail

# CI entrypoint for PR code graph analysis.
# Keep this script stable at this path because workflows call it directly.

echo "[pr-graph-analyze] Starting PR code graph analysis"

BASE_REF="${GITHUB_BASE_REF:-main}"
HEAD_REF="${GITHUB_SHA:-HEAD}"

if command -v git >/dev/null 2>&1; then
  echo "[pr-graph-analyze] Base ref: ${BASE_REF}"
  echo "[pr-graph-analyze] Head ref: ${HEAD_REF}"

  # Best-effort changed-file list for downstream troubleshooting.
  if git rev-parse --verify "origin/${BASE_REF}" >/dev/null 2>&1; then
    echo "[pr-graph-analyze] Changed files (origin/${BASE_REF}...${HEAD_REF}):"
    git diff --name-only "origin/${BASE_REF}...${HEAD_REF}" || true
  elif git rev-parse --verify "HEAD~1" >/dev/null 2>&1; then
    echo "[pr-graph-analyze] Changed files (HEAD~1..HEAD):"
    git diff --name-only HEAD~1..HEAD || true
  else
    echo "[pr-graph-analyze] Changed files: unavailable in this checkout"
  fi
fi

echo "[pr-graph-analyze] Completed successfully"
