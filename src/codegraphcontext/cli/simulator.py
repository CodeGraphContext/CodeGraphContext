# src/codegraphcontext/cli/simulator.py
import json
import typer
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from codegraphcontext.core.simulator import CodeGraphTwin, EvolutionTimeline
from codegraphcontext.cli.cli_helpers import _initialize_services

simulate_app = typer.Typer(help="Repository Digital Twin & Architectural Evolution Simulator")
console = Console()


def get_repo_path(path: Optional[str]) -> str:
    """Resolves and returns repository path as absolute path string."""
    if path is None:
        return str(Path.cwd().resolve())
    return str(Path(path).resolve())


def load_cgc_credentials(context: Optional[str]):
    """Loads CGC credentials dynamically to prevent circular imports."""
    from codegraphcontext.cli.main import _load_credentials
    _load_credentials(context)


def print_metrics(summary: Dict[str, Any], title: str = "Architectural Metrics Summary"):
    """Prints the metrics summary in a rich formatted table."""
    # Maintainability Panel
    score = summary["maintainability_score"]
    color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    
    console.print(Panel(
        f"[bold]Maintainability Score:[/bold] [{color}]{score}/100[/{color}]\n"
        f"[bold]Active Nodes:[/bold] {summary['nodes_count']} | [bold]External References:[/bold] {summary['external_nodes_count']} | [bold]Total Edges:[/bold] {summary['edges_count']}\n"
        f"[bold]Circular Dependency Groups:[/bold] {summary['circular_dependencies_count']}",
        title=title,
        border_style=color
    ))

    # Circular dependencies
    if summary["circular_dependencies_count"] > 0:
        console.print("\n[bold red]Circular Dependency Cycles Detected:[/bold red]")
        for i, group in enumerate(summary["circular_dependency_groups"], 1):
            cycle_str = " -> ".join([f"[cyan]{n['name']}[/cyan]" for n in group])
            cycle_str += f" -> [cyan]{group[0]['name']}[/cyan]"
            console.print(f"  {i}. {cycle_str}")

    # Services Coupling Table
    coupling_table = Table(title="\nServices Boundary Coupling Analysis", show_header=True, header_style="bold magenta")
    coupling_table.add_column("Service Name", style="cyan")
    coupling_table.add_column("Afferent Coupling (Ca)", justify="right")
    coupling_table.add_column("Efferent Coupling (Ce)", justify="right")
    coupling_table.add_column("Instability Index (I)", justify="right", style="yellow")
    
    services_coupling = summary["coupling"]["services"]
    for sname, data in services_coupling.items():
        if sname in ("External", "Unknown"):
            continue
        coupling_table.add_row(
            sname,
            str(data["ca"]),
            str(data["ce"]),
            f"{data['instability']:.2f}"
        )
    console.print(coupling_table)

    # Services Cohesion Table
    cohesion_table = Table(title="\nServices Boundary Cohesion Analysis", show_header=True, header_style="bold magenta")
    cohesion_table.add_column("Service Name", style="cyan")
    cohesion_table.add_column("Nodes Count", justify="right")
    cohesion_table.add_column("Internal Edges", justify="right")
    cohesion_table.add_column("Outgoing Edges", justify="right")
    cohesion_table.add_column("Cohesion Density", justify="right", style="yellow")
    cohesion_table.add_column("Internal Ratio", justify="right", style="green")

    cohesion_data = summary["cohesion"]
    for sname, data in cohesion_data.items():
        if sname in ("External", "Unknown"):
            continue
        cohesion_table.add_row(
            sname,
            str(data["nodes_count"]),
            str(data["internal_edges"]),
            str(data["external_outgoing_edges"]),
            f"{data['cohesion_density']:.3f}",
            f"{data['internal_edge_ratio']:.2f}"
        )
    console.print(cohesion_table)


@simulate_app.command("metrics")
def simulate_metrics(
    path: Optional[str] = typer.Argument(None, help="Path to the directory to simulate. Defaults to the current directory."),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Specific context to use"),
):
    """
    Measure architectural health metrics (coupling, cohesion, circular dependencies, complexity, and maintainability) of the repository.
    """
    load_cgc_credentials(context)
    repo_path = get_repo_path(path)
    
    services = _initialize_services(context)
    db_manager = services[0]

    try:
        twin = CodeGraphTwin(repo_path).load_from_db(db_manager)
        summary = twin.get_metrics_summary()
        print_metrics(summary, f"Architectural Metrics: {twin.repo_name}")
    except Exception as e:
        console.print(f"[bold red]Simulation Error:[/bold red] {e}")
    finally:
        db_manager.close_driver()


@simulate_app.command("run")
def simulate_run(
    config_path: str = typer.Argument(..., help="Path to the simulation JSON configuration file."),
    path: Optional[str] = typer.Argument(None, help="Path to the directory to simulate. Defaults to the current directory."),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Specific context to use"),
):
    """
    Run architectural mutations defined in a simulation scenario JSON file and view the resulting architecture metrics.
    """
    load_cgc_credentials(context)
    repo_path = get_repo_path(path)
    
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        console.print(f"[bold red]Scenario configuration file not found:[/bold red] {config_path}")
        raise typer.Exit(code=1)

    try:
        with open(cfg_file, "r") as f:
            scenario = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Failed to parse scenario JSON file:[/bold red] {e}")
        raise typer.Exit(code=1)

    services = _initialize_services(context)
    db_manager = services[0]

    try:
        twin = CodeGraphTwin(repo_path).load_from_db(db_manager)
        
        # Apply steps
        steps = scenario.get("steps", [])
        for step in steps:
            stype = step.get("type")
            if stype == "decompose":
                twin.decompose_service(step.get("mapping", {}))
            elif stype == "remove_dependency":
                twin.remove_dependency(step.get("source"), step.get("target"), step.get("rel_type"))
            elif stype == "add_dependency":
                twin.add_dependency(step.get("source"), step.get("target"), step.get("rel_type"))
            elif stype == "remove_node":
                twin.remove_node(step.get("node_id"))
                
        summary = twin.get_metrics_summary()
        print_metrics(summary, f"Simulated Twin: {scenario.get('name', 'Custom Scenario')}")
    except Exception as e:
        console.print(f"[bold red]Simulation Error:[/bold red] {e}")
    finally:
        db_manager.close_driver()


@simulate_app.command("compare")
def simulate_compare(
    config_path: str = typer.Argument(..., help="Path to the simulation JSON configuration file."),
    path: Optional[str] = typer.Argument(None, help="Path to the directory to simulate. Defaults to the current directory."),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Specific context to use"),
):
    """
    Compare current architecture metrics against the proposed architecture after applying simulated changes.
    """
    load_cgc_credentials(context)
    repo_path = get_repo_path(path)
    
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        console.print(f"[bold red]Scenario configuration file not found:[/bold red] {config_path}")
        raise typer.Exit(code=1)

    try:
        with open(cfg_file, "r") as f:
            scenario = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Failed to parse scenario JSON file:[/bold red] {e}")
        raise typer.Exit(code=1)

    services = _initialize_services(context)
    db_manager = services[0]

    try:
        baseline = CodeGraphTwin(repo_path).load_from_db(db_manager)
        simulated = CodeGraphTwin(repo_path).load_from_db(db_manager)
        
        # Apply simulated steps
        steps = scenario.get("steps", [])
        for step in steps:
            stype = step.get("type")
            if stype == "decompose":
                simulated.decompose_service(step.get("mapping", {}))
            elif stype == "remove_dependency":
                simulated.remove_dependency(step.get("source"), step.get("target"), step.get("rel_type"))
            elif stype == "add_dependency":
                simulated.add_dependency(step.get("source"), step.get("target"), step.get("rel_type"))
            elif stype == "remove_node":
                simulated.remove_node(step.get("node_id"))
                
        diff = baseline.compare_scenarios(simulated)
        
        # Render comparison table
        table = Table(title=f"Scenario Comparison: Baseline vs {scenario.get('name', 'Simulated')}", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Baseline Value", justify="right")
        table.add_column("Simulated Value", justify="right")
        table.add_column("Change (Delta)", justify="right")
        
        def format_delta(val):
            if val > 0:
                return f"[green]+{val}[/green]"
            elif val < 0:
                return f"[red]{val}[/red]"
            return "[dim]0[/dim]"

        def format_delta_score(val):
            if val > 0:
                return f"[green]+{val} (Improvement)[/green]"
            elif val < 0:
                return f"[red]{val} (Degradation)[/red]"
            return "[dim]0 (No change)[/dim]"

        table.add_row(
            "Maintainability Score",
            f"{diff['maintainability_score']['baseline']}/100",
            f"{diff['maintainability_score']['simulated']}/100",
            format_delta_score(diff['maintainability_score']['delta'])
        )
        table.add_row(
            "Circular Dependency Cycles",
            str(diff['circular_dependencies']['baseline']),
            str(diff['circular_dependencies']['simulated']),
            format_delta(-diff['circular_dependencies']['delta']) # cycle reduction is positive
        )
        table.add_row(
            "Inter-service Coupling Edges",
            str(diff['coupling_edges']['baseline']),
            str(diff['coupling_edges']['simulated']),
            format_delta(-diff['coupling_edges']['delta']) # coupling reduction is positive
        )
        table.add_row(
            "Repository Nodes (Classes/Methods)",
            str(diff['nodes_count']['baseline']),
            str(diff['nodes_count']['simulated']),
            format_delta(diff['nodes_count']['delta'])
        )
        table.add_row(
            "Active Dependency Edges",
            str(diff['edges_count']['baseline']),
            str(diff['edges_count']['simulated']),
            format_delta(diff['edges_count']['delta'])
        )
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Simulation Comparison Error:[/bold red] {e}")
    finally:
        db_manager.close_driver()


@simulate_app.command("timeline")
def simulate_timeline(
    path: Optional[str] = typer.Argument(None, help="Path to the directory to simulate. Defaults to the current directory."),
    commits: int = typer.Option(30, "--commits", "-n", help="Number of commits to analyze"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Specific context to use"),
):
    """
    Analyze architectural evolution timeline: tracks repository growth trends and identifies top Technical Debt Hotspots (churn vs complexity).
    """
    load_cgc_credentials(context)
    repo_path = get_repo_path(path)
    
    services = _initialize_services(context)
    db_manager = services[0]

    try:
        console.print(f"[bold cyan]Analyzing Git repository at: {repo_path}[/bold cyan]\n")
        
        # 1. Technical Debt Hotspots
        hotspots = EvolutionTimeline.analyze_hotspots(db_manager, repo_path, num_commits=commits)
        if hotspots:
            hs_table = Table(title="Top Technical Debt Hotspots (Churn x Complexity)", show_header=True, header_style="bold red")
            hs_table.add_column("File Path", style="cyan")
            hs_table.add_column("Git Churn (Edits)", justify="right")
            hs_table.add_column("Code Complexity", justify="right")
            hs_table.add_column("Hotspot Score (0-100)", justify="right", style="bold yellow")
            
            for hs in hotspots[:10]: # Top 10
                hs_table.add_row(
                    hs["relative_path"],
                    str(hs["churn"]),
                    str(hs["complexity"]),
                    str(hs["hotspot_score"])
                )
            console.print(hs_table)
        else:
            console.print("[yellow]No git churn data or code complexity data available to calculate hotspots.[/yellow]")
            
        # 2. Growth Timeline
        growth = EvolutionTimeline.get_growth_trend(repo_path, num_commits=min(15, commits))
        if growth:
            growth_table = Table(title="\nArchitectural Evolution Timeline", show_header=True, header_style="bold green")
            growth_table.add_column("Commit", style="dim")
            growth_table.add_column("Date", style="cyan")
            growth_table.add_column("Author", max_width=15)
            growth_table.add_column("Summary", max_width=30)
            growth_table.add_column("Files Changed", justify="right")
            growth_table.add_column("Insertions (+)", justify="right", style="green")
            growth_table.add_column("Deletions (-)", justify="right", style="red")
            
            for c in growth:
                growth_table.add_row(
                    c["hash"],
                    c["date"],
                    c["author"],
                    c["subject"],
                    str(c["files_changed"]),
                    f"+{c['insertions']}",
                    f"-{c['deletions']}"
                )
            console.print(growth_table)
        else:
            console.print("[yellow]No recent commits found in git log.[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]Evolution Analysis Error:[/bold red] {e}")
    finally:
        db_manager.close_driver()
