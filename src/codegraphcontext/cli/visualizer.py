import urllib.parse
from typing import Optional, List, Dict, Any, Set
from pathlib import Path
from .cli_helpers import visualize_helper

def check_visual_flag(ctx, visual: bool, cypher_query: str = None):
    """
    Helper to check the --visual flag and launch the visualizer.
    This is called from within analyze/find commands.
    """
    if visual and cypher_query:
        # We start the visualizer on port 8000
        # Passing empty repo handles showing just the query results
        port = 8000
        encoded_query = urllib.parse.quote(cypher_query)
        visualization_url = f"http://localhost:{port}/explore?cypher_query={encoded_query}"
        
        from rich.console import Console
        console = Console(stderr=True)
        console.print(f"[green]Starting visualizer...[/green]")
        console.print(f"[cyan]Visualizing results at:[/cyan] {visualization_url}")
        
        # Start the backend server and open the browser
        visualize_helper(repo_path=None, port=port)
        return True
    return False

def visualize_call_graph(cypher_query: str):
    """Visualize a call graph result."""
    visualize_helper(repo_path=None, port=8000)

def visualize_call_chain(cypher_query: str):
    """Visualize a call chain result."""
    visualize_helper(repo_path=None, port=8000)

def visualize_dependencies(cypher_query: str):
    """Visualize code dependencies."""
    visualize_helper(repo_path=None, port=8000)

def visualize_inheritance_tree(cypher_query: str):
    """Visualize class inheritance tree."""
    visualize_helper(repo_path=None, port=8000)

def visualize_overrides(cypher_query: str):
    """Visualize method overrides."""
    visualize_helper(repo_path=None, port=8000)

def visualize_search_results(cypher_query: str):
    """Visualize search results."""
    visualize_helper(repo_path=None, port=8000)
