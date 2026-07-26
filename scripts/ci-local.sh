#!/usr/bin/env bash
#
# Run the GitHub Actions checks locally, the same way CI runs them.
#
# The point is to catch a red CI before pushing. Each job below mirrors a
# workflow in .github/workflows/ step for step — same install command, same
# test invocation, same Python versions — rather than approximating it with a
# bare `pytest`, which is how divergences get missed.
#
#   ./scripts/ci-local.sh              # lint + build-test on every available Python
#   ./scripts/ci-local.sh lint         # Lint            (lint.yml)
#   ./scripts/ci-local.sh test         # Build Test      (test.yml)
#   ./scripts/ci-local.sh test 3.12    # Build Test, one Python only
#   ./scripts/ci-local.sh e2e          # End-to-end      (e2e-tests.yml)  ** see warning **
#   ./scripts/ci-local.sh parity       # Database Parity (db-parity-check.yml)
#
# Missing interpreters are fetched with `uv python install` when uv is present;
# otherwise that leg is skipped with a note. Nothing here needs sudo.
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_ROOT="${CGC_CI_LOCAL_WORKDIR:-${TMPDIR:-/tmp}/cgc-ci-local}"
# Matches the matrix in .github/workflows/test.yml
PY_VERSIONS=("3.12" "3.13" "3.14")

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; DIM=$'\033[2m'; NC=$'\033[0m'
FAILURES=()

log()  { printf '%s\n' "$*"; }
head1() { printf '\n%s==> %s%s\n' "$YELLOW" "$*" "$NC"; }
ok()   { printf '%s  PASS%s  %s\n' "$GREEN" "$NC" "$*"; }
bad()  { printf '%s  FAIL%s  %s\n' "$RED" "$NC" "$*"; FAILURES+=("$1"); }

find_python() {
    # Echo a usable interpreter for $1, fetching it with uv if necessary.
    local want="$1" exe
    exe="$(command -v "python${want}" 2>/dev/null)" && { printf '%s' "$exe"; return 0; }
    if command -v uv >/dev/null 2>&1; then
        uv python install "$want" >/dev/null 2>&1 || true
        exe="$(uv python find "$want" 2>/dev/null)" && [ -x "$exe" ] && { printf '%s' "$exe"; return 0; }
    fi
    return 1
}

# ---------------------------------------------------------------- Lint -------
run_lint() {
    head1 "Lint  (lint.yml)"
    local py; py="$(find_python 3.12 || command -v python3)"
    local venv="$WORK_ROOT/lint-venv"
    [ -d "$venv" ] || "$py" -m venv "$venv"
    "$venv/bin/python" -m pip install --upgrade pip ruff -q || { bad "Lint (install)"; return; }

    # Keep these two lists byte-identical to lint.yml. They differ deliberately:
    # database_embedded_kuzu.py is checked but not format-checked.
    local check_files=(
        src/codegraphcontext/core/graph_query.py
        src/codegraphcontext/core/database_kuzu.py
        src/codegraphcontext/core/database_ladybug.py
        src/codegraphcontext/core/database_embedded_kuzu.py
        src/codegraphcontext/tools/indexing/embeddings.py
        src/codegraphcontext/tools/indexing/vector_resolver.py
    )
    local format_files=(
        src/codegraphcontext/core/graph_query.py
        src/codegraphcontext/core/database_kuzu.py
        src/codegraphcontext/core/database_ladybug.py
        src/codegraphcontext/tools/indexing/embeddings.py
        src/codegraphcontext/tools/indexing/vector_resolver.py
    )

    ( cd "$REPO_ROOT" && "$venv/bin/ruff" check "${check_files[@]}" --select F,E9 ) \
        && ok "ruff check" || bad "Lint (ruff check)"
    ( cd "$REPO_ROOT" && "$venv/bin/ruff" format --check "${format_files[@]}" ) \
        && ok "ruff format --check" || bad "Lint (ruff format)"
}

# ----------------------------------------------------------- Build Test ------
run_build_test() {
    local only="${1:-}"
    for v in "${PY_VERSIONS[@]}"; do
        [ -n "$only" ] && [ "$only" != "$v" ] && continue
        head1 "Build Test  (test.yml)  Python $v"

        local py
        if ! py="$(find_python "$v")"; then
            log "${DIM}  skipped: no python$v and uv could not provide it${NC}"
            continue
        fi

        local work="$WORK_ROOT/test-$v"
        rm -rf "$work"; mkdir -p "$work/home"
        # actions/checkout gives a clean tree; copy tracked files only so local
        # build artefacts and stray files cannot influence the result.
        git -C "$REPO_ROOT" archive --format=tar HEAD | ( mkdir -p "$work/repo" && tar -x -C "$work/repo" )

        (
            cd "$work/repo" || exit 1
            # Isolated HOME: CGC writes config and embedded databases under
            # ~/.codegraphcontext, and leaking that between runs (or into the
            # developer's real config) changes results.
            export HOME="$work/home"
            "$py" -m venv .venv                                     || exit 1
            ./.venv/bin/python -m pip install --upgrade pip -q      || exit 1
            ./.venv/bin/python -m pip install build -q              || exit 1
            ./.venv/bin/python -m pip install '.[dev,parsing]' -q   || exit 1
            ./.venv/bin/python -m build                             || exit 1
            export PYTHONPATH="${PYTHONPATH:-}:$work/repo/src"
            # run_tests.sh invokes a bare `pytest`, which resolves through PATH.
            # On a GitHub runner setup-python has already put the environment's
            # bin dir first; locally it has not, so without this the system
            # pytest is used and the run dies with ModuleNotFoundError.
            export PATH="$work/repo/.venv/bin:$PATH"
            chmod +x tests/run_tests.sh
            ./tests/run_tests.sh fast
        ) > "$work/output.log" 2>&1

        local rc=$?
        local summary
        summary="$(grep -oE '[0-9]+ (passed|failed)[^=]*' "$work/output.log" | tail -1)"
        if [ $rc -eq 0 ]; then
            ok "Python $v  ${summary:-completed}"
        else
            bad "Build Test (Python $v)"
            log "${DIM}    log: $work/output.log${NC}"
            grep -E '^(FAILED|ERROR) ' "$work/output.log" | head -10 | sed 's/^/    /'
        fi
    done
}

# ------------------------------------------------------- E2E and parity ------
warn_destructive_neo4j() {
    cat <<'WARN'

  !! tests/e2e/test_verify_databases_parity.py runs

         MATCH (n) DETACH DELETE n

     against NEO4J_URI, which defaults to bolt://localhost:7687.
     If you have a Neo4j there with data you care about, IT WILL BE WIPED.

     Point NEO4J_URI at a throwaway instance first, e.g.

         docker run -d --name cgc-neo4j-test -p 17687:7687 -p 17474:7474 \
             -e NEO4J_AUTH=neo4j/12345678 neo4j:5.12.0-community
         export NEO4J_URI=bolt://localhost:17687 \
                NEO4J_USERNAME=neo4j NEO4J_PASSWORD=12345678

WARN
}

confirm_or_abort() {
    warn_destructive_neo4j
    if [ "${CGC_CI_LOCAL_YES:-}" = "1" ]; then
        log "  CGC_CI_LOCAL_YES=1 set; continuing."
        return 0
    fi
    read -r -p "  NEO4J_URI=${NEO4J_URI:-bolt://localhost:7687} — continue? [y/N] " reply
    case "$reply" in [yY]*) return 0 ;; *) log "  aborted."; return 1 ;; esac
}

run_suite() {   # $1 = label, $2 = run_tests.sh arg or pytest path
    local label="$1" target="$2"
    head1 "$label"
    confirm_or_abort || return 0

    local py; py="$(find_python 3.14 || find_python 3.12 || command -v python3)"
    local work="$WORK_ROOT/${label// /-}"
    rm -rf "$work"; mkdir -p "$work/home"
    git -C "$REPO_ROOT" archive --format=tar HEAD | ( mkdir -p "$work/repo" && tar -x -C "$work/repo" )
    (
        cd "$work/repo" || exit 1
        export HOME="$work/home"
        "$py" -m venv .venv                                  || exit 1
        ./.venv/bin/python -m pip install --upgrade pip -q   || exit 1
        ./.venv/bin/python -m pip install -e '.[dev]' -q     || exit 1
        if [ "$target" = "e2e" ]; then
            chmod +x tests/run_tests.sh && ./tests/run_tests.sh e2e
        else
            ./.venv/bin/pytest "$target" -v -s
        fi
    ) 2>&1 | tee "$work/output.log"

    if [ "${PIPESTATUS[0]}" -eq 0 ]; then ok "$label"; else bad "$label"; fi
}

# ------------------------------------------------------------------ main -----
mkdir -p "$WORK_ROOT"
case "${1:-all}" in
    lint)   run_lint ;;
    test)   run_build_test "${2:-}" ;;
    e2e)    run_suite "End-to-end Tests" e2e ;;
    parity) run_suite "Database Parity Check" tests/e2e/test_verify_databases_parity.py ;;
    all)    run_lint; run_build_test ;;
    -h|--help|help)
        sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        exit 0 ;;
    *)
        log "${RED}unknown target: $1${NC}  (try: lint | test | e2e | parity | all)"
        exit 2 ;;
esac

printf '\n%s\n' "------------------------------------------------------------"
if [ ${#FAILURES[@]} -eq 0 ]; then
    printf '%sAll selected CI checks passed.%s\n' "$GREEN" "$NC"
    exit 0
fi
printf '%s%d check(s) failed:%s\n' "$RED" "${#FAILURES[@]}" "$NC"
printf '  - %s\n' "${FAILURES[@]}"
exit 1
