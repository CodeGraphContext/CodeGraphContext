# src/codegraphcontext/cli/registry_commands.py
"""
CLI commands for interacting with the CodeGraphContext bundle registry.
Allows users to list, search, download, and request bundles from the command line.
"""

import requests
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
from typing import Optional, List, Dict, Any
import time

console = Console()

GITHUB_ORG = "CodeGraphContext"
GITHUB_REPO = "CodeGraphContext"
REGISTRY_API_URL = f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/releases"
MANIFEST_URL = f"https://github.com/{GITHUB_ORG}/{GITHUB_REPO}/releases/download/on-demand-bundles/manifest.json"


def fetch_available_bundles() -> List[Dict[str, Any]]:
    """
    Fetch all available bundles from GitHub Releases.
    Returns a list of bundle dictionaries with metadata.
    Preserves all versions - no deduplication.
    """
    all_bundles = []
    
    try:
        # 1. Fetch on-demand bundles from manifest
        try:
            response = requests.get(MANIFEST_URL, timeout=10)
            if response.status_code == 200:
                manifest = response.json()
                if manifest.get('bundles'):
                    for bundle in manifest['bundles']:
                        bundle['source'] = 'on-demand'
                        # Ensure bundle has a full_name field (with version info)
                        if 'bundle_name' in bundle:
                            # Extract full name without .cgc extension
                            bundle['full_name'] = bundle['bundle_name'].replace('.cgc', '')
                        all_bundles.append(bundle)
        except Exception as e:
            console.print(f"[dim]Note: Could not fetch on-demand bundles: {e}[/dim]")
        
        # 2. Fetch weekly pre-indexed bundles
        try:
            response = requests.get(REGISTRY_API_URL, timeout=10)
            if response.status_code == 200:
                releases = response.json()
                
                # Find weekly releases (bundles-YYYYMMDD pattern)
                weekly_releases = [r for r in releases if r['tag_name'].startswith('bundles-') and r['tag_name'] != 'bundles-latest']
                
                if weekly_releases:
                    # Get the most recent weekly release
                    latest_weekly = weekly_releases[0]
                    
                    for asset in latest_weekly.get('assets', []):
                        if asset['name'].endswith('.cgc'):
                            # Full bundle name without extension
                            full_name = asset['name'].replace('.cgc', '')
                            
                            # Parse bundle name
                            name_parts = full_name.split('-')
                            bundle = {
                                'name': name_parts[0],  # Base package name
                                'full_name': full_name,  # Complete name with version
                                'repo': f"{name_parts[0]}/{name_parts[0]}",  # Simplified
                                'bundle_name': asset['name'],
                                'version': name_parts[1] if len(name_parts) > 1 else 'latest',
                                'commit': name_parts[2] if len(name_parts) > 2 else 'unknown',
                                'size': f"{asset['size'] / 1024 / 1024:.1f}MB",
                                'download_url': asset['browser_download_url'],
                                'generated_at': asset['updated_at'],
                                'source': 'weekly'
                            }
                            all_bundles.append(bundle)
        except Exception as e:
            console.print(f"[dim]Note: Could not fetch weekly bundles: {e}[/dim]")
        
        # Normalize all bundles to have required fields
        for bundle in all_bundles:
            # Ensure 'name' field exists (base package name)
            if 'name' not in bundle:
                repo = bundle.get('repo', '')
                if '/' in repo:
                    bundle['name'] = repo.split('/')[-1]
                else:
                    # Extract from full_name or bundle_name
                    full_name = bundle.get('full_name', bundle.get('bundle_name', 'unknown'))
                    bundle['name'] = full_name.split('-')[0]
            
            # Ensure 'full_name' exists
            if 'full_name' not in bundle:
                bundle['full_name'] = bundle.get('bundle_name', bundle.get('name', 'unknown')).replace('.cgc', '')
        
        # NO DEDUPLICATION - Keep all versions
        return all_bundles
    
    except Exception as e:
        console.print(f"[bold red]Error fetching bundles: {e}[/bold red]")
        return []


def _get_base_package_name(bundle_name: str) -> str:
    """
    Extract base package name from full bundle name.
    
    Examples:
        'python-bitcoin-utils-main-61d1969' -> 'python-bitcoin-utils'
        'flask-main-abc123' -> 'flask'
        'requests' -> 'requests'
    """
    # Remove .cgc extension if present
    name = bundle_name.replace('.cgc', '')
    
    # Split by hyphen and take the first part
    # This assumes package names don't contain hyphens (may need refinement)
    parts = name.split('-')
    
    # For multi-word package names like 'python-bitcoin-utils',
    # we need smarter logic. For now, take first part.
    # TODO: Improve this with a known package list or better heuristics
    return parts[0]


def list_bundles(verbose: bool = False, unique: bool = False):
    """
    Display all available bundles in a table.
    
    Args:
        verbose: Show additional details like download URLs
        unique: Show only one version per package (most recent)
    """
    console.print("[cyan]Fetching available bundles...[/cyan]")
    
    bundles = fetch_available_bundles()
    
    if not bundles:
        console.print("[yellow]No bundles found in registry.[/yellow]")
        console.print("[dim]The registry may be empty or unreachable.[/dim]")
        return
    
    # If unique flag is set, keep only the most recent version per package
    if unique:
        unique_bundles = {}
        for bundle in bundles:
            base_name = bundle.get('name', 'unknown')
            # Keep the one with the most recent timestamp
            if base_name not in unique_bundles:
                unique_bundles[base_name] = bundle
            else:
                # Compare timestamps (generated_at field)
                current_time = bundle.get('generated_at', '')
                existing_time = unique_bundles[base_name].get('generated_at', '')
                if current_time > existing_time:
                    unique_bundles[base_name] = bundle
        bundles = list(unique_bundles.values())
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", title="Available Bundles")
    table.add_column("Bundle Name", style="cyan", no_wrap=True)
    table.add_column("Repository", style="dim")
    table.add_column("Version", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Source", style="yellow")
    
    if verbose:
        table.add_column("Download URL", style="blue", no_wrap=False)
    
    # Sort by full_name to group versions together
    bundles.sort(key=lambda b: (b.get('name', ''), b.get('full_name', '')))
    
    for bundle in bundles:
        # Use full_name for display (includes version info)
        display_name = bundle.get('full_name', bundle.get('name', 'unknown'))
        repo = bundle.get('repo', 'unknown')
        version = bundle.get('version', bundle.get('tag', 'latest'))
        size = bundle.get('size', 'unknown')
        source = bundle.get('source', 'unknown')
        
        if verbose:
            download_url = bundle.get('download_url', 'N/A')
            table.add_row(display_name, repo, version, size, source, download_url)
        else:
            table.add_row(display_name, repo, version, size, source)
    
    console.print(table)
    console.print(f"\n[dim]Total bundles: {len(bundles)}[/dim]")
    if unique:
        console.print("[dim]Showing only most recent version per package. Use without --unique to see all versions.[/dim]")
    else:
        console.print("[dim]Use --unique to show only one version per package[/dim]")
    console.print("[dim]Use 'cgc registry download <name>' to download a bundle[/dim]")


def search_bundles(query: str):
    """Search for bundles matching the query."""
    console.print(f"[cyan]Searching for '{query}'...[/cyan]")
    
    bundles = fetch_available_bundles()
    
    if not bundles:
        console.print("[yellow]No bundles found in registry.[/yellow]")
        return
    
    # Filter bundles
    query_lower = query.lower()
    matching_bundles = [
        b for b in bundles
        if query_lower in b.get('name', '').lower() or
           query_lower in b.get('repo', '').lower() or
           query_lower in b.get('description', '').lower()
    ]
    
    if not matching_bundles:
        console.print(f"[yellow]No bundles found matching '{query}'[/yellow]")
        console.print("[dim]Try a different search term or use 'cgc registry list' to see all bundles[/dim]")
        return
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", title=f"Search Results for '{query}'")
    table.add_column("Name", style="cyan")
    table.add_column("Repository", style="dim")
    table.add_column("Version", style="green")
    table.add_column("Size", justify="right")
    
    for bundle in matching_bundles:
        name = bundle.get('name', 'unknown')
        repo = bundle.get('repo', 'unknown')
        version = bundle.get('version', bundle.get('tag', 'latest'))
        size = bundle.get('size', 'unknown')
        table.add_row(name, repo, version, size)
    
    console.print(table)
    console.print(f"\n[dim]Found {len(matching_bundles)} matching bundle(s)[/dim]")


def download_bundle(name: str, output_dir: Optional[str] = None, auto_load: bool = False):
    """
    Download a bundle from the registry.
    
    Supports both full names (e.g., 'python-bitcoin-utils-main-61d1969')
    and base names (e.g., 'python-bitcoin-utils' - picks most recent version).
    """
    console.print(f"[cyan]Looking for bundle '{name}'...[/cyan]")
    
    bundles = fetch_available_bundles()
    
    if not bundles:
        console.print("[bold red]Could not fetch bundle registry.[/bold red]")
        raise typer.Exit(code=1)
    
    # Strategy 1: Try exact match on full_name (with version)
    bundle = None
    for b in bundles:
        if b.get('full_name', '').lower() == name.lower():
            bundle = b
            console.print(f"[dim]Found exact match: {b.get('full_name')}[/dim]")
            break
    
    # Strategy 2: If no exact match, try matching base package name
    # and pick the most recent version
    if not bundle:
        matching_bundles = []
        for b in bundles:
            if b.get('name', '').lower() == name.lower():
                matching_bundles.append(b)
        
        if matching_bundles:
            # Sort by timestamp and pick the most recent
            matching_bundles.sort(key=lambda x: x.get('generated_at', ''), reverse=True)
            bundle = matching_bundles[0]
            
            console.print(f"[yellow]Multiple versions found for '{name}'. Using most recent:[/yellow]")
            console.print(f"[cyan]  → {bundle.get('full_name')}[/cyan]")
            
            if len(matching_bundles) > 1:
                console.print(f"\n[dim]Other available versions:[/dim]")
                for b in matching_bundles[1:4]:  # Show up to 3 alternatives
                    console.print(f"[dim]  • {b.get('full_name')}[/dim]")
                if len(matching_bundles) > 4:
                    console.print(f"[dim]  ... and {len(matching_bundles) - 4} more[/dim]")
                console.print()
    
    # Strategy 3: No match found - show suggestions
    if not bundle:
        # Find bundles with similar base names
        suggestions = []
        name_lower = name.lower()
        for b in bundles:
            base_name = b.get('name', '').lower()
            full_name = b.get('full_name', '').lower()
            
            # Fuzzy matching: check if search term is in base or full name
            if name_lower in base_name or name_lower in full_name:
                suggestions.append(b.get('full_name', b.get('name', 'unknown')))
        
        console.print(f"[bold red]Bundle '{name}' not found in registry.[/bold red]")
        
        if suggestions:
            console.print("\n[yellow]Did you mean one of these?[/yellow]")
            for suggestion in suggestions[:5]:  # Show top 5
                console.print(f"  • {suggestion}")
        
        console.print("\n[dim]Use 'cgc registry list' to see all available bundles[/dim]")
        raise typer.Exit(code=1)
    
    # Get download URL
    download_url = bundle.get('download_url')
    if not download_url:
        console.print(f"[bold red]No download URL found for bundle '{name}'[/bold red]")
        raise typer.Exit(code=1)
    
    # Determine output path
    bundle_filename = bundle.get('bundle_name', f"{name}.cgc")
    if output_dir:
        output_path = Path(output_dir) / bundle_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd() / bundle_filename
    
    # Check if already exists
    if output_path.exists():
        console.print(f"[yellow]Bundle already exists: {output_path}[/yellow]")
        if not typer.confirm("Overwrite?", default=False):
            console.print("[yellow]Download cancelled[/yellow]")
            if auto_load:
                console.print(f"[cyan]Using existing bundle for loading...[/cyan]")
                return str(output_path)
            return
        output_path.unlink()
    
    # Download with progress bar
    try:
        console.print(f"[cyan]Downloading {bundle_filename}...[/cyan]")
        console.print(f"[dim]From: {download_url}[/dim]")
        
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Downloading {bundle.get('size', 'unknown')}...", total=total_size)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
        
        console.print(f"[bold green]✓ Downloaded successfully: {output_path}[/bold green]")
        
        if auto_load:
            return str(output_path)
        else:
            console.print(f"[dim]Load with: cgc load {output_path}[/dim]")
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Download failed: {e}[/bold red]")
        if output_path.exists():
            output_path.unlink()
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        if output_path.exists():
            output_path.unlink()
        raise typer.Exit(code=1)


def request_bundle(repo_url: str, wait: bool = False):
    """Request on-demand generation of a bundle."""
    console.print(f"[cyan]Requesting bundle generation for: {repo_url}[/cyan]")
    
    # Validate GitHub URL
    if not repo_url.startswith('https://github.com/'):
        console.print("[bold red]Invalid GitHub URL. Must start with 'https://github.com/'[/bold red]")
        raise typer.Exit(code=1)
    
    # For now, provide instructions to use the website
    # In the future, this could trigger the workflow via GitHub API
    console.print("\n[yellow]Note: Bundle generation requires GitHub authentication.[/yellow]")
    console.print("[cyan]Please use one of these methods:[/cyan]\n")
    
    console.print("1. [bold]Via Website (Recommended):[/bold]")
    console.print(f"   Visit: https://codegraphcontext.vercel.app")
    console.print(f"   Enter: {repo_url}")
    console.print(f"   Click 'Generate Bundle'\n")
    
    console.print("2. [bold]Via GitHub Actions (Manual):[/bold]")
    console.print(f"   Go to: https://github.com/{GITHUB_ORG}/{GITHUB_REPO}/actions")
    console.print(f"   Select: 'Generate Bundle On-Demand'")
    console.print(f"   Click: 'Run workflow'")
    console.print(f"   Enter: {repo_url}\n")
    
    console.print("[dim]Bundle generation typically takes 5-10 minutes.[/dim]")
    console.print("[dim]Use 'cgc registry list' to check when it's available.[/dim]")
    
    if wait:
        console.print("\n[yellow]Note: Automatic waiting not yet implemented.[/yellow]")
        console.print("[dim]Please check back in 5-10 minutes and use 'cgc registry download <name>'[/dim]")


def load_bundle_command(bundle_name: str, clear_existing: bool = False):
    """
    Load a bundle (for MCP tool integration).
    
    This is a wrapper around download_bundle that returns structured data
    instead of using console output and typer.Exit.
    
    Args:
        bundle_name: Name of the bundle to load
        clear_existing: Whether to clear existing data before loading
        
    Returns:
        Tuple of (success: bool, message: str, stats: dict)
    """
    from pathlib import Path
    from .cli_helpers import _initialize_services
    from ..core.cgc_bundle import CGCBundle
    
    try:
        # Initialize services
        services = _initialize_services()
        if not all(services):
            return (False, "Failed to initialize database services", {})
        
        db_manager, _, _ = services
        
        # Check if bundle exists locally
        bundle_path = Path(bundle_name)
        if not bundle_path.exists():
            # Try to download from registry
            try:
                download_bundle(bundle_name, output_dir=None, auto_load=False)
                # After download, the file should exist
                if not bundle_path.exists():
                    # Try with .cgc extension
                    bundle_path = Path(f"{bundle_name}.cgc")
                    if not bundle_path.exists():
                        return (False, f"Bundle not found: {bundle_name}", {})
            except Exception as e:
                return (False, f"Failed to download bundle: {str(e)}", {})
        
        # Load the bundle
        bundle = CGCBundle(db_manager)
        success, message = bundle.import_from_bundle(
            bundle_path=bundle_path,
            clear_existing=clear_existing
        )
        
        if success:
            # Extract stats from message if available
            stats = {}
            if "Nodes:" in message and "Edges:" in message:
                try:
                    parts = message.split("|")
                    for part in parts:
                        if "Nodes:" in part:
                            stats["nodes"] = int(part.split(":")[1].strip().replace(",", ""))
                        elif "Edges:" in part:
                            stats["edges"] = int(part.split(":")[1].strip().replace(",", ""))
                except:
                    pass
            
            return (True, message, stats)
        else:
            return (False, message, {})
    
    except Exception as e:
        return (False, f"Error loading bundle: {str(e)}", {})
    finally:
        if 'db_manager' in locals():
            db_manager.close_driver()

