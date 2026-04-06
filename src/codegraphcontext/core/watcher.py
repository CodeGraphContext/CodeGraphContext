# src/codegraphcontext/core/watcher.py
"""
This module implements the live file-watching functionality using the `watchdog` library.
It observes directories for changes and triggers updates to the code graph.
"""
import threading
from pathlib import Path
import typing
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

if typing.TYPE_CHECKING:
    from codegraphcontext.tools.graph_builder import GraphBuilder
    from codegraphcontext.core.jobs import JobManager

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

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
        
        # Caches for the repository's state.
        self.all_file_data = []
        self.imports_map = {}
        
        # Perform the initial scan and linking when the watcher is created.
        if perform_initial_scan:
            self._initial_scan()

    def _initial_scan(self):
        """Scans the entire repository, parses all files, and builds the initial graph."""
        info_logger(f"Performing initial scan for watcher: {self.repo_path}")
        supported_extensions = self.graph_builder.parsers.keys()
        all_files = [f for f in self.repo_path.rglob("*") if f.is_file() and f.suffix in supported_extensions]
        
        # 1. Pre-scan all files to get a global map of where every symbol is defined.
        self.imports_map = self.graph_builder._pre_scan_for_imports(all_files)
        
        # 2. Parse all files in detail and cache the parsed data.
        for f in all_files:
            parsed_data = self.graph_builder.parse_file(self.repo_path, f)
            if "error" not in parsed_data:
                self.all_file_data.append(parsed_data)
        
        # 3. After all files are parsed, create the relationships (e.g., function calls) between them.
        self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
        self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
        # Free memory — all_file_data is only needed during the linking pass.
        self.all_file_data.clear()
        info_logger(f"Initial scan and graph linking complete for: {self.repo_path}")

    def _debounce(self, event_path, action):
        """
        Schedules an action to run after a debounce interval.
        This prevents the handler from firing on every single file save event in rapid
        succession, which is common in IDEs. It waits for a quiet period before processing.
        """
        # If a timer already exists for this path, cancel it.
        if event_path in self.timers:
            self.timers[event_path].cancel()
        # Create and start a new timer.
        timer = threading.Timer(self.debounce_interval, action)
        timer.start()
        self.timers[event_path] = timer

    def _update_imports_map_for_file(self, changed_path: Path):
        """Re-scan a single file and merge its contributions into self.imports_map.
        Removes stale paths for the file before inserting new ones so renamed/deleted
        symbols don't leave dangling entries."""
        changed_str = str(changed_path.resolve())
        # Remove old contributions of this file from every symbol it previously exported.
        for symbol in list(self.imports_map.keys()):
            old_list = self.imports_map[symbol]
            if changed_str in old_list:
                new_list = [p for p in old_list if p != changed_str]
                if new_list:
                    self.imports_map[symbol] = new_list
                else:
                    del self.imports_map[symbol]
        # Merge new contributions (if the file still exists).
        if changed_path.exists():
            new_map = self.graph_builder._pre_scan_for_imports([changed_path])
            for symbol, paths in new_map.items():
                if symbol not in self.imports_map:
                    self.imports_map[symbol] = []
                self.imports_map[symbol].extend(paths)

    def _handle_modification(self, event_path_str: str):
        """
        Incremental update: only re-parse and re-link the changed file plus the files
        that previously called into it.  O(k) instead of O(n) for every event.

        Algorithm:
          1. Query Neo4j for files that have CALLS/INHERITS touching the changed file
             (must happen BEFORE nodes are deleted, so the graph still has the old edges).
          2. Update self.imports_map for the changed file only (O(1) file scan).
          3. update_file_in_graph — DETACH DELETE cleans up ALL CALLS/INHERITS on the
             changed file's nodes (both incoming and outgoing) automatically.
          4. Delete outgoing CALLS from affected *caller* files (their CALLS to the changed
             file were removed by DETACH DELETE, but their CALLS to unrelated files are
             still there; we must delete all their outgoing CALLS before re-creating so we
             don't leave stale CALLS to functions that have moved/been renamed).
          5. Re-parse only the affected subset (changed file + callers + inheritors).
          6. Build file_class_lookup cheaply from Neo4j (no full re-parse needed).
          7. Re-create CALLS/INHERITS for the subset only.
        """
        info_logger(f"File change detected (incremental update): {event_path_str}")
        changed_path = Path(event_path_str)
        changed_path_str = str(changed_path.resolve())
        supported_extensions = self.graph_builder.parsers.keys()

        # Step 1: Find affected neighbours BEFORE nodes are destroyed.
        caller_paths = self.graph_builder.get_caller_file_paths(changed_path_str)
        inheritor_paths = self.graph_builder.get_inheritance_neighbor_paths(changed_path_str)
        affected_paths = {changed_path_str} | caller_paths | inheritor_paths
        info_logger(
            f"[INCREMENTAL] affected={len(affected_paths)} files "
            f"(callers={len(caller_paths)}, inheritors={len(inheritor_paths)})"
        )

        # Step 2: Update imports_map for the changed file only.
        self._update_imports_map_for_file(changed_path)

        # Step 3: Delete + re-add nodes for the changed file.
        # DETACH DELETE inside update_file_in_graph removes all CALLS/INHERITS on its nodes.
        self.graph_builder.update_file_in_graph(changed_path, self.repo_path, self.imports_map)

        # Step 4: Clean up CALLS/INHERITS from the affected *caller/inheritor* files.
        # Their CALLS to the changed file were already removed by DETACH DELETE, but their
        # CALLS to other files are still intact.  We delete all their outgoing CALLS so we
        # can safely re-create the full set from scratch for the subset.
        other_callers = list(caller_paths)       # does NOT include changed_path_str
        other_inheritors = list(inheritor_paths)
        if other_callers:
            self.graph_builder.delete_outgoing_calls_from_files(other_callers)
        if other_inheritors:
            self.graph_builder.delete_inherits_for_files(other_inheritors)

        # Step 5: Re-parse only the affected subset.
        subset_file_data = []
        for path_str in affected_paths:
            p = Path(path_str)
            if p.exists() and p.suffix in supported_extensions:
                parsed = self.graph_builder.parse_file(self.repo_path, p)
                if "error" not in parsed:
                    subset_file_data.append(parsed)

        # Step 6: Get full-repo file_class_lookup from Neo4j (avoids re-parsing all files).
        # The changed file's new classes are already overlaid inside _create_all_function_calls.
        file_class_lookup = self.graph_builder.get_repo_class_lookup(self.repo_path)

        # Step 7: Re-create CALLS/INHERITS for the affected subset only.
        info_logger(f"[INCREMENTAL] Re-linking {len(subset_file_data)} files...")
        self.graph_builder._create_all_function_calls(subset_file_data, self.imports_map, file_class_lookup)
        self.graph_builder._create_all_inheritance_links(subset_file_data, self.imports_map)
        info_logger(f"[INCREMENTAL] Done. Graph refresh for {event_path_str} complete! ✅")

    # The following methods are called by the watchdog observer when a file event occurs.
    def on_created(self, event):
        if not event.is_directory and Path(event.src_path).suffix in self.graph_builder.parsers:
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).suffix in self.graph_builder.parsers:
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and Path(event.src_path).suffix in self.graph_builder.parsers:
            self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            if Path(event.src_path).suffix in self.graph_builder.parsers:
                self._debounce(event.src_path, lambda: self._handle_modification(event.src_path))
            if Path(event.dest_path).suffix in self.graph_builder.parsers:
                self._debounce(event.dest_path, lambda: self._handle_modification(event.dest_path))


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
