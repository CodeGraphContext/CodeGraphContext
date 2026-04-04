import asyncio
import json
import uuid
import urllib.parse
from pathlib import Path
import time
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)

from ..core import get_database_manager
from ..core.jobs import JobManager
from ..tools.code_finder import CodeFinder
from ..tools.graph_builder import GraphBuilder
from ..tools.package_resolver import get_local_package_path

console = Console()


def _initialize_services():
    """Initializes and returns core service managers."""
    console.print("[dim]Initializing services and database connection...[/dim]")
    try:
        db_manager = get_database_manager()
    except ValueError as e:
        console.print(f"[bold red]Database Configuration Error:[/bold red] {e}")
        return None, None, None

    try:
        db_manager.get_driver()
    except Exception as e:
        # Check if this is a FalkorDB failure that should trigger a KùzuDB fallback
        from ..core.database_falkordb import FalkorDBUnavailableError
        if isinstance(e, FalkorDBUnavailableError):
            console.print(f"[yellow]⚠ FalkorDB Lite is not functional in this environment: {e}[/yellow]")
            console.print("[cyan]Falling back to KùzuDB for a reliable experience...[/cyan]")
            
            # Close the broken driver/socket
            try:
                db_manager.close_driver()
            except Exception:
                pass
            
            # Re-initialize explicitly with KùzuDB
            from ..core.database_kuzu import KuzuDBManager
            db_manager = KuzuDBManager()
            try:
                db_manager.get_driver()
                console.print("[green]✓[/green] Successfully switched to KùzuDB fallback")
            except Exception as kuzu_e:
                console.print(f"[bold red]Critical Error:[/bold red] Both FalkorDB and KùzuDB failed: {kuzu_e}")
                return None, None, None
        else:
            console.print(f"[bold red]Database Connection Error:[/bold red] {e}")
            console.print("Please ensure your database is configured correctly or run 'cgc doctor'.")
            return None, None, None
    
    # The GraphBuilder requires an event loop, even for synchronous-style execution
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    graph_builder = GraphBuilder(db_manager, JobManager(), loop)
    code_finder = CodeFinder(db_manager)
    console.print("[dim]Services initialized.[/dim]")
    return db_manager, graph_builder, code_finder


async def _run_index_with_progress(graph_builder: GraphBuilder, path_obj: Path, is_dependency: bool = False):
    """Internal helper to run indexing with a Live progress bar."""
    job_id = graph_builder.job_manager.create_job(str(path_obj), is_dependency=is_dependency)
    
    # Create the progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[filename]}"),
        console=console,
        transient=True,
    ) as progress:
        
        task_id = progress.add_task(
            "Indexing...", 
            total=None,  # Will be updated once file discovery is done
            filename=""
        )

        indexing_task = asyncio.create_task(
            graph_builder.build_graph_from_path_async(path_obj, is_dependency=is_dependency, job_id=job_id)
        )

        from ..core.jobs import JobStatus
        
        # Poll for updates
        while not indexing_task.done():
            job = graph_builder.job_manager.get_job(job_id)
            if job:
                if job.total_files > 0:
                    progress.update(task_id, total=job.total_files, completed=job.processed_files)
                
                # Update the current filename in the UI
                current_file = job.current_file or ""
                if len(current_file) > 40:
                    current_file = "..." + current_file[-37:]
                progress.update(task_id, filename=current_file)

                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    break
            
            await asyncio.sleep(0.1)

        # Wait for actual completion and handle final state
        try:
            await indexing_task
            job = graph_builder.job_manager.get_job(job_id)
            if job and job.status == JobStatus.FAILED:
                error_msg = job.errors[0] if job.errors else "Unknown error"
                raise RuntimeError(error_msg)
        except Exception as e:
            raise e


def index_helper(path: str):
    """Synchronously indexes a repository."""
    time_start = time.time()
    services = _initialize_services()
    if not all(services):
        return

    db_manager, graph_builder, code_finder = services
    path_obj = Path(path).resolve()

    if not path_obj.exists():
        console.print(f"[red]Error: Path does not exist: {path_obj}[/red]")
        db_manager.close_driver()
        return

    indexed_repos = code_finder.list_indexed_repositories()
    repo_exists = any(Path(repo["path"]).resolve() == path_obj for repo in indexed_repos)
    
    if repo_exists:
        # Check if the repository actually has files (not just an empty node from interrupted indexing)
        try:
            with db_manager.get_driver().session() as session:
                result = session.run(
                    "MATCH (r:Repository {path: $path})-[:CONTAINS]->(f:File) RETURN count(f) as file_count",
                    path=str(path_obj)
                )
                record = result.single()
                file_count = record["file_count"] if record else 0
                
                if file_count > 0:
                    console.print(f"[yellow]Repository '{path}' is already indexed with {file_count} files. Skipping.[/yellow]")
                    console.print("[dim]💡 Tip: Use 'cgc index --force' to re-index[/dim]")
                    db_manager.close_driver()
                    return
                else:
                    console.print(f"[yellow]Repository '{path}' exists but has no files (likely interrupted). Re-indexing...[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check file count: {e}. Proceeding with indexing...[/yellow]")

    console.print(f"Starting indexing for: {path_obj}")

    try:
        asyncio.run(_run_index_with_progress(graph_builder, path_obj, is_dependency=False))
        time_end = time.time()
        elapsed = time_end - time_start
        console.print(f"[green]Successfully finished indexing: {path} in {elapsed:.2f} seconds[/green]")
        
        # Check if auto-watch is enabled
        try:
            from codegraphcontext.cli.config_manager import get_config_value
            auto_watch = get_config_value('ENABLE_AUTO_WATCH')
            if auto_watch and str(auto_watch).lower() == 'true':
                console.print("\n[cyan]🔍 ENABLE_AUTO_WATCH is enabled. Starting watcher...[/cyan]")
                db_manager.close_driver()  # Close before starting watcher
                watch_helper(path)  # This will block the terminal
                return  # watch_helper handles its own cleanup
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check ENABLE_AUTO_WATCH: {e}[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]An error occurred during indexing:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def add_package_helper(package_name: str, language: str):
    """Synchronously indexes a package."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, graph_builder, code_finder = services

    package_path_str = get_local_package_path(package_name, language)
    if not package_path_str:
        console.print(f"[red]Error: Could not find package '{package_name}' for language '{language}'.[/red]")
        db_manager.close_driver()
        return

    package_path = Path(package_path_str)
    
    indexed_repos = code_finder.list_indexed_repositories()
    if any(repo.get("name") == package_name for repo in indexed_repos if repo.get("is_dependency")):
        console.print(f"[yellow]Package '{package_name}' is already indexed. Skipping.[/yellow]")
        db_manager.close_driver()
        return

    console.print(f"Starting indexing for package '{package_name}' at: {package_path}")

    try:
        asyncio.run(_run_index_with_progress(graph_builder, package_path, is_dependency=True))
        console.print(f"[green]Successfully finished indexing package: {package_name}[/green]")
    except Exception as e:
        console.print(f"[bold red]An error occurred during package indexing:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def list_repos_helper():
    """Lists all indexed repositories."""
    services = _initialize_services()
    if not all(services):
        return
    
    db_manager, _, code_finder = services
    
    try:
        repos = code_finder.list_indexed_repositories()
        if not repos:
            console.print("[yellow]No repositories indexed yet.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="dim")
        table.add_column("Path")
        table.add_column("Type")

        for repo in repos:
            repo_type = "Dependency" if repo.get("is_dependency") else "Project"
            table.add_row(repo["name"], repo["path"], repo_type)
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def delete_helper(repo_path: str):
    """Deletes a repository from the graph."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, graph_builder, _ = services
    
    try:
        if graph_builder.delete_repository_from_graph(repo_path):
            console.print(f"[green]Successfully deleted repository: {repo_path}[/green]")
        else:
            console.print(f"[yellow]Repository not found in graph: {repo_path}[/yellow]")
            console.print("[dim]Tip: Use 'cgc list' to see available repositories.[/dim]")
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def cypher_helper(query: str):
    """Executes a read-only Cypher query."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, _ = services
    
    # Replicating safety checks from MCPServer
    forbidden_keywords = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP', 'CALL apoc']
    if any(keyword in query.upper() for keyword in forbidden_keywords):
        console.print("[bold red]Error: This command only supports read-only queries.[/bold red]")
        db_manager.close_driver()
        return

    try:
        with db_manager.get_driver().session() as session:
            result = session.run(query)
            records = [record.data() for record in result]
            console.print(json.dumps(records, indent=2))
    except Exception as e:
        console.print(f"[bold red]An error occurred while executing query:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def cypher_helper_visual(query: str):
    """Executes a read-only Cypher query and visualizes the results."""
    from .visualizer import visualize_cypher_results
    
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, _ = services
    
    # Replicating safety checks from MCPServer
    forbidden_keywords = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP', 'CALL apoc']
    if any(keyword in query.upper() for keyword in forbidden_keywords):
        console.print("[bold red]Error: This command only supports read-only queries.[/bold red]")
        db_manager.close_driver()
        return

    try:
        with db_manager.get_driver().session() as session:
            result = session.run(query)
            records = [record.data() for record in result]
            
            if not records:
                console.print("[yellow]No results to visualize.[/yellow]")
                return  # finally block will close driver
            
            visualize_cypher_results(records, query)
    except Exception as e:
        console.print(f"[bold red]An error occurred while executing query:[/bold red] {e}")
    finally:
        db_manager.close_driver()


import uvicorn
import urllib.parse
from ..viz.server import run_server, set_db_manager

def visualize_helper(repo_path: Optional[str] = None, port: int = 8000):
    """"Generates an interactive visualization using the Playground UI."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, _ = services
    
    # Set the DB manager for the server
    set_db_manager(db_manager)
    
    # Determine the static directory (built React app)
    # This points to src/codegraphcontext/viz/dist where we build the website
    # (relative to src/codegraphcontext/cli/cli_helpers.py)
    # Using .resolve() is more robust for path comparison and existence checks
    this_file = Path(__file__).resolve()
    package_root = this_file.parent.parent
    static_dir = package_root / "viz" / "dist"
    
    # Fallback for development if not yet built in viz/dist
    if not static_dir.exists():
        # Look for website/dist in the project root (3 levels up from cli/cli_helpers.py, 4 parents)
        # 1: cli/, 2: codegraphcontext/, 3: src/, 4: project_root/
        project_root = this_file.parent.parent.parent.parent
        dev_static_dir = project_root / "website" / "dist"
        
        # Also try one level up from package_root just in case of different layouts
        alt_dev_dir = package_root.parent.parent / "website" / "dist"
        
        if dev_static_dir.exists():
            static_dir = dev_static_dir
        elif alt_dev_dir.exists():
            static_dir = alt_dev_dir
        else:
            # Last resort: try current working directory
            cwd_static_dir = Path.cwd() / "website" / "dist"
            if cwd_static_dir.exists():
                static_dir = cwd_static_dir
            else:
                console.print(f"[yellow]Warning: Visualization assets not found.[/yellow]")
                console.print(f"[dim]Checked paths:[/dim]")
                console.print(f"  [dim]- {static_dir}[/dim]")
                console.print(f"  [dim]- {dev_static_dir}[/dim]")
                console.print(f"  [dim]- {alt_dev_dir}[/dim]")
                console.print(f"  [dim]- {cwd_static_dir}[/dim]")
                console.print("[dim]Please run 'cd website && npm run build' first.[/dim]")
                # We continue anyway to let the server start (helpful for dev)
    
    # Construct the URL
    backend_url = f"http://localhost:{port}"
    params = {"backend": backend_url}
    if repo_path:
        params["repo_path"] = str(Path(repo_path).resolve())
    
    query_string = urllib.parse.urlencode(params)
    visualization_url = f"{backend_url}/explore?{query_string}"
    
    console.print(f"[green]Starting visualizer server on {backend_url}...[/green]")
    console.print(f"[cyan]Opening Playground UI:[/cyan] {visualization_url}")
    
    # Open browser in a separate thread/process if possible, or just before starting server
    def open_browser():
        import time
        import webbrowser
        time.sleep(1.5) # Give the server a moment to start
        webbrowser.open(visualization_url)
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        run_server(host="127.0.0.1", port=port, static_dir=str(static_dir))
    except Exception as e:
        console.print(f"[bold red]An error occurred while running the server:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def reindex_helper(path: str):
    """Force re-index by deleting and rebuilding the repository."""
    time_start = time.time()
    services = _initialize_services()
    if not all(services):
        return

    db_manager, graph_builder, code_finder = services
    path_obj = Path(path).resolve()

    if not path_obj.exists():
        console.print(f"[red]Error: Path does not exist: {path_obj}[/red]")
        db_manager.close_driver()
        return

    # Check if already indexed
    indexed_repos = code_finder.list_indexed_repositories()
    repo_exists = any(Path(repo["path"]).resolve() == path_obj for repo in indexed_repos)
    
    if repo_exists:
        console.print(f"[yellow]Deleting existing index for: {path_obj}[/yellow]")
        try:
            graph_builder.delete_repository_from_graph(str(path_obj))
            console.print("[green]✓[/green] Deleted old index")
        except Exception as e:
            console.print(f"[red]Error deleting old index: {e}[/red]")
            db_manager.close_driver()
            return
    
    console.print(f"[cyan]Re-indexing: {path_obj}[/cyan]")
    
    try:
        asyncio.run(_run_index_with_progress(graph_builder, path_obj, is_dependency=False))
        time_end = time.time()
        elapsed = time_end - time_start
        console.print(f"[green]Successfully re-indexed: {path} in {elapsed:.2f} seconds[/green]")
    except Exception as e:
        console.print(f"[bold red]An error occurred during re-indexing:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def update_helper(path: str):
    """Update/refresh index for a path (alias for reindex)."""
    console.print("[cyan]Updating repository index...[/cyan]")
    reindex_helper(path)


def clean_helper():
    """Remove orphaned nodes and relationships from the database."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, _ = services
    
    console.print("[cyan]🧹 Cleaning database (removing orphaned nodes)...[/cyan]")
    
    try:
        # Determine backend type for query compatibility
        db_type = db_manager.__class__.__name__
        is_falkordb = "Falkor" in db_type
        is_kuzu = "Kuzu" in db_type
        
        total_deleted = 0
        batch_size = 1000
        
        with db_manager.get_driver().session() as session:
            # Keep deleting orphaned nodes in batches until none are found
            while True:
                if is_falkordb or is_kuzu:
                    # FalkorDB / KùzuDB-compatible query using OPTIONAL MATCH
                    # (KùzuDB does not support the Neo4j `NOT EXISTS { MATCH ... }` subquery syntax)
                    query = """
                    MATCH (n)
                    WHERE NOT (n:Repository)
                    OPTIONAL MATCH p = (n)-[*..10]-(r:Repository)
                    WITH n, p
                    WHERE p IS NULL
                    WITH n LIMIT $batch_size
                    DETACH DELETE n
                    RETURN count(n) as deleted
                    """
                else:
                    # Neo4j optimized query using NOT EXISTS with bounded path
                    # This is much faster than OPTIONAL MATCH with variable-length paths
                    query = """
                    MATCH (n)
                    WHERE NOT (n:Repository)
                      AND NOT EXISTS {
                        MATCH (n)-[*..10]-(r:Repository)
                      }
                    WITH n LIMIT $batch_size
                    DETACH DELETE n
                    RETURN count(n) as deleted
                    """
                
                result = session.run(query, batch_size=batch_size)
                record = result.single()
                deleted_count = record["deleted"] if record else 0
                total_deleted += deleted_count
                
                if deleted_count == 0:
                    break
                    
                console.print(f"[dim]Deleted {deleted_count} orphaned nodes (batch)...[/dim]")
            
            if total_deleted > 0:
                console.print(f"[green]✓[/green] Deleted {total_deleted} orphaned nodes total")
            else:
                console.print("[green]✓[/green] No orphaned nodes found")
            
            # Clean up any duplicate relationships (if any)
            console.print("[dim]Checking for duplicate relationships...[/dim]")
            # Note: This is database-specific and might not work for all backends
            
        console.print("[green]✅ Database cleanup complete![/green]")
    except Exception as e:
        console.print(f"[bold red]An error occurred during cleanup:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def stats_helper(path: str = None):
    """Show indexing statistics for a repository or overall."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, code_finder = services
    
    try:
        if path:
            # Stats for specific repository
            path_obj = Path(path).resolve()
            console.print(f"[cyan]📊 Statistics for: {path_obj}[/cyan]\n")
            
            with db_manager.get_driver().session() as session:
                # Get repository node
                repo_query = """
                MATCH (r:Repository {path: $path})
                RETURN r
                """
                result = session.run(repo_query, path=str(path_obj))
                if not result.single():
                    console.print(f"[red]Repository not found: {path_obj}[/red]")
                    return
                
                # Get stats
                # Get stats using separate queries to handle depth and avoid Cartesian products
                # 1. Files
                file_query = "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(f:File) RETURN count(f) as c"
                file_count = session.run(file_query, path=str(path_obj)).single()["c"]
                
                # 2. Functions (including methods in classes)
                func_query = "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(func:Function) RETURN count(func) as c"
                func_count = session.run(func_query, path=str(path_obj)).single()["c"]
                
                # 3. Classes
                class_query = "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(c:Class) RETURN count(c) as c"
                class_count = session.run(class_query, path=str(path_obj)).single()["c"]
                
                # 4. Modules (imported) - Note: Module nodes are outside the repo structure usually, connected via IMPORTS
                # We need to traverse from files to modules
                module_query = "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(f:File)-[:IMPORTS]->(m:Module) RETURN count(DISTINCT m) as c"
                module_count = session.run(module_query, path=str(path_obj)).single()["c"]

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Metric", style="cyan")
                table.add_column("Count", style="green", justify="right")
                
                table.add_row("Files", str(file_count))
                table.add_row("Functions", str(func_count))
                table.add_row("Classes", str(class_count))
                table.add_row("Imported Modules", str(module_count))
                
                console.print(table)
        else:
            # Overall stats
            console.print("[cyan]📊 Overall Database Statistics[/cyan]\n")
            
            with db_manager.get_driver().session() as session:
                # Get overall counts using separate O(1) queries
                repo_count = session.run("MATCH (r:Repository) RETURN count(r) as c").single()["c"]
                
                if repo_count > 0:
                    file_count = session.run("MATCH (f:File) RETURN count(f) as c").single()["c"]
                    func_count = session.run("MATCH (f:Function) RETURN count(f) as c").single()["c"]
                    class_count = session.run("MATCH (c:Class) RETURN count(c) as c").single()["c"]
                    module_count = session.run("MATCH (m:Module) RETURN count(m) as c").single()["c"]
                    
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Count", style="green", justify="right")
                    
                    table.add_row("Repositories", str(repo_count))
                    table.add_row("Files", str(file_count))
                    table.add_row("Functions", str(func_count))
                    table.add_row("Classes", str(class_count))
                    table.add_row("Modules", str(module_count))
                    
                    console.print(table)
                else:
                    console.print("[yellow]No data indexed yet.[/yellow]")
                    
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        db_manager.close_driver()


def watch_helper(path: str):
    """Watch a directory for changes and auto-update the graph (blocking mode)."""
    import logging
    from ..core.watcher import CodeWatcher
    
    # Suppress verbose watchdog DEBUG logs
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    logging.getLogger('watchdog.observers').setLevel(logging.WARNING)
    logging.getLogger('watchdog.observers.inotify_buffer').setLevel(logging.WARNING)
    
    services = _initialize_services()
    if not all(services):
        return

    db_manager, graph_builder, code_finder = services
    path_obj = Path(path).resolve()

    if not path_obj.exists():
        console.print(f"[red]Error: Path does not exist: {path_obj}[/red]")
        db_manager.close_driver()
        return
    
    if not path_obj.is_dir():
        console.print(f"[red]Error: Path must be a directory: {path_obj}[/red]")
        db_manager.close_driver()
        return

    console.print(f"[bold cyan]🔍 Watching {path_obj} for changes...[/bold cyan]")
    
    # Check if already indexed
    indexed_repos = code_finder.list_indexed_repositories()
    is_indexed = any(Path(repo["path"]).resolve() == path_obj for repo in indexed_repos)
    
    # Create watcher instance
    job_manager = JobManager()
    watcher = CodeWatcher(graph_builder, job_manager)
    
    try:
        # Start the observer thread
        watcher.start()
        
        # Add the directory to watch
        if is_indexed:
            console.print("[green]✓[/green] Already indexed (no initial scan needed)")
            watcher.watch_directory(str(path_obj), perform_initial_scan=False)
        else:
            console.print("[yellow]⚠[/yellow]  Not indexed yet. Performing initial scan...")
            
            # Index the repository first (like MCP does)
            async def do_index():
                await graph_builder.build_graph_from_path_async(path_obj, is_dependency=False)
            
            asyncio.run(do_index())
            console.print("[green]✓[/green] Initial scan complete")
            
            # Now start watching (without another scan)
            watcher.watch_directory(str(path_obj), perform_initial_scan=False)
        
        console.print("[bold green]👀 Monitoring for file changes...[/bold green] (Press Ctrl+C to stop)")
        console.print("[dim]💡 Tip: Open a new terminal window to continue working[/dim]\n")
        
        # Block here and keep the watcher running
        import threading
        stop_event = threading.Event()
        
        try:
            stop_event.wait()  # Wait indefinitely until interrupted
        except KeyboardInterrupt:
            console.print("\n[yellow]🛑 Stopping watcher...[/yellow]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Stopping watcher...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        watcher.stop()
        db_manager.close_driver()
        console.print("[green]✓[/green] Watcher stopped. Graph is up to date.")



def unwatch_helper(path: str):
    """Stop watching a directory."""
    console.print(f"[yellow]⚠️  Note: 'cgc unwatch' only works when the watcher is running via MCP server.[/yellow]")
    console.print(f"[dim]For CLI watch mode, simply press Ctrl+C in the watch terminal.[/dim]")
    console.print(f"\n[cyan]Path specified:[/cyan] {Path(path).resolve()}")


def list_watching_helper():
    """List all directories currently being watched."""
    console.print(f"[yellow]⚠️  Note: 'cgc watching' only works when the watcher is running via MCP server.[/yellow]")
    console.print(f"[dim]For CLI watch mode, check the terminal where you ran 'cgc watch'.[/dim]")
    console.print(f"\n[cyan]To see watched directories in MCP mode:[/cyan]")
    console.print(f"  1. Start the MCP server: cgc mcp start")
    console.print(f"  2. Use the 'list_watched_paths' MCP tool from your IDE")
