"""
This module implements the live file-watching functionality using the `watchdog` library.
It observes directories for changes and triggers updates to the code graph.
"""

import os
import threading
from pathlib import Path
import typing

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

if typing.TYPE_CHECKING:
    from pathspec import PathSpec
    from ..tools.graph_builder import GraphBuilder
    from ..core.jobs import JobManager

from .cgcignore import build_ignore_spec
from ..tools.indexing.constants import DEFAULT_IGNORE_PATTERNS
from ..cli.config_manager import get_config_value
from ..utils.debug_log import debug_log, info_logger, error_logger, warning_logger


POLLING_ENV_VAR = "CGC_WATCH_POLLING"
TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


def should_use_polling_observer(use_polling: typing.Optional[bool] = None) -> bool:
    if use_polling is not None:
        return use_polling
    return os.getenv(POLLING_ENV_VAR, "").strip().lower() in TRUE_ENV_VALUES


class RepositoryEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        graph_builder: "GraphBuilder",
        repo_path: Path,
        debounce_interval=2.0,
        perform_initial_scan: bool = True,
        cgcignore_path: str = None,
        ignore_spec: "PathSpec" = None,
        sync_on_start: bool = False,
    ):
        super().__init__()
        self.graph_builder = graph_builder
        self.repo_path = repo_path.resolve()
        self.debounce_interval = debounce_interval
        self.timers = {}

        self.ignore_root = self.repo_path
        self.ignore_spec = ignore_spec
        self._load_ignore_spec(cgcignore_path)

        self.all_file_data = []
        self.imports_map = {}

        if sync_on_start:
            self.synchronize_with_disk()
        elif perform_initial_scan:
            self._initial_scan()

    def _load_ignore_spec(self, cgcignore_path: str = None) -> None:
        if self.ignore_spec is not None:
            return
        try:
            self.ignore_spec, resolved = build_ignore_spec(
                ignore_root=self.ignore_root,
                default_patterns=DEFAULT_IGNORE_PATTERNS,
                explicit_path=cgcignore_path,
            )
            if resolved:
                debug_log(f"Watcher using ignore file: {resolved}")
        except OSError as e:
            self.ignore_spec = None
            warning_logger(f"Could not load ignore rules: {e}")

    def _should_ignore(self, path: str | Path) -> bool:
        path_obj = Path(path).resolve()
        ignore_root = getattr(self, "ignore_root", self.repo_path)

        ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
        if ignore_dirs_str:
            ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}
            try:
                parts = {p.lower() for p in path_obj.relative_to(ignore_root).parent.parts}
                if parts.intersection(ignore_dirs):
                    return True
            except ValueError:
                pass

        ignore_spec = getattr(self, "ignore_spec", None)
        if not ignore_spec:
            return False

        try:
            rel = path_obj.relative_to(ignore_root).as_posix()
        except ValueError:
            return False

        return ignore_spec.match_file(rel)

    def _is_supported_code_file(self, path: str | Path) -> bool:
        path_obj = Path(path)
        return (
            path_obj.is_file()
            and path_obj.suffix in self.graph_builder.parsers
            and not self._should_ignore(path_obj)
        )

    def _iter_supported_files(self) -> list[Path]:
        from ..tools.indexing.discovery import discover_files_to_index

        supported = self.graph_builder.parsers.keys()
        files, _ = discover_files_to_index(
            self.repo_path,
            supported_extensions=set(supported),
        )
        return files

    def _initial_scan(self):
        info_logger(f"Initial scan: {self.repo_path}")
        all_files = self._iter_supported_files()

        self.imports_map = self.graph_builder.pre_scan_imports(all_files)

        for f in all_files:
            parsed = self.graph_builder.parse_file(self.repo_path, f)
            if "error" not in parsed:
                self.all_file_data.append(parsed)

        repo_name = self.repo_path.name
        repo_path_str = self.repo_path.resolve().as_posix()

        self.graph_builder.add_repository_to_graph(self.repo_path, is_dependency=False)

        for fd in self.all_file_data:
            self.graph_builder.add_file_to_graph(
                fd, repo_name, self.imports_map, repo_path_str=repo_path_str
            )

        self.graph_builder.link_function_calls(self.all_file_data, self.imports_map)
        self.graph_builder.link_inheritance(self.all_file_data, self.imports_map)

        self.all_file_data.clear()
        info_logger("Initial scan complete")

    def synchronize_with_disk(self) -> None:
        info_logger(f"Syncing: {self.repo_path}")

        current_files = self._iter_supported_files()
        current_paths = {str(p.resolve()) for p in current_files}
        indexed = self.graph_builder.get_repo_file_paths(self.repo_path)

        self.imports_map = self.graph_builder.pre_scan_imports(current_files)

        for stale in indexed - current_paths:
            self.graph_builder.delete_file_from_graph(stale)

        refreshed = []
        refreshed_paths: list[str] = []
        for p in current_files:
            fd = self.graph_builder.update_file_in_graph(
                p, self.repo_path, self.imports_map
            )
            if fd and "error" not in fd:
                refreshed.append(fd)
                refreshed_paths.append(p.resolve().as_posix())

        if refreshed_paths:
            # Only clear edges originating from the files we touched — do not
            # wipe the entire repo call graph like delete_relationship_links().
            self.graph_builder.delete_outgoing_calls_from_files(refreshed_paths)
            self.graph_builder.delete_inherits_for_files(refreshed_paths)
            self.graph_builder.link_function_calls(refreshed, self.imports_map)
            self.graph_builder.link_inheritance(refreshed, self.imports_map)

        info_logger("Sync complete")

    def _debounce(self, event_path, action):
        if event_path in self.timers:
            self.timers[event_path].cancel()
        t = threading.Timer(self.debounce_interval, action)
        t.start()
        self.timers[event_path] = t

    def cancel_timers(self):
        for t in self.timers.values():
            t.cancel()
        self.timers.clear()

    def _update_imports_map_for_file(self, changed_path: Path):
        """Re-scan a single file and merge its contributions into self.imports_map."""
        changed_str = str(changed_path.resolve())
        for symbol in list(self.imports_map.keys()):
            old_list = self.imports_map[symbol]
            if changed_str in old_list:
                new_list = [p for p in old_list if p != changed_str]
                if new_list:
                    self.imports_map[symbol] = new_list
                else:
                    del self.imports_map[symbol]
        if changed_path.exists():
            new_map = self.graph_builder.pre_scan_imports([changed_path])
            for symbol, paths in new_map.items():
                if symbol not in self.imports_map:
                    self.imports_map[symbol] = []
                self.imports_map[symbol].extend(paths)

    def _handle_modification(self, event_path_str: str):
        """Incremental update: re-parse and re-link only the changed file and its neighbours."""
        info_logger(f"File change detected (incremental update): {event_path_str}")
        changed_path = Path(event_path_str)
        if self._should_ignore(changed_path):
            debug_log(f"Ignored watcher update based on .cgcignore: {changed_path}")
            return

        changed_path_str = changed_path.resolve().as_posix()
        supported_extensions = self.graph_builder.parsers.keys()

        caller_paths = {
            p
            for p in self.graph_builder.get_caller_file_paths(changed_path_str)
            if p and not self._should_ignore(p)
        }
        inheritor_paths = {
            p
            for p in self.graph_builder.get_inheritance_neighbor_paths(changed_path_str)
            if p and not self._should_ignore(p)
        }
        affected_paths = {changed_path_str} | caller_paths | inheritor_paths
        info_logger(
            f"[INCREMENTAL] affected={len(affected_paths)} files "
            f"(callers={len(caller_paths)}, inheritors={len(inheritor_paths)})"
        )

        self._update_imports_map_for_file(changed_path)

        self.graph_builder.update_file_in_graph(changed_path, self.repo_path, self.imports_map)

        other_callers = list(caller_paths)
        other_inheritors = list(inheritor_paths)
        if other_callers:
            self.graph_builder.delete_outgoing_calls_from_files(other_callers)
        if other_inheritors:
            self.graph_builder.delete_inherits_for_files(other_inheritors)

        subset_file_data = []
        for path_str in affected_paths:
            p = Path(path_str)
            if p.exists() and p.suffix in supported_extensions and not self._should_ignore(p):
                parsed = self.graph_builder.parse_file(self.repo_path, p)
                if "error" not in parsed:
                    subset_file_data.append(parsed)

        file_class_lookup = self.graph_builder.get_repo_class_lookup(self.repo_path)

        info_logger(f"[INCREMENTAL] Re-linking {len(subset_file_data)} files...")
        self.graph_builder.link_function_calls(
            subset_file_data, self.imports_map, file_class_lookup
        )
        self.graph_builder.link_inheritance(subset_file_data, self.imports_map)

        try:
            from codegraphcontext.cli.config_manager import get_config_value as _gcv
            _vector_enabled = (_gcv("ENABLE_VECTOR_RESOLVE") or "false").lower() == "true"
            _inherit_enabled = (_gcv("ENABLE_INHERIT_RESOLVE") or "false").lower() == "true"
        except Exception as _cfg_e:
            warning_logger(f"[PHASE4/5] Could not read config flags: {_cfg_e}")
            _vector_enabled = False
            _inherit_enabled = False

        if _vector_enabled:
            try:
                from codegraphcontext.tools.indexing.embeddings import EmbeddingPipeline
                embed_pipeline = EmbeddingPipeline(self.graph_builder.driver)
                embed_pipeline.invalidate_for_file(changed_path_str)
                embed_pipeline.run(str(self.repo_path))
                info_logger(f"[EMBED] Incremental embedding complete for {changed_path_str}")
            except Exception as _e:
                warning_logger(f"[EMBED] Incremental embedding failed: {_e}")

        if _inherit_enabled:
            try:
                from codegraphcontext.tools.indexing.resolution.post_resolution import run_inheritance_reresolve
                _vector_resolver = None
                if _vector_enabled:
                    try:
                        from codegraphcontext.tools.indexing.vector_resolver import VectorResolver
                        _vector_resolver = VectorResolver(self.graph_builder.driver)
                    except Exception as _ve:
                        warning_logger(f"[VECTOR] Resolver unavailable for watcher: {_ve}")
                n_improved = run_inheritance_reresolve(
                    self.graph_builder.driver, str(self.repo_path), _vector_resolver
                )
                info_logger(f"[INHERIT-RESOLVE] Incremental: {n_improved} edges improved")
            except Exception as _e:
                warning_logger(f"[INHERIT-RESOLVE] Incremental failed: {_e}")

        info_logger(f"[INCREMENTAL] Done. Graph refresh for {event_path_str} complete! ✅")

    def on_created(self, event):
        if not event.is_directory and self._is_supported_code_file(event.src_path):
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_modified(self, event):
        if not event.is_directory and self._is_supported_code_file(event.src_path):
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory:
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._debounce(event.dest_path, lambda: self._handle_modification(event.dest_path))


class CodeWatcher:
    def __init__(
        self,
        graph_builder: "GraphBuilder",
        job_manager="JobManager",
        use_polling: typing.Optional[bool] = None,
    ):
        self.graph_builder = graph_builder
        observer_cls = PollingObserver if should_use_polling_observer(use_polling) else Observer
        self.observer = observer_cls()

        self.watched_paths = set()
        self.watches = {}
        self.handlers = {}

    def watch_directory(
        self,
        path: str,
        perform_initial_scan: bool = True,
        cgcignore_path: str = None,
        sync_on_start: bool = False,
    ):
        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        if path_str in self.watched_paths:
            return {"message": "Already watching"}

        handler = RepositoryEventHandler(
            self.graph_builder,
            path_obj,
            perform_initial_scan=perform_initial_scan,
            sync_on_start=sync_on_start,
            cgcignore_path=cgcignore_path,
        )

        watch = self.observer.schedule(handler, path_str, recursive=True)

        self.watches[path_str] = watch
        self.handlers[path_str] = handler
        self.watched_paths.add(path_str)

        return {"message": f"Watching {path_str}"}

    def unwatch_directory(self, path: str):
        path_str = str(Path(path).resolve())

        handler = self.handlers.pop(path_str, None)
        if handler:
            handler.cancel_timers()

        watch = self.watches.pop(path_str, None)
        if watch:
            self.observer.unschedule(watch)

        self.watched_paths.discard(path_str)

        return {"message": f"Stopped watching {path_str}"}

    def list_watched_paths(self):
        return list(self.watched_paths)

    def start(self):
        if not self.observer.is_alive():
            self.observer.start()

    def stop(self):
        for h in self.handlers.values():
            h.cancel_timers()
        self.handlers.clear()

        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()