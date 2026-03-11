# src/codegraphcontext/cli/setup_macos.py
import platform
import time
from pathlib import Path

def _has_brew(run_command, console) -> bool:
    return run_command(["which", "brew"], console, check=False) is not None

def _brew_install_neo4j(run_command, console) -> str:
    if run_command(["brew", "install", "neo4j@5"], console, check=False):
        return "neo4j@5"
    if run_command(["brew", "install", "neo4j"], console, check=False):
        return "neo4j"
    return ""

def _brew_start(service: str, run_command, console) -> bool:
    return run_command(["brew", "services", "start", service], console, check=False) is not None

def _set_initial_password(new_pw: str, run_command, console) -> bool:
    cmd = [
        "cypher-shell",
        "-u", "neo4j",
        "-p", "neo4j",
        f"ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO '{new_pw}'",
    ]
    return run_command(cmd, console, check=False) is not None

def setup_macos_binary(console, prompt, run_command, _save_neo4j_credentials):
    """Automates Neo4j install & config on macOS via Homebrew."""
    os_name = platform.system()
    console.print(f"Detected Operating System: [bold yellow]{os_name}[/bold yellow]")

    if os_name != "Darwin":
        console.print("[yellow]This installer is for macOS only.[/yellow]")
        return

    console.print("[bold]Starting automated Neo4j installation for macOS.[/bold]")

    if not prompt([{
        "type": "confirm",
        "message": "Proceed with Homebrew-based install of Neo4j?",
        "name": "proceed",
        "default": True
    }]).get("proceed"):
        return

    console.print("\n[bold]Step: Checking for Homebrew...[/bold]")
    if not _has_brew(run_command, console):
        console.print(
            "[bold red]Homebrew not found.[/bold red] "
            "Install from [bold blue]https://brew.sh[/bold blue] and re-run this setup."
        )
        return

    console.print("\n[bold]Step: Installing Neo4j via Homebrew...[/bold]")
    service = _brew_install_neo4j(run_command, console)
    if not service:
        console.print("[bold red]Failed to install Neo4j via Homebrew.[/bold red]")
        return

    console.print(f"\n[bold]Step: Starting Neo4j service ({service})...[/bold]")
    if not _brew_start(service, run_command, console):
        console.print("[bold red]Failed to start Neo4j with brew services.[/bold red]")
        return

    while True:
        answers = prompt([
            {"type": "password", "message": "Enter a new password for Neo4j:", "name": "pw"},
            {"type": "password", "message": "Confirm the new password:", "name": "pw2"},
        ]) or {}
        if not answers:
            return
        pw, pw2 = answers.get("pw"), answers.get("pw2")
        if pw and pw == pw2:
            new_password = pw
            break
        console.print("[red]Passwords do not match or are empty. Please try again.[/red]")

    console.print("\n[yellow]Waiting 10 seconds for Neo4j to finish starting...[/yellow]")
    time.sleep(10)

    console.print("\n[bold]Step: Setting initial password with cypher-shell...[/bold]")
    if not _set_initial_password(new_password, run_command, console):
        console.print(
            "[bold red]Failed to set the initial password.[/bold red]\n"
            "Try manually:\n"
            "  cypher-shell -u neo4j -p neo4j \"ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO '<your_pw>'\""
        )
        return

    creds = {"uri": "neo4j://localhost:7687", "username": "neo4j", "password": new_password}
    _save_neo4j_credentials(creds)

