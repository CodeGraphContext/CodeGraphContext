# src/codegraphcontext/cli/main.py
"""
This module defines the command-line interface (CLI) for the CodeGraphContext application.
It uses the Typer library to create a user-friendly and well-documented CLI.

Commands:
- mcp setup: Runs an interactive wizard to configure the MCP client.
- mcp start: Launches the main MCP server.
- help: Displays help information.
- version: Show the installed version.
"""
import typer
from rich.console import Console
from rich.table import Table
from rich import box
from typing import Optional
import asyncio
import logging
import json
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv, set_key
from importlib.metadata import version as pkg_version, PackageNotFoundError

from codegraphcontext.server import MCPServer
from codegraphcontext.core.database import DatabaseManager
from .setup_wizard import run_neo4j_setup_wizard, configure_mcp_client
from . import config_manager
# Import the new helper functions
from .cli_helpers import (
    index_helper,
    add_package_helper,
    list_repos_helper,
    delete_helper,
    cypher_helper,
    cypher_helper_visual,
    visualize_helper,
    reindex_helper,
    clean_helper,
    stats_helper,
    _initialize_services,
    watch_helper,
    unwatch_helper,
    list_watching_helper,
)

# Set the log level for the noisy neo4j, asyncio, and urllib3 loggers to WARNING to keep the output clean.
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


# Import visualization module
from .visualizer import (
    visualize_call_graph,
    visualize_call_chain,
    visualize_dependencies,
    visualize_inheritance_tree,
    visualize_overrides,
    visualize_search_results,
    check_visual_flag,
)

# Initialize the Typer app and Rich console for formatted output.
app = typer.Typer(
    name="cgc",
    help="CodeGraphContext: An MCP server for AI-powered code analysis.\n\n[DEPRECATED] 'cgc start' is deprecated. Use 'cgc mcp start' instead.",
    add_completion=True,
)
console = Console(stderr=True)

# Configure basic logging for the application.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


def get_version() -> str:
    """
    Try to read version from the installed package metadata.
    Fallback to a dev version if not installed.
    """
    try:
        return pkg_version("codegraphcontext")  # must match [project].name in pyproject.toml
    except PackageNotFoundError:
        return "0.0.0 (dev)"


# Create MCP command group
mcp_app = typer.Typer(help="MCP client configuration commands")
app.add_typer(mcp_app, name="mcp")

@mcp_app.command("setup")
def mcp_setup():
    """
    Configure MCP Client (IDE/CLI Integration).
    
    Sets up CodeGraphContext integration with your IDE or CLI tool:
    - VS Code, Cursor, Windsurf
    - Claude Desktop, Gemini CLI
    - Cline, RooCode, Amazon Q Developer
    
    Works with FalkorDB by default (no database setup needed).
    """
    console.print("\n[bold cyan]MCP Client Setup[/bold cyan]")
    console.print("Configure your IDE or CLI tool to use CodeGraphContext.\n")
    configure_mcp_client()

@mcp_app.command("start")
def mcp_start():
    """
    Start the CodeGraphContext MCP server.
    
    Starts the server which listens for JSON-RPC requests from stdin.
    This is used by IDE integrations (VS Code, Cursor, etc.).
    """
    console.print("[bold green]Starting CodeGraphContext Server...[/bold green]")
    _load_credentials()

    server = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Initialize and run the main server.
        server = MCPServer(loop=loop)
        loop.run_until_complete(server.run())
    except ValueError as e:
        # This typically happens if credentials are still not found after all checks.
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("Please run `cgc neo4j setup` or use FalkorDB (default).")
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        console.print("\n[bold yellow]Server stopped by user.[/bold yellow]")
    finally:
        # Ensure server and event loop are properly closed.
        if server:
            server.shutdown()
        loop.close()

@mcp_app.command("tools")
def mcp_tools():
    """
    List all available MCP tools.
    
    Shows all tools that can be called by AI assistants through the MCP interface.
    """
    _load_credentials()
    console.print("[bold green]Available MCP Tools:[/bold green]")
    try:
        # Instantiate the server to access the tool definitions.
        server = MCPServer()
        tools = server.tools.values()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Tool Name", style="dim", width=30)
        table.add_column("Description")

        for tool in sorted(tools, key=lambda t: t['name']):
            table.add_row(tool['name'], tool['description'])

        console.print(table)

    except ValueError as e:
        console.print(f"[bold red]Error loading tools:[/bold red] {e}")
        console.print("Please ensure your database is configured correctly.")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")

# Abbreviation for mcp setup
@app.command("m", rich_help_panel="Shortcuts")
def mcp_setup_alias():
    """Shortcut for 'cgc mcp setup'"""
    mcp_setup()


# Create Neo4j command group
neo4j_app = typer.Typer(help="Neo4j database configuration commands")
app.add_typer(neo4j_app, name="neo4j")

@neo4j_app.command("setup")
def neo4j_setup():
    """
    Configure Neo4j Database Connection.
    
    Choose from multiple setup options:
    - Local (Docker-based, recommended)
    - Local (Binary installation on Linux)
    - Hosted (Neo4j AuraDB or remote instance)
    - Connect to existing Neo4j instance
    
    Note: This is optional. CodeGraphContext works with FalkorDB by default.
    """
    console.print("\n[bold cyan]Neo4j Database Setup[/bold cyan]")
    console.print("Configure Neo4j database connection for CodeGraphContext.\n")
    run_neo4j_setup_wizard()

# Abbreviation for neo4j setup
@app.command("n", rich_help_panel="Shortcuts")
def neo4j_setup_alias():
    """Shortcut for 'cgc neo4j setup'"""
    neo4j_setup()



def _load_credentials():
    """
    Loads configuration and credentials from various sources into environment variables.
    Uses per-variable precedence - each variable is loaded from the highest priority source.
    Priority order (highest to lowest):
    1. Local `mcp.json` env vars (highest - explicit MCP server config)
    2. Local `.env` in project directory (high - project-specific overrides)
    3. Global `~/.codegraphcontext/.env` (lowest - user defaults)
    """
    from dotenv import dotenv_values
    
    # Collect all config sources in reverse priority order (lowest to highest)
    config_sources = []
    config_source_names = []
    
    # 3. Global .env file (lowest priority - user defaults)
    global_env_path = Path.home() / ".codegraphcontext" / ".env"
    if global_env_path.exists():
        try:
            config_sources.append(dotenv_values(str(global_env_path)))
            config_source_names.append(str(global_env_path))
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load global .env: {e}[/yellow]")
    
    # 2. Local project .env (higher priority - project-specific overrides)
    try:
        dotenv_path = find_dotenv(usecwd=True, raise_error_if_not_found=False)
        if dotenv_path:
            config_sources.append(dotenv_values(dotenv_path))
            config_source_names.append(str(dotenv_path))
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load .env from current directory: {e}[/yellow]")
    
    # 1. Local mcp.json (highest priority - explicit MCP server config)
    mcp_file_path = Path.cwd() / "mcp.json"
    if mcp_file_path.exists():
        try:
            with open(mcp_file_path, "r") as f:
                mcp_config = json.load(f)
            server_env = mcp_config.get("mcpServers", {}).get("CodeGraphContext", {}).get("env", {})
            if server_env:
                config_sources.append(server_env)
                config_source_names.append("mcp.json")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load mcp.json: {e}[/yellow]")
    
    # Merge all configs with proper precedence (later sources override earlier ones)
    merged_config = {}
    for config in config_sources:
        merged_config.update(config)
    
    # Apply merged config to environment
    for key, value in merged_config.items():
        if value is not None:  # Only set non-None values
            os.environ[key] = str(value)
    
    # Report what was loaded
    if config_source_names:
        if len(config_source_names) == 1:
            console.print(f"[dim]Loaded configuration from: {config_source_names[-1]}[/dim]")
        else:
            console.print(f"[dim]Loaded configuration from: {', '.join(config_source_names)} (highest priority: {config_source_names[-1]})[/dim]")
    else:
        console.print("[yellow]No configuration file found. Using defaults.[/yellow]")
    
    
    # Show which database is actually being used
    # Check for runtime override first (from -db/--database flag)
    runtime_db = os.environ.get("CGC_RUNTIME_DB_TYPE")
    if runtime_db:
        default_db = runtime_db.lower()
    else:
        default_db = os.environ.get("DEFAULT_DATABASE", "falkordb").lower()
    
    if default_db == "neo4j":
        has_neo4j_creds = all([
            os.environ.get("NEO4J_URI"),
            os.environ.get("NEO4J_USERNAME"),
            os.environ.get("NEO4J_PASSWORD")
        ])
        if has_neo4j_creds:
            console.print("[cyan]Using database: Neo4j[/cyan]")
        else:
            console.print("[yellow]⚠ DEFAULT_DATABASE=neo4j but credentials not found. Falling back to FalkorDB.[/yellow]")
    else:
        console.print("[cyan]Using database: FalkorDB[/cyan]")



# ============================================================================
# CONFIG COMMAND GROUP
# ============================================================================

config_app = typer.Typer(help="Manage configuration settings")
app.add_typer(config_app, name="config")

@config_app.command("show")
def config_show():
    """
    Display current configuration settings.
    
    Shows all configuration values including database, indexing options,
    logging settings, and performance tuning parameters.
    """
    config_manager.show_config()

@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Value to set")
):
    """
    Set a configuration value.
    
    Examples:
        cgc config set DEFAULT_DATABASE neo4j
        cgc config set INDEX_VARIABLES false
        cgc config set MAX_FILE_SIZE_MB 20
        cgc config set DEBUG_LOGS true
    """
    config_manager.set_config_value(key, value)

@config_app.command("reset")
def config_reset():
    """
    Reset all configuration to default values.
    
    This will restore all settings to their defaults.
    Your current configuration will be backed up.
    """
    if typer.confirm("Are you sure you want to reset all configuration to defaults?", default=False):
        config_manager.reset_config()
    else:
        console.print("[yellow]Reset cancelled[/yellow]")

@config_app.command("db")
def config_db(backend: str = typer.Argument(..., help="Database backend: 'neo4j' or 'falkordb'")):
    """
    Quickly switch the default database backend.
    
    Shortcut for 'cgc config set DEFAULT_DATABASE <backend>'.
    
    Examples:
        cgc config db neo4j
        cgc config db falkordb
    """
    backend = backend.lower()
    if backend not in ['falkordb', 'neo4j']:
        console.print(f"[bold red]Invalid backend: {backend}[/bold red]")
        console.print("Must be 'falkordb' or 'neo4j'")
        raise typer.Exit(code=1)
    
    config_manager.set_config_value("DEFAULT_DATABASE", backend)
    console.print(f"[green]✔ Default database switched to {backend}[/green]")

# ============================================================================
# BUNDLE COMMAND GROUP - Pre-indexed Graph Snapshots
# ============================================================================

bundle_app = typer.Typer(help="Create and load pre-indexed graph bundles")
app.add_typer(bundle_app, name="bundle")

@bundle_app.command("export")
def bundle_export(
    output: str = typer.Argument(..., help="Output path for the .cgc bundle file"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Specific repository path to export (default: export all)"),
    no_stats: bool = typer.Option(False, "--no-stats", help="Skip statistics generation")
):
    """
    Export the current graph to a portable .cgc bundle.
    
    Creates a pre-indexed graph snapshot that can be distributed and loaded
    instantly without re-indexing. Perfect for sharing famous repositories.
    
    Examples:
        cgc bundle export numpy.cgc --repo /path/to/numpy
        cgc bundle export my-project.cgc
        cgc bundle export all-repos.cgc --no-stats
    """
    _load_credentials()
    from codegraphcontext.core.cgc_bundle import CGCBundle
    
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        output_path = Path(output)
        repo_path = Path(repo).resolve() if repo else None
        
        console.print(f"[cyan]Exporting graph to {output_path}...[/cyan]")
        if repo_path:
            console.print(f"[dim]Repository: {repo_path}[/dim]")
        else:
            console.print(f"[dim]Exporting all repositories[/dim]")
        
        bundle = CGCBundle(db_manager)
        success, message = bundle.export_to_bundle(
            output_path,
            repo_path=repo_path,
            include_stats=not no_stats
        )
        
        if success:
            console.print(f"[bold green]{message}[/bold green]")
        else:
            console.print(f"[bold red]Export failed: {message}[/bold red]")
            raise typer.Exit(code=1)
    
    finally:
        db_manager.close_driver()

@bundle_app.command("import")
def bundle_import(
    bundle_file: str = typer.Argument(..., help="Path to the .cgc bundle file to import"),
    clear: bool = typer.Option(False, "--clear", help="Clear existing graph data before importing")
):
    """
    Import a .cgc bundle into the current database.
    
    Loads a pre-indexed graph snapshot into your database. Use --clear to
    replace all existing data with the bundle contents.
    
    Examples:
        cgc bundle import numpy.cgc
        cgc bundle import my-project.cgc --clear
    """
    _load_credentials()
    from codegraphcontext.core.cgc_bundle import CGCBundle
    
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        bundle_path = Path(bundle_file)
        
        if not bundle_path.exists():
            console.print(f"[bold red]Bundle file not found: {bundle_path}[/bold red]")
            raise typer.Exit(code=1)
        
        if clear:
            console.print("[yellow]⚠️  Warning: This will clear all existing graph data![/yellow]")
            if not typer.confirm("Are you sure you want to continue?", default=False):
                console.print("[yellow]Import cancelled[/yellow]")
                return
        
        console.print(f"[cyan]Importing bundle from {bundle_path}...[/cyan]")
        
        bundle = CGCBundle(db_manager)
        success, message = bundle.import_from_bundle(
            bundle_path,
            clear_existing=clear
        )
        
        if success:
            console.print(f"[bold green]{message}[/bold green]")
        else:
            console.print(f"[bold red]Import failed: {message}[/bold red]")
            raise typer.Exit(code=1)
    
    finally:
        db_manager.close_driver()

@bundle_app.command("load")
def bundle_load(
    bundle_name: str = typer.Argument(..., help="Bundle name or path to load (e.g., 'numpy' or 'numpy.cgc')"),
    clear: bool = typer.Option(False, "--clear", help="Clear existing graph data before loading")
):
    """
    Load a pre-indexed bundle (download if needed, then import).
    
    This is a convenience command that will:
    1. Check if the bundle exists locally
    2. Download from registry if not found
    3. Import the bundle into the database
    
    Examples:
        cgc load numpy
        cgc load numpy.cgc --clear
        cgc load /path/to/bundle.cgc
    """
    _load_credentials()
    
    bundle_path = Path(bundle_name)
    
    # If it's an absolute path or has .cgc extension and exists, use it directly
    if bundle_path.is_absolute() or (bundle_path.suffix == '.cgc' and bundle_path.exists()):
        bundle_import(str(bundle_path), clear=clear)
        return
    
    # Add .cgc extension if not present
    if not bundle_path.suffix:
        bundle_path = Path(f"{bundle_name}.cgc")
    
    # Check if exists locally
    if bundle_path.exists():
        console.print(f"[dim]Found local bundle: {bundle_path}[/dim]")
        bundle_import(str(bundle_path), clear=clear)
        return
    
    # Try to download from registry
    console.print(f"[yellow]Bundle '{bundle_name}' not found locally.[/yellow]")
    console.print(f"[cyan]Attempting to download from registry...[/cyan]")
    
    try:
        from .registry_commands import download_bundle
        
        # Extract just the name (without .cgc extension)
        name = bundle_path.stem
        
        # Download the bundle
        downloaded_path = download_bundle(name, output_dir=None, auto_load=True)
        
        if downloaded_path:
            # Import the downloaded bundle
            bundle_import(downloaded_path, clear=clear)
        else:
            console.print(f"[bold red]Failed to download bundle '{name}'[/bold red]")
            raise typer.Exit(code=1)
    
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        console.print(f"[dim]Use 'cgc registry list' to see available bundles[/dim]")
        raise typer.Exit(code=1)

# Shortcut commands at root level
@app.command("export", rich_help_panel="Bundle Shortcuts")
def export_shortcut(
    output: str = typer.Argument(..., help="Output path for the .cgc bundle file"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Specific repository path to export")
):
    """Shortcut for 'cgc bundle export'"""
    bundle_export(output, repo, False)

@app.command("load", rich_help_panel="Bundle Shortcuts")
def load_shortcut(
    bundle_name: str = typer.Argument(..., help="Bundle name or path to load"),
    clear: bool = typer.Option(False, "--clear", help="Clear existing graph data before loading")
):
    """Shortcut for 'cgc bundle load'"""
    bundle_load(bundle_name, clear)

# ============================================================================
# REGISTRY COMMAND GROUP - Browse and Download Bundles
# ============================================================================

registry_app = typer.Typer(help="Browse and download bundles from the registry")
app.add_typer(registry_app, name="registry")

@registry_app.command("list")
def registry_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information including download URLs"),
    unique: bool = typer.Option(False, "--unique", "-u", help="Show only one version per package (most recent)")
):
    """
    List all available bundles in the registry.
    
    Shows bundles from both weekly pre-indexed releases and on-demand generations.
    By default, shows all versions. Use --unique to see only the most recent version per package.
    
    Examples:
        cgc registry list
        cgc registry list --verbose
        cgc registry list --unique
    """
    from .registry_commands import list_bundles
    list_bundles(verbose=verbose, unique=unique)

@registry_app.command("search")
def registry_search(
    query: str = typer.Argument(..., help="Search query (matches name, repository, or description)")
):
    """
    Search for bundles in the registry.
    
    Searches bundle names, repositories, and descriptions for matches.
    
    Examples:
        cgc registry search numpy
        cgc registry search web
        cgc registry search http
    """
    from .registry_commands import search_bundles
    search_bundles(query)

@registry_app.command("download")
def registry_download(
    name: str = typer.Argument(..., help="Bundle name to download (e.g., 'numpy')"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory (default: current directory)"),
    load: bool = typer.Option(False, "--load", "-l", help="Automatically load the bundle after downloading")
):
    """
    Download a bundle from the registry.
    
    Downloads the specified bundle to the current directory or specified output directory.
    Use --load to automatically import the bundle after downloading.
    
    Examples:
        cgc registry download numpy
        cgc registry download pandas --output ./bundles
        cgc registry download fastapi --load
    """
    from .registry_commands import download_bundle
    
    bundle_path = download_bundle(name, output_dir, auto_load=load)
    
    if load and bundle_path:
        console.print(f"\n[cyan]Loading bundle...[/cyan]")
        bundle_import(bundle_path, clear=False)

@registry_app.command("request")
def registry_request(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to index"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for generation to complete (not yet implemented)")
):
    """
    Request on-demand generation of a bundle.
    
    Submits a request to generate a bundle for the specified GitHub repository.
    The bundle will be available in the registry after 5-10 minutes.
    
    Examples:
        cgc registry request https://github.com/encode/httpx
        cgc registry request https://github.com/pallets/flask
    """
    from .registry_commands import request_bundle
    request_bundle(repo_url, wait=wait)

# ============================================================================
# DOCTOR DIAGNOSTIC COMMAND
# ============================================================================

@app.command()
def doctor():
    """
    Run diagnostics to check system health and configuration.
    
    Checks:
    - Configuration validity
    - Database connectivity
    - Tree-sitter installation
    - Required dependencies
    - File permissions
    """
    console.print("[bold cyan]🏥 Running CodeGraphContext Diagnostics...[/bold cyan]\n")
    
    all_checks_passed = True
    
    # 1. Check configuration
    console.print("[bold]1. Checking Configuration...[/bold]")
    try:
        config = config_manager.load_config()
        console.print(f"   [green]✓[/green] Configuration loaded from {config_manager.CONFIG_FILE}")
        
        # Validate each config value
        invalid_configs = []
        for key, value in config.items():
            is_valid, error_msg = config_manager.validate_config_value(key, value)
            if not is_valid:
                invalid_configs.append(f"{key}: {error_msg}")
        
        if invalid_configs:
            console.print(f"   [red]✗[/red] Invalid configuration values found:")
            for err in invalid_configs:
                console.print(f"     - {err}")
            all_checks_passed = False
        else:
            console.print(f"   [green]✓[/green] All configuration values are valid")
    except Exception as e:
        console.print(f"   [red]✗[/red] Configuration error: {e}")
        all_checks_passed = False
    
    # 2. Check database connectivity
    console.print("\n[bold]2. Checking Database Connection...[/bold]")
    try:
        _load_credentials()
        default_db = config.get("DEFAULT_DATABASE", "falkordb")
        console.print(f"   Default database: {default_db}")
        
        if default_db == "neo4j":
            uri = os.environ.get("NEO4J_URI")
            username = os.environ.get("NEO4J_USERNAME")
            password = os.environ.get("NEO4J_PASSWORD")
            
            if uri and username and password:
                console.print(f"   [cyan]Testing Neo4j connection to {uri}...[/cyan]")
                is_connected, error_msg = DatabaseManager.test_connection(uri, username, password)
                if is_connected:
                    console.print(f"   [green]✓[/green] Neo4j connection successful")
                else:
                    console.print(f"   [red]✗[/red] Neo4j connection failed: {error_msg}")
                    all_checks_passed = False
            else:
                console.print(f"   [yellow]⚠[/yellow] Neo4j credentials not set. Run 'cgc neo4j setup'")
        else:
            # FalkorDB
            try:
                import falkordb
                console.print(f"   [green]✓[/green] FalkorDB Lite is installed")
            except ImportError:
                console.print(f"   [yellow]⚠[/yellow] FalkorDB Lite not installed (Python 3.12+ only)")
                console.print(f"       Run: pip install falkordblite")
    except Exception as e:
        console.print(f"   [red]✗[/red] Database check error: {e}")
        all_checks_passed = False
    
    # 3. Check tree-sitter installation
    console.print("\n[bold]3. Checking Tree-Sitter Installation...[/bold]")
    try:
        from tree_sitter import Language, Parser
        console.print(f"   [green]✓[/green] tree-sitter is installed")
        
        try:
            from tree_sitter_language_pack import get_language
            console.print(f"   [green]✓[/green] tree-sitter-language-pack is installed")
            
            # Test a few languages
            test_langs = ["python", "javascript", "typescript"]
            for lang in test_langs:
                try:
                    get_language(lang)
                    console.print(f"   [green]✓[/green] {lang} parser available")
                except Exception:
                    console.print(f"   [yellow]⚠[/yellow] {lang} parser not available")
        except ImportError:
            console.print(f"   [red]✗[/red] tree-sitter-language-pack not installed")
            all_checks_passed = False
    except ImportError as e:
        console.print(f"   [red]✗[/red] tree-sitter not installed: {e}")
        all_checks_passed = False
    
    # 4. Check file permissions
    console.print("\n[bold]4. Checking File Permissions...[/bold]")
    try:
        config_dir = config_manager.CONFIG_DIR
        if config_dir.exists():
            console.print(f"   [green]✓[/green] Config directory exists: {config_dir}")
            
            # Check if writable
            test_file = config_dir / ".test_write"
            try:
                test_file.touch()
                test_file.unlink()
                console.print(f"   [green]✓[/green] Config directory is writable")
            except Exception as e:
                console.print(f"   [red]✗[/red] Config directory not writable: {e}")
                all_checks_passed = False
        else:
            console.print(f"   [yellow]⚠[/yellow] Config directory doesn't exist, will be created on first use")
    except Exception as e:
        console.print(f"   [red]✗[/red] Permission check error: {e}")
        all_checks_passed = False
    
    # 5. Check cgc command availability
    console.print("\n[bold]5. Checking CGC Command...[/bold]")
    import shutil
    cgc_path = shutil.which("cgc")
    if cgc_path:
        console.print(f"   [green]✓[/green] cgc command found at: {cgc_path}")
    else:
        console.print(f"   [yellow]⚠[/yellow] cgc command not in PATH (using python -m cgc)")
    
    # Final summary
    console.print("\n" + "=" * 60)
    if all_checks_passed:
        console.print("[bold green]✅ All diagnostics passed! System is healthy.[/bold green]")
    else:
        console.print("[bold yellow]⚠️  Some issues detected. Please review the output above.[/bold yellow]")
        console.print("\n[cyan]Common fixes:[/cyan]")
        console.print("  • For Neo4j issues: Run 'cgc neo4j setup'")
        console.print("  • For missing packages: pip install codegraphcontext")
        console.print("  • For config issues: Run 'cgc config reset'")
    console.print("=" * 60 + "\n")




@app.command()
def start():
    """
    [DEPRECATED] Use 'cgc mcp start' instead. This command will be removed in a future version.
    """
    console.print("[yellow]⚠️  'cgc start' is deprecated. Use 'cgc mcp start' instead.[/yellow]")
    mcp_start()


@app.command()
def index(
    path: Optional[str] = typer.Argument(None, help="Path to the directory or file to index. Defaults to the current directory."),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-index (delete existing and rebuild)")
):
    """
    Indexes a directory or file by adding it to the code graph.
    If no path is provided, it indexes the current directory.
    
    Use --force to delete the existing index and rebuild from scratch.
    """
    _load_credentials()
    if path is None:
        path = str(Path.cwd())
    
    if force:
        console.print("[yellow]Force re-indexing (--force flag detected)[/yellow]")
        reindex_helper(path)
    else:
        index_helper(path)

@app.command()
def clean():
    """
    Remove orphaned nodes and relationships from the database.
    
    This will clean up nodes that are not connected to any repository,
    helping to keep your database tidy and performant.
    """
    _load_credentials()
    clean_helper()

@app.command()
def stats(path: Optional[str] = typer.Argument(None, help="Path to show stats for. Omit for overall stats.")):
    """
    Show indexing statistics.
    
    If a path is provided, shows stats for that specific repository.
    Otherwise, shows overall database statistics.
    """
    _load_credentials()
    if path:
        path = str(Path(path).resolve())
    stats_helper(path)

@app.command()
def delete(
    path: Optional[str] = typer.Argument(None, help="Path of the repository to delete from the code graph."),
    all_repos: bool = typer.Option(False, "--all", help="Delete all indexed repositories")
):
    """
    Deletes a repository from the code graph.
    
    Use --all to delete all repositories at once (requires confirmation).
    
    Examples:
        cgc delete ./my-project       # Delete specific repository
        cgc delete --all              # Delete all repositories
    """
    _load_credentials()
    
    if all_repos:
        # Delete all repositories
        services = _initialize_services()
        if not all(services):
            return
        db_manager, graph_builder, code_finder = services
        
        try:
            # Get list of repositories
            repos = code_finder.list_indexed_repositories()
            
            if not repos:
                console.print("[yellow]No repositories to delete.[/yellow]")
                return
            
            # Show what will be deleted
            console.print(f"\n[bold red]⚠️  WARNING: You are about to delete ALL {len(repos)} repositories![/bold red]\n")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan")
            table.add_column("Path", style="dim")
            
            for repo in repos:
                table.add_row(repo.get("name", ""), repo.get("path", ""))
            
            console.print(table)
            console.print()
            
            # Double confirmation
            if not typer.confirm("Are you sure you want to delete ALL repositories?", default=False):
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return
            
            console.print("[yellow]Please type 'delete all' to confirm:[/yellow] ", end="")
            confirmation = input()
            
            if confirmation.strip().lower() != "delete all":
                console.print("[yellow]Deletion cancelled. Confirmation text did not match.[/yellow]")
                return
            
            # Delete all repositories
            console.print("\n[cyan]Deleting all repositories...[/cyan]")
            deleted_count = 0
            
            for repo in repos:
                repo_path = repo.get("path", "")
                try:
                    graph_builder.delete_repository_from_graph(repo_path)
                    console.print(f"[green]✓[/green] Deleted: {repo.get('name', '')}")
                    deleted_count += 1
                except Exception as e:
                    console.print(f"[red]✗[/red] Failed to delete {repo.get('name', '')}: {e}")
            
            console.print(f"\n[bold green]Successfully deleted {deleted_count}/{len(repos)} repositories![/bold green]")
            
        finally:
            db_manager.close_driver()
    else:
        # Delete specific repository
        if not path:
            console.print("[red]Error: Please provide a path or use --all to delete all repositories[/red]")
            console.print("Usage: cgc delete <path> or cgc delete --all")
            raise typer.Exit(code=1)
        
        delete_helper(path)

@app.command()
def visualize(query: Optional[str] = typer.Argument(None, help="The Cypher query to visualize.")):
    """
    Generates a URL to visualize a Cypher query in the Neo4j Browser.
    If no query is provided, a default query will be used.
    """
    if query is None:
        query = "MATCH p=()-->() RETURN p"
    _load_credentials()
    visualize_helper(query)

@app.command("list")
def list_repositories():
    """
    List all indexed repositories.
    
    Shows all projects and packages that have been indexed in the code graph.
    """
    _load_credentials()
    list_repos_helper()

@app.command(name="add-package")
def add_package(package_name: str = typer.Argument(..., help="Name of the package to add."), language: str = typer.Argument(..., help="Language of the package." )):
    """
    Adds a package to the code graph.
    """
    _load_credentials()
    add_package_helper(package_name, language)

# ============================================================================
# WATCH COMMAND GROUP - Live File Monitoring
# ============================================================================

@app.command()
def watch(
    path: str = typer.Argument(".", help="Path to the directory to watch. Defaults to current directory.")
):
    """
    Watch a directory for file changes and automatically update the code graph.
    
    This command runs in the foreground and monitors the specified directory
    for any file changes. When changes are detected, the code graph is
    automatically updated.
    
    The watcher will:
    - Perform an initial scan if the directory is not yet indexed
    - Monitor for file creation, modification, deletion, and moves
    - Automatically re-index affected files and update relationships
    
    Press Ctrl+C to stop watching.
    
    Examples:
        cgc watch .                    # Watch current directory
        cgc watch /path/to/project     # Watch specific directory
        cgc w .                        # Using shortcut alias
    """
    _load_credentials()
    watch_helper(path)

@app.command()
def unwatch(
    path: str = typer.Argument(..., help="Path to stop watching")
):
    """
    Stop watching a directory for changes.
    
    Note: This command is primarily for MCP server mode.
    For CLI watch mode, simply press Ctrl+C in the watch terminal.
    
    Examples:
        cgc unwatch /path/to/project
    """
    _load_credentials()
    unwatch_helper(path)

@app.command()
def watching():
    """
    List all directories currently being watched for changes.
    
    Note: This command is primarily for MCP server mode.
    For CLI watch mode, check the terminal where you ran 'cgc watch'.
    
    Examples:
        cgc watching
    """
    _load_credentials()
    list_watching_helper()



# ============================================================================
# FIND COMMAND GROUP - Code Search & Discovery
# ============================================================================

find_app = typer.Typer(help="Find and search code elements")
app.add_typer(find_app, name="find")

@find_app.command("name")
def find_by_name(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Exact name to search for"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type (function, class, file, module)"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Find code elements by exact name.
    
    Examples:
        cgc find name MyClass
        cgc find name calculate --type function
        cgc find name MyClass --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = []
        
        # Search based on type filter
        if type is None or type.lower() == 'all':
            funcs = code_finder.find_by_function_name(name, fuzzy_search=False)
            classes = code_finder.find_by_class_name(name, fuzzy_search=False)
            variables = code_finder.find_by_variable_name(name)
            modules = code_finder.find_by_module_name(name)
            imports = code_finder.find_imports(name)

            for f in funcs: f['type'] = 'Function'
            for c in classes: c['type'] = 'Class'
            for v in variables: v['type'] = 'Variable'
            for m in modules: m['type'] = 'Module'; m['path'] = m.get('name', 'External') # Modules might differ
            for i in imports: 
                i['type'] = 'Import'
                i['name'] = i.get('alias') or i.get('imported_name')
            
            results.extend(funcs)
            results.extend(classes)
            results.extend(variables)
            results.extend(modules)
            results.extend(imports)
        
        elif type.lower() == 'function':
            results = code_finder.find_by_function_name(name, fuzzy_search=False)
            for r in results: r['type'] = 'Function'
            
        elif type.lower() == 'class':
            results = code_finder.find_by_class_name(name, fuzzy_search=False)
            for r in results: r['type'] = 'Class'
            
        elif type.lower() == 'variable':
            results = code_finder.find_by_variable_name(name)
            for r in results: r['type'] = 'Variable'

        elif type.lower() == 'module':
            results = code_finder.find_by_module_name(name)
            for r in results: 
                r['type'] = 'Module'
                r['path'] = r.get('name')
            
        elif type.lower() == 'file':
            # Quick query for file
            with db_manager.get_driver().session() as session:
                res = session.run("MATCH (n:File) WHERE n.name = $name RETURN n.name as name, n.path as path, n.is_dependency as is_dependency", name=name)
                results = [dict(record) for record in res]
                for r in results: r['type'] = 'File'
        
        if not results:
            console.print(f"[yellow]No code elements found with name '{name}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_search_results(results, name, search_type="name")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="bold blue")
        table.add_column("Location", style="dim", overflow="fold")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('name', ''),
                res.get('type', 'Unknown'),
                location_str
            )
            
        console.print(f"[cyan]Found {len(results)} matches for '{name}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("pattern")
def find_by_pattern(
    ctx: typer.Context,
    pattern: str = typer.Argument(..., help="Substring pattern to search (fuzzy search fallback)"),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", "-c", help="Case-sensitive search"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Find code elements using substring matching.
    
    Examples:
        cgc find pattern "Auth"       # Finds Auth, Authentication, Authorize...
        cgc find pattern "process_"   # Finds process_data, process_request...
        cgc find pattern "Auth" --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        with db_manager.get_driver().session() as session:
            # Search Functions, Classes, and Modules
            # Note: FalkorDB Lite might not support regex, using CONTAINS
            
            if not case_sensitive:
                query = """
                    MATCH (n)
                    WHERE (n:Function OR n:Class OR n:Module OR n:Variable) AND toLower(n.name) CONTAINS toLower($pattern)
                    RETURN 
                        labels(n)[0] as type,
                        n.name as name,
                        n.path as path,
                        n.line_number as line_number,
                        n.is_dependency as is_dependency
                    ORDER BY n.is_dependency ASC, n.name
                    LIMIT 50
                """
            else:
                 query = """
                    MATCH (n)
                    WHERE (n:Function OR n:Class OR n:Module OR n:Variable) AND n.name CONTAINS $pattern
                    RETURN 
                        labels(n)[0] as type,
                        n.name as name,
                        n.path as path,
                        n.line_number as line_number,
                        n.is_dependency as is_dependency
                    ORDER BY n.is_dependency ASC, n.name
                    LIMIT 50
                """
            
            result = session.run(query, pattern=pattern)
            
            results = [dict(record) for record in result]
        
        if not results:
            console.print(f"[yellow]No matches found for pattern '{pattern}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_search_results(results, pattern, search_type="pattern")
            return
            
        if not case_sensitive and any(c in pattern for c in "*?["):
             console.print("[yellow]Note: Wildcards/Regex are not fully supported in this mode. Performing substring search.[/yellow]")

        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Location", style="dim", overflow="fold")
        table.add_column("Source", style="yellow")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', '') if res.get('line_number') is not None else '')
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('name', ''),
                res.get('type', 'Unknown'),
                location_str,
                "📦 Dependency" if res.get('is_dependency') else "📝 Project"
            )
            
        console.print(f"[cyan]Found {len(results)} matches for pattern '{pattern}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("type")
def find_by_type(
    ctx: typer.Context,
    element_type: str = typer.Argument(..., help="Type to search for (function, class, file, module)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results to return"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Find all elements of a specific type.
    
    Examples:
        cgc find type class
        cgc find type function --limit 100
        cgc find type class --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_by_type(element_type, limit)
        
        if not results:
            console.print(f"[yellow]No elements found of type '{element_type}'[/yellow]")
            return
        
        # Add type to results for visualization
        for r in results:
            r['type'] = element_type.capitalize()
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_search_results(results, element_type, search_type="type")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        table.add_column("Source", style="yellow")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path
            
            table.add_row(
                res.get('name', ''),
                location_str,
                "📦 Dependency" if res.get('is_dependency') else "📝 Project"
            )
            
        console.print(f"[cyan]Found {len(results)} {element_type}s:[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("variable")
def find_by_variable(
    name: str = typer.Argument(..., help="Variable name to search for")
):
    """
    Find variables by name.
    
    Examples:
        cgc find variable MAX_RETRIES
        cgc find variable config
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_by_variable_name(name)
        
        if not results:
            console.print(f"[yellow]No variables found with name '{name}'[/yellow]")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        table.add_column("Context", style="yellow")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('name', ''),
                location_str,
                res.get('context', '') or 'module'
            )
            
        console.print(f"[cyan]Found {len(results)} variable(s) named '{name}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("content")
def find_by_content_search(
    query: str = typer.Argument(..., help="Text to search for in source code and docstrings")
):
    """
    Search code content (source and docstrings) using full-text index.
    
    Examples:
        cgc find content "error 503"
        cgc find content "TODO: refactor"
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        try:
            results = code_finder.find_by_content(query)
        except Exception as e:
            error_msg = str(e).lower()
            if ('fulltext' in error_msg or 'db.index.fulltext' in error_msg) and "Falkor" in db_manager.__class__.__name__:
                console.print("\n[bold red]❌ Full-text search is not supported on FalkorDB[/bold red]\n")
                console.print("[yellow]💡 You have two options:[/yellow]\n")
                console.print("  1. [cyan]Switch to Neo4j:[/cyan]")
                console.print(f"     [dim]cgc --database neo4j find content \"{query}\"[/dim]\n")
                console.print("  2. [cyan]Use pattern search instead:[/cyan]")
                console.print(f"     [dim]cgc find pattern \"{query}\"[/dim]")
                console.print("     [dim](searches in names only, not source code)[/dim]\n")
                return
            else:
                # Re-raise if it's a different error
                raise
        
        if not results:
            console.print(f"[yellow]No content matches found for '{query}'[/yellow]")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Location", style="dim", overflow="fold")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('name', ''),
                res.get('type', 'Unknown'),
                location_str
            )
            
        console.print(f"[cyan]Found {len(results)} content match(es) for '{query}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("decorator")
def find_by_decorator_search(
    decorator: str = typer.Argument(..., help="Decorator name to search for"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path")
):
    """
    Find functions with a specific decorator.
    
    Examples:
        cgc find decorator app.route
        cgc find decorator test --file tests/test_main.py
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_functions_by_decorator(decorator, file)
        
        if not results:
            console.print(f"[yellow]No functions found with decorator '@{decorator}'[/yellow]")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Function", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        table.add_column("Decorators", style="yellow")
        
        for res in results:
            decorators_str = ", ".join(res.get('decorators', []))
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('function_name', ''),
                location_str,
                decorators_str
            )
            
        console.print(f"[cyan]Found {len(results)} function(s) with decorator '@{decorator}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@find_app.command("argument")
def find_by_argument_search(
    argument: str = typer.Argument(..., help="Argument/parameter name to search for"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path")
):
    """
    Find functions that take a specific argument/parameter.
    
    Examples:
        cgc find argument password
        cgc find argument user_id --file src/auth.py
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_functions_by_argument(argument, file)
        
        if not results:
            console.print(f"[yellow]No functions found with argument '{argument}'[/yellow]")
            return
            
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Function", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        
        for res in results:
            path = res.get('path', '') or ''
            line_str = str(res.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('function_name', ''),
                location_str
            )
            
        console.print(f"[cyan]Found {len(results)} function(s) with argument '{argument}':[/cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()


# ============================================================================
# ANALYZE COMMAND GROUP - Code Analysis & Relationships
# ============================================================================

analyze_app = typer.Typer(help="Analyze code relationships, dependencies, and quality")
app.add_typer(analyze_app, name="analyze")

@analyze_app.command("calls")
def analyze_calls(
    ctx: typer.Context,
    function: str = typer.Argument(..., help="Function name to analyze"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Show what functions this function calls (callees).
    
    Example:
        cgc analyze calls process_data
        cgc analyze calls process_data --file src/main.py
        cgc analyze calls process_data --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.what_does_function_call(function, file)
        
        if not results:
            console.print(f"[yellow]No function calls found for '{function}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_call_graph(results, function, direction="outgoing")
            return
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Called Function", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        table.add_column("Type", style="yellow")
        
        for result in results:
            path = result.get("called_file_path", "")
            line_str = str(result.get("called_line_number", ""))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                result.get("called_function", ""),
                location_str,
                "📦 Dependency" if result.get("called_is_dependency") else "📝 Project"
            )
        
        console.print(f"\n[bold cyan]Function '{function}' calls:[/bold cyan]")
        console.print(table)
        console.print(f"\n[dim]Total: {len(results)} function(s)[/dim]")
    finally:
        db_manager.close_driver()

@analyze_app.command("callers")
def analyze_callers(
    ctx: typer.Context,
    function: str = typer.Argument(..., help="Function name to analyze"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Show what functions call this function.
    
    Example:
        cgc analyze callers process_data
        cgc analyze callers process_data --file src/main.py
        cgc analyze callers process_data --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.who_calls_function(function, file)
        
        if not results:
            console.print(f"[yellow]No callers found for '{function}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_call_graph(results, function, direction="incoming")
            return
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Caller Function", style="cyan")
        table.add_column("Location", style="green")
        table.add_column("Call Type", style="yellow")

        
        for result in results:
            path = result.get("caller_file_path", "")
            line_number = result.get("caller_line_number")

            location = f"{path}:{line_number}" if line_number else path

            table.add_row(
                result.get("caller_function", ""),
                location,
                "📦 Dependency" if result.get("caller_is_dependency") else "📝 Project"
                )
        
        console.print(f"\n[bold cyan]Functions that call '{function}':[/bold cyan]")
        console.print(table)
        console.print(f"\n[dim]Total: {len(results)} caller(s)[/dim]")
    finally:
        db_manager.close_driver()

@analyze_app.command("chain")
def analyze_chain(
    ctx: typer.Context,
    from_func: str = typer.Argument(..., help="Starting function"),
    to_func: str = typer.Argument(..., help="Target function"),
    max_depth: int = typer.Option(5, "--depth", "-d", help="Maximum call chain depth"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="File for starting function"),
    to_file: Optional[str] = typer.Option(None, "--to-file", help="File for target function"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Show call chain between two functions.
    
    Example:
        cgc analyze chain main process_data --depth 10
        cgc analyze chain main process --from-file main.py --to-file utils.py
        cgc analyze chain main process_data --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_function_call_chain(from_func, to_func, max_depth, from_file, to_file)
        
        if not results:
            console.print(f"[yellow]No call chain found between '{from_func}' and '{to_func}' within depth {max_depth}[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_call_chain(results, from_func, to_func)
            return
        
        for idx, chain in enumerate(results, 1):
            console.print(f"\n[bold cyan]Call Chain #{idx} (length: {chain.get('chain_length', 0)}):[/bold cyan]")
            
            functions = chain.get('function_chain', [])
            call_details = chain.get('call_details', [])
            
            for i, func in enumerate(functions):
                indent = "  " * i
                
                # Print function
                console.print(f"{indent}[cyan]{func.get('name', 'Unknown')}[/cyan] [dim]({func.get('path', '')}:{func.get('line_number', '')})[/dim]")
                
                # If there is a next step, print the connecting call detail
                if i < len(functions) - 1 and i < len(call_details):
                    detail = call_details[i]
                    line = detail.get('call_line', '?')
                    
                    # Format args for display
                    args_info = ""
                    args_val = detail.get('args', [])
                    if args_val:
                        if isinstance(args_val, list):
                            # Filter legacy punctuation just in case
                            clean_args = [str(a) for a in args_val if str(a) not in ('(', ')', ',')]
                            args_str = ", ".join(clean_args)
                        else:
                            args_str = str(args_val)
                            
                        # Truncate if too long
                        if len(args_str) > 50:
                            args_str = args_str[:47] + "..."
                        args_info = f" [dim]({args_str})[/dim]"
                    
                    console.print(f"{indent}  ⬇ [dim]calls at line {line}[/dim]{args_info}")
    finally:
        db_manager.close_driver()

@analyze_app.command("deps")
def analyze_dependencies(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Module name"),
    show_external: bool = typer.Option(True, "--external/--no-external", help="Show external dependencies"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Show dependencies and imports for a module.
    
    Example:
        cgc analyze deps numpy
        cgc analyze deps mymodule --no-external
        cgc analyze deps mymodule --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_module_dependencies(target)
        
        if not results.get('importers') and not results.get('imports'):
            console.print(f"[yellow]No dependency information found for '{target}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_dependencies(results, target)
            return
        
        # Show who imports this module
        if results.get('importers'):
            console.print(f"\n[bold cyan]Files that import '{target}':[/bold cyan]")
            table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            table.add_column("Location", style="cyan", overflow="fold")
            
            for imp in results['importers']:
                path = imp.get('importer_file_path', '')
                line_str = str(imp.get('import_line_number', ''))
                location_str = f"{path}:{line_str}" if line_str else path

                table.add_row(
                    location_str
                )
            console.print(table)
    finally:
        db_manager.close_driver()

@analyze_app.command("tree")
def analyze_inheritance_tree(
    ctx: typer.Context,
    class_name: str = typer.Argument(..., help="Class name"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Show inheritance hierarchy for a class.
    
    Example:
        cgc analyze tree MyClass
        cgc analyze tree MyClass --file src/models.py
        cgc analyze tree MyClass --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_class_hierarchy(class_name, file)
        
        # Check if visual mode is enabled (check for any hierarchy data)
        has_hierarchy = results.get('parent_classes') or results.get('child_classes')
        if check_visual_flag(ctx, visual):
            if has_hierarchy:
                visualize_inheritance_tree(results, class_name)
            else:
                console.print(f"[yellow]No inheritance hierarchy to visualize for '{class_name}'[/yellow]")
            return
        
        console.print(f"\n[bold cyan]Class Hierarchy for '{class_name}':[/bold cyan]\n")
        
        # Show parent classes
        if results.get('parent_classes'):
            console.print("[bold yellow]Parents (inherits from):[/bold yellow]")
            for parent in results['parent_classes']:
                console.print(f"  ⬆ [cyan]{parent.get('parent_class', '')}[/cyan] [dim]({parent.get('parent_file_path', '')}:{parent.get('parent_line_number', '')})[/dim]")
        else:
            console.print("[dim]No parent classes found[/dim]")
        
        console.print()
        
        # Show child classes
        if results.get('child_classes'):
            console.print("[bold yellow]Children (classes that inherit from this):[/bold yellow]")
            for child in results['child_classes']:
                console.print(f"  ⬇ [cyan]{child.get('child_class', '')}[/cyan] [dim]({child.get('child_file_path', '')}:{child.get('child_line_number', '')})[/dim]")
        else:
            console.print("[dim]No child classes found[/dim]")
        
        console.print()
        
        # Show methods
        if results.get('methods'):
            console.print(f"[bold yellow]Methods ({len(results['methods'])}):[/bold yellow]")
            for method in results['methods'][:10]:  # Limit to 10
                console.print(f"  • [green]{method.get('method_name', '')}[/green]({method.get('method_args', '')})")
            if len(results['methods']) > 10:
                console.print(f"  [dim]... and {len(results['methods']) - 10} more[/dim]")
    finally:
        db_manager.close_driver()

@analyze_app.command("complexity")
def analyze_complexity(
    path: Optional[str] = typer.Argument(None, help="Specific function name to analyze"),
    threshold: int = typer.Option(10, "--threshold", "-t", help="Complexity threshold for warnings"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to show"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path (only used when function name is provided)")
):
    """
    Show cyclomatic complexity for functions.
    
    Example:
        cgc analyze complexity                    # Most complex functions
        cgc analyze complexity --threshold 15     # Functions over threshold
        cgc analyze complexity my_function        # Specific function
        cgc analyze complexity my_function -f file.py # Specific function in file
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        if path:
            # Specific function
            result = code_finder.get_cyclomatic_complexity(path, file)
            if result:
                console.print(f"\n[bold cyan]Complexity for '{path}':[/bold cyan]")
                console.print(f"  Cyclomatic Complexity: [yellow]{result.get('complexity', 'N/A')}[/yellow]")
                console.print(f"  File: [dim]{result.get('path', '')}[/dim]")
                console.print(f"  Line: [dim]{result.get('line_number', '')}[/dim]")
            else:
                console.print(f"[yellow]Function '{path}' not found or has no complexity data[/yellow]")
        else:
            # Most complex functions
            results = code_finder.find_most_complex_functions(limit)
            
            if not results:
                console.print("[yellow]No complexity data available[/yellow]")
                return
            
            table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            table.add_column("Function", style="cyan")
            table.add_column("Complexity", style="yellow", justify="right")
            table.add_column("Location", style="dim", overflow="fold")
            
            for func in results:
                complexity = func.get('complexity', 0)
                color = "red" if complexity > threshold else "yellow" if complexity > threshold/2 else "green"
                path = func.get('path', '')
                line_str = str(func.get('line_number', ''))
                location_str = f"{path}:{line_str}" if line_str else path

                table.add_row(
                    func.get('function_name', ''),
                    f"[{color}]{complexity}[/{color}]",
                    location_str
                )
            
            console.print(f"\n[bold cyan]Most Complex Functions (threshold: {threshold}):[/bold cyan]")
            console.print(table)
            console.print(f"\n[dim]{len([f for f in results if f.get('complexity', 0) > threshold])} function(s) exceed threshold[/dim]")
    finally:
        db_manager.close_driver()

@analyze_app.command("dead-code")
def analyze_dead_code(
    path: Optional[str] = typer.Argument(None, help="Path to analyze (not yet implemented)"),
    exclude_decorators: Optional[str] = typer.Option(None, "--exclude", "-e", help="Comma-separated decorators to exclude")
):
    """
    Find potentially unused functions and classes.
    
    Example:
        cgc analyze dead-code
        cgc analyze dead-code --exclude route,task,api
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        exclude_list = exclude_decorators.split(',') if exclude_decorators else []
        results = code_finder.find_dead_code(exclude_list)
        
        unused_funcs = results.get('potentially_unused_functions', [])
        
        if not unused_funcs:
            console.print("[green]✓ No dead code found![/green]")
            return
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Function", style="cyan")
        table.add_column("Location", style="dim", overflow="fold")
        
        for func in unused_funcs:
            path = func.get('path', '')
            line_str = str(func.get('line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                func.get('function_name', ''),
                location_str
            )
        
        console.print(f"\n[bold yellow]⚠️  Potentially Unused Functions:[/bold yellow]")
        console.print(table)
        console.print(f"\n[dim]Total: {len(unused_funcs)} function(s)[/dim]")
        console.print(f"[dim]Note: {results.get('note', '')}[/dim]")
    finally:
        db_manager.close_driver()

@analyze_app.command("overrides")
def analyze_overrides(
    ctx: typer.Context,
    function_name: str = typer.Argument(..., help="Function/method name to find implementations of"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Find all implementations of a function across different classes.
    
    Useful for finding polymorphic implementations and method overrides.
    
    Example:
        cgc analyze overrides area
        cgc analyze overrides process
        cgc analyze overrides area --visual
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        results = code_finder.find_function_overrides(function_name)
        
        if not results:
            console.print(f"[yellow]No implementations found for function '{function_name}'[/yellow]")
            return
        
        # Check if visual mode is enabled
        if check_visual_flag(ctx, visual):
            visualize_overrides(results, function_name)
            return
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Class", style="cyan")
        table.add_column("Function", style="green")
        table.add_column("Location", style="dim", overflow="fold")
        
        for res in results:
            path = res.get('class_file_path', '')
            line_str = str(res.get('function_line_number', ''))
            location_str = f"{path}:{line_str}" if line_str else path

            table.add_row(
                res.get('class_name', ''),
                res.get('function_name', ''),
                location_str
            )
        
        console.print(f"\n[bold cyan]Found {len(results)} implementation(s) of '{function_name}':[/bold cyan]")
        console.print(table)
    finally:
        db_manager.close_driver()

@analyze_app.command("variable")
def analyze_variable_usage(
    variable_name: str = typer.Argument(..., help="Variable name to analyze"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file path")
):
    """
    Analyze where a variable is defined and used across the codebase.
    
    Shows all instances of the variable and their scope (function, class, module).
    
    Example:
        cgc analyze variable MAX_RETRIES
        cgc analyze variable config
        cgc analyze variable x --file math_utils.py
    """
    _load_credentials()
    services = _initialize_services()
    if not all(services):
        return
    db_manager, graph_builder, code_finder = services
    
    try:
        # Get variable usage scope
        scope_results = code_finder.find_variable_usage_scope(variable_name, file)
        instances = scope_results.get('instances', [])
        
        if not instances:
            console.print(f"[yellow]No instances found for variable '{variable_name}'[/yellow]")
            return
        
        console.print(f"\n[bold cyan]Variable '{variable_name}' Usage Analysis:[/bold cyan]\n")
        
        # Group by scope type
        by_scope = {}
        for inst in instances:
            scope_type = inst.get('scope_type', 'unknown')
            if scope_type not in by_scope:
                by_scope[scope_type] = []
            by_scope[scope_type].append(inst)
        
        # Display by scope
        for scope_type, items in by_scope.items():
            console.print(f"[bold yellow]{scope_type.upper()} Scope ({len(items)} instance(s)):[/bold yellow]")
            
            table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            table.add_column("Scope Name", style="cyan")
            table.add_column("Location", style="dim", overflow="fold")
            table.add_column("Value", style="yellow")
            
            for item in items:
                path = item.get('path', '')
                line_str = str(item.get('line_number', ''))
                location_str = f"{path}:{line_str}" if line_str else path

                table.add_row(
                    item.get('scope_name', ''),
                    location_str,
                    str(item.get('variable_value', ''))[:50] if item.get('variable_value') else '-'
                )
            
            console.print(table)
            console.print()
        
        console.print(f"[dim]Total: {len(instances)} instance(s) across {len(by_scope)} scope type(s)[/dim]")
    finally:
        db_manager.close_driver()


# ============================================================================
# QUERY COMMAND - Raw Cypher Queries
# ============================================================================

@app.command("query")
def query_graph(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Cypher query to execute (read-only)"),
    visual: bool = typer.Option(False, "--visual", "--viz", "-V", help="Show results as interactive graph visualization")
):
    """
    Execute a custom Cypher query on the code graph.
    
    Examples:
        cgc query "MATCH (f:Function) RETURN f.name LIMIT 10"
        cgc query "MATCH (c:Class)-[:CONTAINS]->(m) RETURN c.name, count(m)"
        cgc query "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50" --visual
    """
    _load_credentials()
    
    # Check if visual mode is enabled
    if check_visual_flag(ctx, visual):
        cypher_helper_visual(query)
    else:
        cypher_helper(query)

# Keep old 'cypher' as alias for backward compatibility
@app.command("cypher", hidden=True)
def cypher_legacy(query: str = typer.Argument(..., help="The read-only Cypher query to execute.")):
    """[Deprecated] Use 'cgc query' instead."""
    console.print("[yellow]⚠️  'cgc cypher' is deprecated. Use 'cgc query' instead.[/yellow]")
    cypher_helper(query)



# ============================================================================
# ABBREVIATIONS / SHORTCUTS for common commands
# ============================================================================

@app.command("i", rich_help_panel="Shortcuts")
def index_abbrev(
    path: Optional[str] = typer.Argument(None, help="Path to index"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-index (delete existing and rebuild)")
):
    """Shortcut for 'cgc index'"""
    index(path, force=force)

@app.command("ls", rich_help_panel="Shortcuts")
def list_abbrev():
    """Shortcut for 'cgc list'"""
    list_repositories()

@app.command("rm", rich_help_panel="Shortcuts")
def delete_abbrev(
    path: Optional[str] = typer.Argument(None, help="Path to delete"),
    all_repos: bool = typer.Option(False, "--all", help="Delete all indexed repositories")
):
    """Shortcut for 'cgc delete'"""
    delete(path, all_repos)

@app.command("v", rich_help_panel="Shortcuts")
def visualize_abbrev(query: Optional[str] = typer.Argument(None, help="Cypher query")):
    """Shortcut for 'cgc visualize'"""
    visualize(query)

@app.command("w", rich_help_panel="Shortcuts")
def watch_abbrev(path: str = typer.Argument(".", help="Path to watch")):
    """Shortcut for 'cgc watch'"""
    watch(path)


# ============================================================================



@app.command()
def help(ctx: typer.Context):
    """Show the main help message and exit."""
    root_ctx = ctx.parent or ctx
    typer.echo(root_ctx.get_help())


@app.command("version")
def version_cmd():
    """Show the application version."""
    console.print(f"CodeGraphContext [bold cyan]{get_version()}[/bold cyan]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    database: Optional[str] = typer.Option(
        None, 
        "--database", 
        "-db", 
        help="[Global] Temporarily override database backend (falkordb or neo4j) for any command"
    ),
    visual: bool = typer.Option(
        False,
        "--visual",
        "--viz",
        "-V",
        help="[Global] Show results as interactive graph visualization in browser"
    ),
    version_: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="[Root-level only] Show version and exit",
        is_eager=True,
    ),
    help_: bool = typer.Option(
        None,
        "--help",
        "-h",
        help="[Root-level only] Show help and exit",
        is_eager=True,
    ), 
):
    """
    Main entry point for the cgc CLI application.
    If no subcommand is provided, it displays a welcome message with instructions.
    """
    # Initialize context object for sharing state with subcommands
    ctx.ensure_object(dict)
    
    if database:
        os.environ["CGC_RUNTIME_DB_TYPE"] = database

    # Store visual flag in context for subcommands to access
    if visual:
        ctx.obj["visual"] = True

    if version_:
        console.print(f"CodeGraphContext [bold cyan]{get_version()}[/bold cyan]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print("[bold green]👋 Welcome to CodeGraphContext (cgc)![/bold green]\n")
        console.print("CodeGraphContext is both an [bold cyan]MCP server[/bold cyan] and a [bold cyan]CLI toolkit[/bold cyan] for code analysis.\n")
        console.print("🤖 [bold]For MCP Server Mode (AI assistants):[/bold]")
        console.print("   1. Run [cyan]cgc mcp setup[/cyan] (or [cyan]cgc m[/cyan]) to configure your IDE")
        console.print("   2. Run [cyan]cgc mcp start[/cyan] to launch the server\n")
        console.print("🛠️  [bold]For CLI Toolkit Mode (direct usage):[/bold]")
        console.print("   • [cyan]cgc index .[/cyan] - Index your current directory")
        console.print("   • [cyan]cgc list[/cyan] - List indexed repositories\n")
        console.print("📊 [bold]Using Neo4j instead of FalkorDB?[/bold]")
        console.print("     Run [cyan]cgc neo4j setup[/cyan] (or [cyan]cgc n[/cyan]) to configure Neo4j\n")
        console.print("📈 [bold]Want visual graph output?[/bold]")
        console.print("     Add [cyan]-V[/cyan] or [cyan]--visual[/cyan] to any analyze/find command\n")
        console.print("👉 Run [cyan]cgc help[/cyan] to see all available commands")
        console.print("👉 Run [cyan]cgc --version[/cyan] to check the version\n")
        console.print("👉 Running [green]codegraphcontext[/green] works the same as using [green]cgc[/green]")


if __name__ == "__main__":
    app()