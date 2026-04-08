# Patch Implementation Checklist

Auto-generated from source checks.

## src/codegraphcontext/server.py
- [x] `def _read_request_blocking(self) -> Tuple[Optional[dict], Optional[str]]:`
- [x] `def _write_response(self, response: dict, framing: Optional[str]) -> None:`
- [x] `if ctx.database and not os.environ.get('CGC_RUNTIME_DB_TYPE'):`

## src/codegraphcontext/tools/graph_builder.py
- [x] `if backend_type == 'kuzudb':`
- [x] `function_code_search_fts`
- [x] `is_falkordb = backend_type in ('falkordb', 'falkordb-remote')`

## src/codegraphcontext/tools/code_finder.py
- [x] `self._is_kuzu = self._backend_type == 'kuzudb'`
- [x] `def _ensure_kuzu_fts_indexes(self) -> None:`
- [x] `def _query_kuzu_fts(`
- [x] `def _find_by_content_kuzu(`

## src/codegraphcontext/cli/cli_helpers.py
- [x] `def watch_service_install_helper(`
- [x] `def watch_service_status_helper(unit_name: str):`
- [x] `def watch_service_stop_helper(unit_name: str, disable: bool = False):`
- [x] `def watch_service_remove_helper(unit_name: str, keep_unit_file: bool = False):`

## src/codegraphcontext/cli/main.py
- [x] `@app.command(name="watch-service-install")`
- [x] `@app.command(name="watch-service-status")`
- [x] `@app.command(name="watch-service-stop")`
- [x] `@app.command(name="watch-service-remove")`

## scripts/validate_patch_and_runtime.py
- [x] `def runtime_validate() -> None:`
- [x] `def cli_surface_validate() -> None:`
- [x] `VALIDATION_OK`

Overall status: PASS
