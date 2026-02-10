# src/codegraphcontext/cli/cli_helpers.py
import asyncio
import json
import urllib.parse
from pathlib import Path
import time
from rich.console import Console
from rich.table import Table

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
    except ValueError as e:
        console.print(f"[bold red]Database Connection Error:[/bold red] {e}")
        console.print("Please ensure your Neo4j credentials are correct and the database is running.")
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
    console.print("[yellow]This may take a few minutes for large repositories...[/yellow]")

    async def do_index():
        await graph_builder.build_graph_from_path_async(path_obj, is_dependency=False)

    try:
        asyncio.run(do_index())
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
    console.print("[yellow]This may take a few minutes...[/yellow]")

    async def do_index():
        await graph_builder.build_graph_from_path_async(package_path, is_dependency=True)

    try:
        asyncio.run(do_index())
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


import webbrowser

def visualize_helper(query: str):
    """Generates a visualization."""
    services = _initialize_services()
    if not all(services):
        return

    db_manager, _, _ = services
    
    # Check if FalkorDB
    if "FalkorDB" in db_manager.__class__.__name__:
        _visualize_falkordb(db_manager)
    else:
        try:
            encoded_query = urllib.parse.quote(query)
            visualization_url = f"http://localhost:7474/browser/?cmd=edit&arg={encoded_query}"
            console.print("[green]Graph visualization URL:[/green]")
            console.print(visualization_url)
            console.print("Open the URL in your browser to see the graph.")
        except Exception as e:
            console.print(f"[bold red]An error occurred while generating URL:[/bold red] {e}")
        finally:
            db_manager.close_driver()

def _visualize_falkordb(db_manager):
    console.print("[dim]Generating FalkorDB visualization (showing up to 500 relationships)...[/dim]")
    try:
        data_nodes = []
        data_edges = []
        
        with db_manager.get_driver().session() as session:
            # Fetch nodes and edges
            q = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 500"
            result = session.run(q)
            
            seen_nodes = set()
            
            for record in result:
                # record values are Node/Relationship objects from falkordb client
                n = record['n']
                r = record['r']
                m = record['m']
                
                # Process Node helper
                def process_node(node):
                    nid = getattr(node, 'id', -1)
                    labels = getattr(node, 'labels', [])
                    lbl = list(labels)[0] if labels else "Node"
                    props = getattr(node, 'properties', {})
                    name = props.get('name', str(nid))
                    
                    if nid not in seen_nodes:
                        seen_nodes.add(nid)
                        color = "#97c2fc" # Default blue
                        if "Repository" in labels: color = "#ffb3ba" # Red
                        elif "File" in labels: color = "#baffc9" # Green
                        elif "Class" in labels: color = "#bae1ff" # Light Blue
                        elif "Function" in labels: color = "#ffffba" # Yellow
                        elif "Package" in labels: color = "#ffdfba" # Orange
                        
                        data_nodes.append({
                            "id": nid, 
                            "label": name, 
                            "group": lbl, 
                            "title": str(props),
                            "color": color
                        })
                    return nid

                nid = process_node(n)
                mid = process_node(m)
                
                # Check Edge
                e_type = getattr(r, 'relation', '') or getattr(r, 'type', 'REL')
                data_edges.append({
                    "from": nid,
                    "to": mid,
                    "label": e_type,
                    "arrows": "to"
                })
        
        filename = "codegraph_viz.html"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <title>CodeGraphContext Visualization</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style type="text/css">
    #mynetwork {{
      width: 100%;
      height: 100vh;
      border: 1px solid lightgray;
    }}
  </style>
</head>
<body>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(data_nodes)});
    var edges = new vis.DataSet({json.dumps(data_edges)});
    var container = document.getElementById('mynetwork');
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
        nodes: {{ shape: 'dot', size: 16 }},
        physics: {{ stabilization: false }},
        layout: {{ improvedLayout: false }}
    }};
    var network = new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
        
        out_path = Path(filename).resolve()
        with open(out_path, "w") as f:
            f.write(html_content)
            
        console.print(f"[green]Visualization generated at:[/green] {out_path}")
        console.print("Opening in default browser...")
        webbrowser.open(f"file://{out_path}")

    except Exception as e:
        console.print(f"[bold red]Visualization failed:[/bold red] {e}")
        import traceback
        traceback.print_exc()
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
    console.print("[yellow]This may take a few minutes for large repositories...[/yellow]")

    async def do_index():
        await graph_builder.build_graph_from_path_async(path_obj, is_dependency=False)

    try:
        asyncio.run(do_index())
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
        # Determine if we're using FalkorDB or Neo4j for query optimization
        db_type = db_manager.__class__.__name__
        is_falkordb = "Falkor" in db_type
        
        total_deleted = 0
        batch_size = 1000
        
        with db_manager.get_driver().session() as session:
            # Keep deleting orphaned nodes in batches until none are found
            while True:
                if is_falkordb:
                    # FalkorDB-compatible query using OPTIONAL MATCH
                    query = """
                    MATCH (n)
                    WHERE NOT (n:Repository)
                    OPTIONAL MATCH path = (n)-[*..10]-(r:Repository)
                    WITH n, path
                    WHERE path IS NULL
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
