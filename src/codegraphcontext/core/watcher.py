# src/codegraphcontext/core/watcher.py
"""
This module implements the live file-watching functionality using the `watchdog` library.
It observes directories for changes and triggers updates to the code graph.
"""
import threading
import sys
import os
from pathlib import Path
import typing
import pathspec
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

if typing.TYPE_CHECKING:
    from codegraphcontext.tools.graph_builder import GraphBuilder
    from codegraphcontext.core.jobs import JobManager

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.cli.config_manager import get_config_value
from codegraphcontext.tools.graph_builder import DEFAULT_IGNORE_PATTERNS

WATCHER_DEBUG_STDERR = os.getenv("CGC_WATCHER_DEBUG", "false").lower() == "true"


def _watcher_debug_stderr(message: str):
    if WATCHER_DEBUG_STDERR:
        print(message, file=sys.stderr, flush=True)

class RepositoryEventHandler(FileSystemEventHandler):
    """
    A dedicated event handler for a single repository being watched.
    
    This handler is stateful. It performs an initial scan of the repository
    to build a baseline and then uses this cached state to perform efficient
    updates when files are changed, created, or deleted.
    """
    def __init__(self, graph_builder: "GraphBuilder", repo_path: Path, debounce_interval=2.0, perform_initial_scan: bool = True):
        """
        Initializes the event handler.

        Args:
            graph_builder: An instance of the GraphBuilder to perform graph operations.
            repo_path: The absolute path to the repository directory to watch.
            debounce_interval: The time in seconds to wait for more changes before processing an event.
            perform_initial_scan: Whether to perform an initial scan of the repository.
        """
        super().__init__()
        self.graph_builder = graph_builder
        self.repo_path = repo_path
        self.debounce_interval = debounce_interval
        self.timers = {} # A dictionary to manage debounce timers for file paths.
        self.supported_extensions = set(self.graph_builder.parsers.keys())
        self.ignore_root = self.repo_path.resolve()
        self.ignore_dirs = self._load_ignore_dirs()
        self.ignore_spec = self._build_ignore_spec()
        self.known_files = set(self._scan_supported_files())
        self.file_symbol_index = {}
        self.refresh_state_lock = threading.Lock()
        self.refresh_in_progress = False
        self.pending_refresh_paths = {}
        
        # Caches for the repository's state.
        self.all_file_data = []
        self.imports_map = {}
        
        # Perform the initial scan and linking when the watcher is created.
        if perform_initial_scan:
            self._initial_scan()

    def _load_ignore_dirs(self):
        ignore_dirs_str = (get_config_value("IGNORE_DIRS") or "").strip()
        if not ignore_dirs_str:
            return set()
        return {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}

    def _build_ignore_spec(self):
        cgcignore_path = None
        curr = self.ignore_root
        while True:
            candidate = curr / ".cgcignore"
            if candidate.exists():
                cgcignore_path = candidate
                break
            if curr.parent == curr:
                break
            curr = curr.parent

        user_patterns = []
        if cgcignore_path:
            with open(cgcignore_path) as f:
                user_patterns = [
                    line.strip()
                    for line in f.read().splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]

        return pathspec.PathSpec.from_lines("gitwildmatch", DEFAULT_IGNORE_PATTERNS + user_patterns)

    def _is_supported_path(self, event_path: str) -> bool:
        return Path(event_path).suffix in self.supported_extensions

    def _is_ignored_path(self, event_path: str) -> bool:
        path_obj = Path(event_path).resolve()

        try:
            rel_to_repo = path_obj.relative_to(self.repo_path.resolve())
        except ValueError:
            return False

        if self.ignore_dirs:
            parts = {p.lower() for p in rel_to_repo.parent.parts}
            if parts.intersection(self.ignore_dirs):
                return True

        return self.ignore_spec.match_file(rel_to_repo.as_posix())

    def _scan_supported_files(self):
        return [
            f
            for f in self.repo_path.rglob("*")
            if f.is_file()
            and f.suffix in self.supported_extensions
            and not self._is_ignored_path(str(f))
        ]

    def _get_supported_files(self):
        existing_files = []
        stale_files = []
        for f in self.known_files:
            if f.exists():
                existing_files.append(f)
            else:
                stale_files.append(f)
        for f in stale_files:
            self.known_files.discard(f)
        return existing_files

    def _replace_import_symbols(self, path_str: str, symbols: set[str]):
        previous_symbols = self.file_symbol_index.pop(path_str, set())
        for symbol in previous_symbols:
            existing_paths = self.imports_map.get(symbol, [])
            filtered_paths = [
                existing_path
                for existing_path in existing_paths
                if str(Path(existing_path).resolve()) != path_str
            ]
            if filtered_paths:
                self.imports_map[symbol] = filtered_paths
            else:
                self.imports_map.pop(symbol, None)

        if not symbols:
            return

        self.file_symbol_index[path_str] = set(symbols)
        for symbol in symbols:
            existing_paths = self.imports_map.setdefault(symbol, [])
            if path_str not in existing_paths:
                existing_paths.append(path_str)

    def _refresh_imports_cache(self, changed_paths: list[str]):
        rescannable_files = []
        for changed_path in changed_paths:
            path_obj = Path(changed_path).resolve()
            if (
                path_obj.exists()
                and path_obj.is_file()
                and self._is_supported_path(str(path_obj))
                and not self._is_ignored_path(str(path_obj))
            ):
                rescannable_files.append(path_obj)
            else:
                self._replace_import_symbols(str(path_obj), set())

        if not rescannable_files:
            return

        rescanned_symbols = self.graph_builder.pre_scan_files_to_symbol_index(rescannable_files)
        for path_obj in rescannable_files:
            path_str = str(path_obj.resolve())
            self._replace_import_symbols(path_str, rescanned_symbols.get(path_str, set()))

    def _initial_scan(self):
        """Scans the entire repository, parses all files, and builds the initial graph."""
        info_logger(f"Performing initial scan for watcher: {self.repo_path}")
        all_files = self._get_supported_files()
        
        # 1. Pre-scan all files to get a global map of where every symbol is defined.
        self.imports_map = self.graph_builder._pre_scan_for_imports(all_files)
        self.file_symbol_index = self.graph_builder.build_file_symbol_index(self.imports_map)
        
        # 2. Parse all files in detail and cache the parsed data.
        for f in all_files:
            parsed_data = self.graph_builder.parse_file(self.repo_path, f)
            if "error" not in parsed_data:
                self.all_file_data.append(parsed_data)
        
        # 3. After all files are parsed, create the relationships (e.g., function calls) between them.
        self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
        self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
        info_logger(f"Initial scan and graph linking complete for: {self.repo_path}")

    def _debounce(self, event_path, action):
        """
        Schedules an action to run after a debounce interval.
        This prevents the handler from firing on every single file save event in rapid
        succession, which is common in IDEs. It waits for a quiet period before processing.
        """
        debug_log(f"[watcher] debounce scheduled for {event_path}")
        # If a timer already exists for this path, cancel it.
        if event_path in self.timers:
            self.timers[event_path].cancel()

        def wrapped_action():
            debug_log(f"[watcher] debounce firing for {event_path}")
            _watcher_debug_stderr(f"[watcher-debug] debounce firing for {event_path}")
            try:
                self._run_refresh_cycle(event_path)
            except Exception as e:
                error_logger(f"Watcher refresh failed for {event_path}: {e}")
                debug_log(f"[watcher] debounce action failed for {event_path}: {e}")
                _watcher_debug_stderr(f"[watcher-debug] debounce action failed for {event_path}: {e}")
                raise

        # Create and start a new timer.
        timer = threading.Timer(self.debounce_interval, wrapped_action)
        timer.start()
        self.timers[event_path] = timer

    def _queue_refresh_path(self, event_path: str):
        self.pending_refresh_paths[event_path] = None

    def _drain_pending_refresh_paths(self):
        queued_paths = list(self.pending_refresh_paths.keys())
        self.pending_refresh_paths.clear()
        return queued_paths

    def _run_refresh_cycle(self, event_path):
        with self.refresh_state_lock:
            if self.refresh_in_progress:
                self._queue_refresh_path(event_path)
                _watcher_debug_stderr(
                    f"[watcher-debug] refresh already running; queued latest path {event_path}"
                )
                return
            self.refresh_in_progress = True

        try:
            current_paths = [event_path]
            while True:
                self._handle_modifications(current_paths)
                with self.refresh_state_lock:
                    if not self.pending_refresh_paths:
                        self.refresh_in_progress = False
                        return
                    current_paths = self._drain_pending_refresh_paths()
                _watcher_debug_stderr(
                    f"[watcher-debug] running queued refresh for {len(current_paths)} path(s)"
                )
        except Exception:
            with self.refresh_state_lock:
                self.refresh_in_progress = False
            raise

    def _handle_modifications(self, event_path_strs: list[str]):
        """
        Orchestrates the complete update cycle for one or more modified, created, moved,
        or deleted files. This batches queued file changes into a single refresh cycle.
        """
        changed_paths = [str(Path(path).resolve()) for path in dict.fromkeys(event_path_strs)]
        if not changed_paths:
            return

        if len(changed_paths) == 1:
            info_logger(f"File change detected, starting full repository refresh for: {changed_paths[0]}")
            debug_log(f"[watcher] _handle_modifications start for {changed_paths[0]}")
            _watcher_debug_stderr(f"[watcher-debug] refresh start for {changed_paths[0]}")
        else:
            info_logger(
                f"Detected {len(changed_paths)} file changes, starting batched repository refresh."
            )
            debug_log(
                f"[watcher] _handle_modifications start for batch of {len(changed_paths)} paths"
            )
            _watcher_debug_stderr(
                f"[watcher-debug] refresh start for batch of {len(changed_paths)} path(s)"
            )

        for changed_path in changed_paths:
            path_obj = Path(changed_path)
            if (
                path_obj.exists()
                and path_obj.is_file()
                and self._is_supported_path(changed_path)
                and not self._is_ignored_path(changed_path)
            ):
                self.known_files.add(path_obj)
            else:
                self.known_files.discard(path_obj)

        # 1. Get all supported files in the repository.
        all_files = self._get_supported_files()
        debug_log(f"[watcher] selected {len(all_files)} supported files for refresh")
        _watcher_debug_stderr(f"[watcher-debug] selected {len(all_files)} files for refresh")

        # 2. Update the cached imports map only for files that changed.
        self._refresh_imports_cache(changed_paths)
        info_logger("Refreshed global imports map incrementally.")
        debug_log(f"[watcher] refreshed imports map with {len(self.imports_map)} entries")
        _watcher_debug_stderr(
            f"[watcher-debug] refreshed imports map with {len(self.imports_map)} entries"
        )

        # 3. Identify the subset of files that need call/inheritance relinking
        # before changed-file nodes are deleted and recreated.
        relink_paths = self.graph_builder.get_files_requiring_relink(changed_paths)
        _watcher_debug_stderr(
            f"[watcher-debug] relink target set contains {len(relink_paths)} path(s)"
        )

        # 4. Update the changed files in one DB session.
        updated_files = self.graph_builder.update_files_in_graph(
            [Path(path) for path in changed_paths],
            self.repo_path,
            self.imports_map,
        )

        # 5. Re-parse only the files that need outgoing CALLS / INHERITS recomputed.
        # Reuse freshly parsed changed files from the graph update step when possible.
        self.all_file_data = []
        for f in all_files:
            path_str = str(f.resolve())
            if path_str not in relink_paths:
                continue
            cached_update = updated_files.get(path_str)
            if cached_update and "error" not in cached_update and not cached_update.get("deleted"):
                self.all_file_data.append(cached_update)
                continue
            parsed_data = self.graph_builder.parse_file(self.repo_path, f)
            if "error" not in parsed_data:
                self.all_file_data.append(parsed_data)
        info_logger("Refreshed in-memory cache of all file data.")
        debug_log(f"[watcher] refreshed file cache with {len(self.all_file_data)} parsed files")
        _watcher_debug_stderr(
            f"[watcher-debug] refreshed file cache with {len(self.all_file_data)} parsed files"
        )

        # 6. Re-link the affected graph slice using the updated cache and imports map.
        info_logger("Re-linking the graph for calls and inheritance...")
        self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
        self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
        if len(changed_paths) == 1:
            info_logger(f"Graph refresh for change in {changed_paths[0]} complete! ✅")
            debug_log(f"[watcher] graph refresh complete for {changed_paths[0]}")
            _watcher_debug_stderr(f"[watcher-debug] graph refresh complete for {changed_paths[0]}")
        else:
            info_logger(f"Batched graph refresh for {len(changed_paths)} changes complete! ✅")
            debug_log(
                f"[watcher] graph refresh complete for batch of {len(changed_paths)} paths"
            )
            _watcher_debug_stderr(
                f"[watcher-debug] graph refresh complete for batch of {len(changed_paths)} path(s)"
            )

    # The following methods are called by the watchdog observer when a file event occurs.
    def on_created(self, event):
        if not event.is_directory and self._is_supported_path(event.src_path) and not self._is_ignored_path(event.src_path):
            self.known_files.add(Path(event.src_path).resolve())
            debug_log(f"[watcher] on_created accepted {event.src_path}")
            _watcher_debug_stderr(f"[watcher-debug] on_created accepted {event.src_path}")
            self._debounce(event.src_path, lambda: self._handle_modifications([event.src_path]))

    def on_modified(self, event):
        if not event.is_directory and self._is_supported_path(event.src_path) and not self._is_ignored_path(event.src_path):
            self.known_files.add(Path(event.src_path).resolve())
            debug_log(f"[watcher] on_modified accepted {event.src_path}")
            _watcher_debug_stderr(f"[watcher-debug] on_modified accepted {event.src_path}")
            self._debounce(event.src_path, lambda: self._handle_modifications([event.src_path]))

    def on_deleted(self, event):
        if not event.is_directory and self._is_supported_path(event.src_path) and not self._is_ignored_path(event.src_path):
            self.known_files.discard(Path(event.src_path).resolve())
            debug_log(f"[watcher] on_deleted accepted {event.src_path}")
            self._debounce(event.src_path, lambda: self._handle_modifications([event.src_path]))

    def on_moved(self, event):
        if not event.is_directory:
            if self._is_supported_path(event.src_path) and not self._is_ignored_path(event.src_path):
                self.known_files.discard(Path(event.src_path).resolve())
                debug_log(f"[watcher] on_moved accepted src {event.src_path}")
                self._debounce(event.src_path, lambda: self._handle_modifications([event.src_path]))
            if self._is_supported_path(event.dest_path) and not self._is_ignored_path(event.dest_path):
                self.known_files.add(Path(event.dest_path).resolve())
                debug_log(f"[watcher] on_moved accepted dest {event.dest_path}")
                self._debounce(event.dest_path, lambda: self._handle_modifications([event.dest_path]))


class CodeWatcher:
    """
    Manages the file system observer thread. It can watch multiple directories,
    assigning a separate `RepositoryEventHandler` to each one.
    """
    def __init__(self, graph_builder: "GraphBuilder", job_manager= "JobManager"):
        self.graph_builder = graph_builder
        self.observer = Observer()
        self.watched_paths = set() # Keep track of paths already being watched.
        self.watches = {} # Store watch objects to allow unscheduling

    def watch_directory(self, path: str, perform_initial_scan: bool = True):
        """Schedules a directory to be watched for changes."""
        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        if path_str in self.watched_paths:
            info_logger(f"Path already being watched: {path_str}")
            return {"message": f"Path already being watched: {path_str}"}
        
        # Create a new, dedicated event handler for this specific repository path.
        event_handler = RepositoryEventHandler(self.graph_builder, path_obj, perform_initial_scan=perform_initial_scan)
        
        watch = self.observer.schedule(event_handler, path_str, recursive=True)
        self.watches[path_str] = watch
        self.watched_paths.add(path_str)
        info_logger(f"Started watching for code changes in: {path_str}")
        
        return {"message": f"Started watching {path_str}."}
    def unwatch_directory(self, path: str):
        """Stops watching a directory for changes."""
        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        if path_str not in self.watched_paths:
            warning_logger(f"Attempted to unwatch a path that is not being watched: {path_str}")
            return {"error": f"Path not currently being watched: {path_str}"}

        watch = self.watches.pop(path_str, None)
        if watch:
            self.observer.unschedule(watch)
        
        self.watched_paths.discard(path_str)
        info_logger(f"Stopped watching for code changes in: {path_str}")
        return {"message": f"Stopped watching {path_str}."}

    def list_watched_paths(self) -> list:
        """Returns a list of all currently watched directory paths."""
        return list(self.watched_paths)

    def start(self):
        """Starts the observer thread."""
        if not self.observer.is_alive():
            self.observer.start()
            info_logger("Code watcher observer thread started.")

    def stop(self):
        """Stops the observer thread gracefully."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join() # Wait for the thread to terminate.
            info_logger("Code watcher observer thread stopped.")
