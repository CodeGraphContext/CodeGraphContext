from InquirerPy import prompt
from rich.console import Console
import subprocess
import platform
import os
from pathlib import Path
import time
import json
import sys
import shutil
import yaml 
from codegraphcontext.core.database import DatabaseManager

console = Console()

# Constants for Docker Neo4j setup
DEFAULT_NEO4J_URI = "neo4j://localhost:7687"
DEFAULT_NEO4J_USERNAME = "neo4j"
DEFAULT_NEO4J_BOLT_PORT = 7687
DEFAULT_NEO4J_HTTP_PORT = 7474

def _generate_mcp_json(creds):
    """Generates and prints the MCP JSON configuration."""
    cgc_path = shutil.which("cgc") or sys.executable

    if "python" in Path(cgc_path).name:
        # fallback to running as module if no cgc binary is found
        command = cgc_path
        args = ["-m", "cgc", "mcp", "start"]
    else:
        command = cgc_path
        args = ["mcp","start"]

    mcp_config = {
        "mcpServers": {
            "CodeGraphContext": {
                "command": command,
                "args": args,
                "env": {
                    "NEO4J_URI": creds.get("uri", ""),
                    "NEO4J_USERNAME": creds.get("username", "neo4j"),
                    "NEO4J_PASSWORD": creds.get("password", "")
                },
                "tools": {
                    "alwaysAllow": [
                        "add_code_to_graph", "add_package_to_graph",
                        "check_job_status", "list_jobs", "find_code",
                        "analyze_code_relationships", "watch_directory",
                        "find_dead_code", "execute_cypher_query",
                        "calculate_cyclomatic_complexity", "find_most_complex_functions",
                        "list_indexed_repositories", "delete_repository", "list_watched_paths", 
                        "unwatch_directory", "visualize_graph_query"
                    ],
                    "disabled": False
                },
                "disabled": False,
                "alwaysAllow": []
            }
        }
    }

    console.print("\n[bold green]Configuration successful![/bold green]")
    console.print("Copy the following JSON and add it to your MCP server configuration file:")
    console.print(json.dumps(mcp_config, indent=2))

    # Also save to a file for convenience
    mcp_file = Path.cwd() / "mcp.json"
    with open(mcp_file, "w") as f:
        json.dump(mcp_config, f, indent=2)
    console.print(f"\n[cyan]For your convenience, the configuration has also been saved to: {mcp_file}[/cyan]")

    # Also save to a .env file for convenience
    env_file = Path.home() / ".codegraphcontext" / ".env"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    with open(env_file, "w") as f:
        f.write(f"NEO4J_URI={creds.get('uri', '')}\n")
        f.write(f"NEO4J_USERNAME={creds.get('username', 'neo4j')}\n")
        f.write(f"NEO4J_PASSWORD={creds.get('password', '')}\n")

    console.print(f"[cyan]Neo4j credentials also saved to: {env_file}[/cyan]")
    _configure_ide(mcp_config)


def find_jetbrains_mcp_config():
    bases = [
        Path.home() / ".config" / "JetBrains",
        Path.home() / "Library/Application Support/JetBrains",
        Path.home() / "AppData/Roaming/JetBrains"
    ]
    configs = []
    for base in bases:
        if base.exists():
            for folder in base.iterdir():  # each IDE/version
                options = folder / "options"
                mcp_file = options / "mcpServer.xml"
                if mcp_file.exists():
                    configs.append(mcp_file)
                    print(mcp_file)
                    return configs


def convert_mcp_json_to_yaml():
    json_path = Path.cwd() / "mcp.json"
    yaml_path = Path.cwd() / "devfile.yaml"
    if json_path.exists():
        with open(json_path, "r") as json_file:
            mcp_config = json.load(json_file)
        with open(yaml_path, "w") as yaml_file:
            yaml.dump(mcp_config, yaml_file, default_flow_style=False)
        console.print(f"[green]Generated devfile.yaml for Amazon Q Developer at {yaml_path}[/green]")

def _configure_ide(mcp_config):
    """Asks user for their IDE and configures it automatically."""
    questions = [
        {
            "type": "confirm",
            "message": "Automatically configure your IDE/CLI (VS Code, Cursor, Windsurf, Claude, Gemini, Cline, RooCode, ChatGPT Codex, Amazon Q Developer, Aider, Kiro)?",
            "name": "configure_ide",
            "default": True,
        }
    ]
    result = prompt(questions)
    if not result or not result.get("configure_ide"):
        console.print("\n[cyan]Skipping automatic IDE configuration. You can add the MCP server manually.[/cyan]")
        return

    ide_questions = [
        {
            "type": "list",
            "message": "Choose your IDE/CLI to configure:",
            "choices": ["VS Code", "Cursor", "Windsurf", "Claude code", "Gemini CLI", "ChatGPT Codex", "Cline", "RooCode", "Amazon Q Developer", "JetBrainsAI", "Aider", "Kiro", "None of the above"],
            "name": "ide_choice",
        }
    ]
    ide_result = prompt(ide_questions)
    ide_choice = ide_result.get("ide_choice")

    if not ide_choice or ide_choice == "None of the above":
        console.print("\n[cyan]You can add the MCP server manually to your IDE/CLI.[/cyan]")
        return


    if ide_choice in ["VS Code", "Cursor/CLI", "Claude code", "Gemini CLI", "ChatGPT Codex", "Cline", "Windsurf", "RooCode", "Amazon Q Developer , JetBrainsAI", "Aider", "Kiro"]:
        console.print(f"\n[bold cyan]Configuring for {ide_choice}...[/bold cyan]")

        if ide_choice == "Amazon Q Developer":
            convert_mcp_json_to_yaml()
            return  
        
        config_paths = {
            "VS Code": [
                Path.home() / ".config" / "Code" / "User" / "settings.json",
                Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",
                Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json"
            ],
            "Cursor/CLI": [
                Path.home() / ".cursor" / "settings.json",
                Path.home() / ".config" / "cursor" / "settings.json",
                Path.home() / "Library" / "Application Support" / "cursor" / "settings.json",
                Path.home() / "AppData" / "Roaming" / "cursor" / "settings.json",
                Path.home() / ".config" / "Cursor" / "User" / "settings.json",
            ],
            "Windsurf": [
                Path.home() / ".windsurf" / "settings.json",
                Path.home() / ".config" / "windsurf" / "settings.json",
                Path.home() / "Library" / "Application Support" / "windsurf" / "settings.json",
                Path.home() / "AppData" / "Roaming" / "windsurf" / "settings.json",
                Path.home() / ".config" / "Windsurf" / "User" / "settings.json",
            ],
            "Claude code": [
                Path.home() / ".claude.json"
            ],
            "Gemini CLI": [
                Path.home() / ".gemini" / "settings.json"
            ],
            "ChatGPT Codex": [
                Path.home() / ".openai" / "mcp_settings.json",
                Path.home() / ".config" / "openai" / "settings.json",
                Path.home() / "AppData" / "Roaming" / "OpenAI" / "settings.json"
            ],
            "Cline": [
                Path.home() / ".config" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                Path.home() / ".config" / "Code - OSS" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
            ],

            "JetBrainsAI": find_jetbrains_mcp_config(), #only for jetbrains ide

            "RooCode": [
                Path.home() / ".config" / "Code" / "User" / "settings.json",   # Linux 
                Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",  # Windows
                Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json"  # macOS
            ],
            "Aider": [
                Path.home() / ".aider" / "settings.json",
                Path.home() / ".config" / "aider" / "settings.json",
                Path.home() / "Library" / "Application Support" / "aider" / "settings.json",
                Path.home() / "AppData" / "Roaming" / "aider" / "settings.json",
                Path.home() / ".config" / "Aider" / "User" / "settings.json",
            ],
            "Kiro": [
                Path.home() / ".kiro" / "settings" / "mcp.json",                                   # macOS / Linux / Windows (user-level global)
                Path.home() / ".config" / "kiro" / "settings" / "mcp.json",                         # Linux (XDG config)
                Path.home() / "AppData" / "Roaming" / "Kiro" / "settings" / "mcp.json",             # Windows
            ]
        }

        target_path = None
        paths_to_check = config_paths.get(ide_choice, [])
        for path in paths_to_check:
            if path.exists():
                target_path = path
                break
        
        if not target_path:
            # If file doesn't exist, check if parent directory exists
            for path in paths_to_check:
                if path.parent.exists():
                    target_path = path
                    break
        
        if not target_path:
            console.print(f"[yellow]Could not automatically find or create the configuration directory for {ide_choice}.[/yellow]")
            console.print("Please add the MCP configuration manually from the `mcp.json` file generated above.")
            return

        console.print(f"Using configuration file at: {target_path}")
        
        try:
            with open(target_path, "r") as f:
                try:
                    settings = json.load(f)
                except json.JSONDecodeError:
                    settings = {}
        except FileNotFoundError:
            settings = {}

        if not isinstance(settings, dict):
            console.print(f"[red]Error: Configuration file at {target_path} is not a valid JSON object.[/red]")
            return

        if "mcpServers" not in settings:
            settings["mcpServers"] = {}
        
        settings["mcpServers"].update(mcp_config["mcpServers"])

        try:
            with open(target_path, "w") as f:
                json.dump(settings, f, indent=2)
            console.print(f"[green]Successfully updated {ide_choice} configuration.[/green]")
        except Exception as e:
            console.print(f"[red]Failed to write to configuration file: {e}[/red]")




def get_project_root() -> Path:
    """Always return the directory where the user runs `cgc` (CWD)."""
    return Path.cwd()

def run_command(command, console, shell=False, check=True, input_text=None):
    """
    Runs a command, captures its output, and handles execution.
    Returns the completed process object on success, None on failure.
    """
    cmd_str = command if isinstance(command, str) else ' '.join(command)
    console.print(f"[cyan]$ {cmd_str}[/cyan]")
    try:
        process = subprocess.run(
            command,
            shell=shell,
            check=check,
            capture_output=True,  # Always capture to control what gets displayed
            text=True,
            timeout=300,
            input=input_text
        )
        return process
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error executing command:[/bold red] {cmd_str}")
        if e.stdout:
            console.print(f"[red]STDOUT: {e.stdout}[/red]")
        if e.stderr:
            console.print(f"[red]STDERR: {e.stderr}[/red]")
        return None
    except subprocess.TimeoutExpired:
        console.print(f"[bold red]Command timed out:[/bold red] {cmd_str}")
        return None

def run_neo4j_setup_wizard():
    """Guides the user through setting up Neo4j database for CodeGraphContext."""
    console.print("[bold cyan]Welcome to the Neo4j Setup Wizard![/bold cyan]")
    
    questions = [
        {
            "type": "list",
            "message": "Where do you want to setup your Neo4j database?",
            "choices": [
                "Local (Recommended: I'll help you run it on this machine)",
                "Hosted (Connect to a remote database like AuraDB)",
                "I already have an existing neo4j instance running.",
            ],
            "name": "db_location",
        }
    ]
    result = prompt(questions)
    db_location = result.get("db_location")

    if db_location and "Hosted" in db_location:
        setup_hosted_db()
    elif db_location and "Local" in db_location:
        setup_local_db()
    elif db_location:
        setup_existing_db()


def configure_mcp_client():
    """
    Configure MCP client (IDE/CLI) integration.
    This function sets up the MCP server configuration for the user's IDE.
    Includes all current configuration values in the env section.
    """
    console.print("[bold cyan]MCP Client Configuration[/bold cyan]\n")
    console.print("This will configure CodeGraphContext integration with your IDE or CLI tool.")
    console.print("CodeGraphContext works with FalkorDB by default (no database setup needed).\n")
    
    # Load current configuration (includes project-local .env if present)
    try:
        from codegraphcontext.cli.config_manager import load_config
        config = load_config()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load configuration: {e}[/yellow]")
        config = {}
    
    # Build env section with all configuration values
    env_vars = {}
    
    # Add database credentials if they exist
    env_file = Path.home() / ".codegraphcontext" / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        if key in ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]:
                            env_vars[key] = value.strip()
        except Exception:
            pass
    
    # Add all configuration values, converting relative paths to absolute
    for key, value in config.items():
        # Skip database credentials (already added above)
        if key in ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]:
            continue
        
        # Convert relative paths to absolute for path-related configs
        if "PATH" in key and value:
            path_obj = Path(value)
            if not path_obj.is_absolute():
                value = str(path_obj.resolve())
        
        env_vars[key] = value
    
    # Generate MCP configuration
    cgc_path = shutil.which("cgc") or sys.executable

    if "python" in Path(cgc_path).name:
        # fallback to running as module if no cgc binary is found
        command = cgc_path
        args = ["-m", "cgc", "mcp", "start"]
    else:
        command = cgc_path
        args = ["mcp", "start"]

    # Create MCP config with complete env section
    mcp_config = {
        "mcpServers": {
            "CodeGraphContext": {
                "command": command,
                "args": args,
                "env": env_vars,
                "tools": {
                    "alwaysAllow": [
                        "add_code_to_graph", "add_package_to_graph",
                        "check_job_status", "list_jobs", "find_code",
                        "analyze_code_relationships", "watch_directory",
                        "find_dead_code", "execute_cypher_query",
                        "calculate_cyclomatic_complexity", "find_most_complex_functions",
                        "list_indexed_repositories", "delete_repository", "list_watched_paths", 
                        "unwatch_directory", "visualize_graph_query"
                    ],
                    "disabled": False
                },
                "disabled": False,
                "alwaysAllow": []
            }
        }
    }

    console.print("\n[bold green]Configuration generated![/bold green]")
    console.print("Copy the following JSON and add it to your MCP server configuration file:")
    console.print(json.dumps(mcp_config, indent=2))

    # Save to file for convenience
    mcp_file = Path.cwd() / "mcp.json"
    with open(mcp_file, "w") as f:
        json.dump(mcp_config, f, indent=2)
    console.print(f"\n[cyan]Configuration saved to: {mcp_file}[/cyan]")
    
    # Configure IDE automatically
    _configure_ide(mcp_config)
    
    console.print("\n[bold green]✅ MCP Client configuration complete![/bold green]")
    console.print("[cyan]You can now run 'cgc mcp start' to launch the server.[/cyan]")
    console.print("[yellow]💡 Tip: To update MCP config after changing settings, re-run 'cgc mcp setup'[/yellow]\n")


def find_latest_neo4j_creds_file():
    """Finds the latest Neo4j credentials file in the Downloads folder."""
    downloads_path = Path.home() / "Downloads"
    if not downloads_path.exists():
        return None
    
    cred_files = list(downloads_path.glob("Neo4j*.txt"))
    if not cred_files:
        return None
        
    latest_file = max(cred_files, key=lambda f: f.stat().st_mtime)
    return latest_file


def setup_existing_db():
    """Guides user to configure an existing Neo4j instance."""
    console.print("\nTo connect to an existing Neo4j database, you'll need your connection credentials.")
    console.print("If you don't have credentials for the database, you can create a new one using 'Local' installation in the previous menu.")
    
    questions = [

        {
            "type": "list",
            "message": "How would you like to add your Neo4j credentials?",
            "choices": ["Add credentials from file", "Add credentials manually"],
            "name": "cred_method",
        }
    ]
    result = prompt(questions)
    cred_method = result.get("cred_method")

    creds = {}
    if cred_method and "file" in cred_method:
        latest_file = find_latest_neo4j_creds_file()
        file_to_parse = None
        if latest_file:
            confirm_questions = [
                {
                    "type": "confirm",
                    "message": f"Found a credentials file: {latest_file}. Use this file?",
                    "name": "use_latest",
                    "default": True,
                }
            ]
            if prompt(confirm_questions).get("use_latest"):
                file_to_parse = latest_file

        if not file_to_parse:
            path_questions = [
                {"type": "input", "message": "Please enter the path to your credentials file:", "name": "cred_file_path"}
            ]
            file_path_str = prompt(path_questions).get("cred_file_path", "")
            path = Path(file_path_str.strip())
            if path.exists() and path.is_file():
                file_to_parse = path
            else:
                console.print("[red]❌ The specified file path does not exist or is not a file.[/red]")
                return

        if file_to_parse:
            try:
                with open(file_to_parse, "r") as f:
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            if key == "NEO4J_URI":
                                creds["uri"] = value
                            elif key == "NEO4J_USERNAME":
                                creds["username"] = value
                            elif key == "NEO4J_PASSWORD":
                                creds["password"] = value
            except Exception as e:
                console.print(f"[red]❌ Failed to parse credentials file: {e}[/red]")
                return

    elif cred_method: # Manual entry
        console.print("Please enter your Neo4j connection details.")
        
        # Loop until valid credentials are provided
        while True:
            questions = [
                {"type": "input", "message": "URI (e.g., 'neo4j://localhost:7687'):", "name": "uri", "default": "neo4j://localhost:7687"},
                {"type": "input", "message": "Username:", "name": "username", "default": "neo4j"},
                {"type": "password", "message": "Password:", "name": "password"},
            ]
            
            manual_creds = prompt(questions)
            if not manual_creds: 
                return # User cancelled
            
            # Validate the user input
            console.print("\n[cyan]🔍 Validating configuration...[/cyan]")
            is_valid, validation_error = DatabaseManager.validate_config(
                manual_creds.get("uri", ""),
                manual_creds.get("username", ""),
                manual_creds.get("password", "")
            )
            
            if not is_valid:
                console.print(validation_error)
                console.print("\n[red]❌ Invalid configuration. Please try again.[/red]\n")
                continue  # Ask for input again
            
            console.print("[green]✅ Configuration format is valid[/green]")
            
            # Test the connection
            console.print("\n[cyan]🔗 Testing connection...[/cyan]")
            is_connected, error_msg = DatabaseManager.test_connection(
                manual_creds.get("uri", ""),
                manual_creds.get("username", ""),
                manual_creds.get("password", "")
            )
            
            if not is_connected:
                console.print(error_msg)
                retry = prompt([{"type": "confirm", "message": "Connection failed. Try again with different credentials?", "name": "retry", "default": True}])
                if not retry.get("retry"):
                    return
                continue  # Ask for input again
            
            console.print("[green]✅ Connection successful![/green]")
            creds = manual_creds
            break  # Exit loop with valid credentials


    if creds.get("uri") and creds.get("password"):
        _generate_mcp_json(creds)
    else:
        console.print("[red]❌ Incomplete credentials. Please try again.[/red]")


def setup_hosted_db():
    """Guides user to configure a remote Neo4j instance."""
    console.print("\nTo connect to a hosted Neo4j database, you'll need your connection credentials.")
    console.print("[yellow]Warning: You are configuring to connect to a remote/hosted Neo4j database. Ensure your credentials are secure.[/yellow]")
    console.print("If you don't have a hosted database, you can create a free one at [bold blue]https://neo4j.com/product/auradb/[/bold blue] (click 'Start free').")
    
    questions = [

        {
            "type": "list",
            "message": "How would you like to add your Neo4j credentials?",
            "choices": ["Add credentials from file", "Add credentials manually"],
            "name": "cred_method",
        }
    ]
    result = prompt(questions)
    cred_method = result.get("cred_method")

    creds = {}
    if cred_method and "file" in cred_method:
        latest_file = find_latest_neo4j_creds_file()
        file_to_parse = None
        if latest_file:
            confirm_questions = [
                {
                    "type": "confirm",
                    "message": f"Found a credentials file: {latest_file}. Use this file?",
                    "name": "use_latest",
                    "default": True,
                }
            ]
            if prompt(confirm_questions).get("use_latest"):
                file_to_parse = latest_file

        if not file_to_parse:
            path_questions = [
                {"type": "input", "message": "Please enter the path to your credentials file:", "name": "cred_file_path"}
            ]
            file_path_str = prompt(path_questions).get("cred_file_path", "")
            path = Path(file_path_str.strip())
            if path.exists() and path.is_file():
                file_to_parse = path
            else:
                console.print("[red]❌ The specified file path does not exist or is not a file.[/red]")
                return

        if file_to_parse:
            try:
                with open(file_to_parse, "r") as f:
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            if key == "NEO4J_URI":
                                creds["uri"] = value
                            elif key == "NEO4J_USERNAME":
                                creds["username"] = value
                            elif key == "NEO4J_PASSWORD":
                                creds["password"] = value
            except Exception as e:
                console.print(f"[red]❌ Failed to parse credentials file: {e}[/red]")
                return

    elif cred_method: # Manual entry
        console.print("Please enter your remote Neo4j connection details.")
        
        # Loop until valid credentials are provided
        while True:
            questions = [
                {"type": "input", "message": "URI (e.g., neo4j+s://xxxx.databases.neo4j.io):", "name": "uri"},
                {"type": "input", "message": "Username:", "name": "username", "default": "neo4j"},
                {"type": "password", "message": "Password:", "name": "password"},
            ]
            
            manual_creds = prompt(questions)
            if not manual_creds:
                return # User cancelled
            
            # Validate the user input
            console.print("\n[cyan]🔍 Validating configuration...[/cyan]")
            is_valid, validation_error = DatabaseManager.validate_config(
                manual_creds.get("uri", ""),
                manual_creds.get("username", ""),
                manual_creds.get("password", "")
            )
            
            if not is_valid:
                console.print(validation_error)
                console.print("\n[red]❌ Invalid configuration. Please try again.[/red]\n")
                continue  # Ask for input again
            
            console.print("[green]✅ Configuration format is valid[/green]")
            
            # Test the connection
            console.print("\n[cyan]🔗 Testing connection...[/cyan]")
            is_connected, error_msg = DatabaseManager.test_connection(
                manual_creds.get("uri", ""),
                manual_creds.get("username", ""),
                manual_creds.get("password", "")
            )
            
            if not is_connected:
                console.print(error_msg)
                retry = prompt([{"type": "confirm", "message": "Connection failed. Try again with different credentials?", "name": "retry", "default": True}])
                if not retry.get("retry"):
                    return
                continue  # Ask for input again
            
            console.print("[green]✅ Connection successful![/green]")
            creds = manual_creds
            break  


    if creds.get("uri") and creds.get("password"):
        _generate_mcp_json(creds)
    else:
        console.print("[red]❌ Incomplete credentials. Please try again.[/red]")

def setup_local_db():
    """Guides user to set up a local Neo4j instance."""
    questions = [
        {
            "type": "list",
            "message": "How would you like to run Neo4j locally?",
            "choices": ["Docker (Easiest)", "Local Binary (Advanced)"],
            "name": "local_method",
        }
    ]
    result = prompt(questions)
    local_method = result.get("local_method")

    if local_method and "Docker" in local_method:
        setup_docker()
    elif local_method:
        if platform.system() == "Darwin":
            # lazy import to avoid circular import
            from .setup_macos import setup_macos_binary
            setup_macos_binary(console, prompt, run_command, _generate_mcp_json)
        else:
            setup_local_binary()

def setup_docker():
    """Creates Docker files and runs docker-compose for Neo4j."""
    console.print("\n[bold cyan]Setting up Neo4j with Docker...[/bold cyan]")

    # Prompt for password first
    console.print("Please set a secure password for your Neo4j database:")
    password_questions = [
        {"type": "password", "message": "Enter Neo4j password:", "name": "password"},
        {"type": "password", "message": "Confirm password:", "name": "password_confirm"},
    ]
    
    while True:
        passwords = prompt(password_questions)
        if not passwords:
            return  # User cancelled
        
        password = passwords.get("password", "")
        if password and password == passwords.get("password_confirm"):
            break
        console.print("[red]Passwords do not match or are empty. Please try again.[/red]")

    # Create data directories
    neo4j_dir = Path.cwd() / "neo4j_data"
    for subdir in ["data", "logs", "conf", "plugins"]:
        (neo4j_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Fixed docker-compose.yml content
    docker_compose_content = f"""
services:
  neo4j:
    image: neo4j:5.21
    container_name: neo4j-cgc
    restart: unless-stopped
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/{password}
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
"""

    # Write docker-compose.yml
    compose_file = Path.cwd() / "docker-compose.yml"
    with open(compose_file, "w") as f:
        f.write(docker_compose_content)

    console.print("[green]✅ docker-compose.yml created with secure password.[/green]")

    # Validate configuration format before attempting Docker operations
    console.print("\n[cyan]🔍 Validating configuration...[/cyan]")
    is_valid, validation_error = DatabaseManager.validate_config(
        DEFAULT_NEO4J_URI, 
        DEFAULT_NEO4J_USERNAME, 
        password
    )

    if not is_valid:
        console.print(validation_error)
        console.print("\n[red]❌ Configuration validation failed. Please fix the issues and try again.[/red]")
        return

    console.print("[green]✅ Configuration format is valid[/green]")

    # Check if Docker is running
    docker_check = run_command(["docker", "--version"], console, check=False)
    if not docker_check:
        console.print("[red]❌ Docker is not installed or not running. Please install Docker first.[/red]")
        return

    # Check if docker-compose is available
    compose_check = run_command(["docker", "compose", "version"], console, check=False)
    if not compose_check:
        console.print("[red]❌ Docker Compose is not available. Please install Docker Compose.[/red]")
        return

    confirm_q = [{"type": "confirm", "message": "Ready to launch Neo4j in Docker?", "name": "proceed", "default": True}]
    if not prompt(confirm_q).get("proceed"):
        return

    try:
        # Pull the image first
        console.print("[cyan]Pulling Neo4j Docker image...[/cyan]")
        pull_process = run_command(["docker", "pull", "neo4j:5.21"], console, check=True)
        if not pull_process:
            console.print("[yellow]⚠️ Could not pull image, but continuing anyway...[/yellow]")

        # Start containers
        console.print("[cyan]Starting Neo4j container...[/cyan]")
        docker_process = run_command(["docker", "compose", "up", "-d"], console, check=True)
        
        if docker_process:
            console.print("[bold green]🚀 Neo4j Docker container started successfully![/bold green]")
            
            # Wait for Neo4j to be ready
            console.print("[cyan]Waiting for Neo4j to be ready (this may take 30-60 seconds)...[/cyan]")
            
            # Try to connect for up to 2 minutes
            max_attempts = 24  # 24 * 5 seconds = 2 minutes
            for attempt in range(max_attempts):
                time.sleep(5)
                
                # Check if container is still running
                status_check = run_command(["docker", "compose", "ps", "-q", "neo4j"], console, check=False)
                if not status_check or not status_check.stdout.strip():
                    console.print("[red]❌ Neo4j container stopped unexpectedly. Check logs with: docker compose logs neo4j[/red]")
                    return
                
                # updated test_connection method
                console.print(f"[yellow]Testing connection... (attempt {attempt + 1}/{max_attempts})[/yellow]")
                is_connected, error_msg = DatabaseManager.test_connection(DEFAULT_NEO4J_URI, DEFAULT_NEO4J_USERNAME, password)
                
                if is_connected:
                    console.print("[bold green]✅ Neo4j is ready and accepting connections![/bold green]")
                    connection_successful = True
                    break
                
                else:
                    # Only show detailed error on last attempt
                    if attempt == max_attempts - 1:
                        console.print("\n[red]❌ Neo4j did not become ready within 2 minutes.[/red]")
                        console.print(error_msg)
                        console.print("\n[cyan]Troubleshooting:[/cyan]")
                        console.print("  • Check logs: docker compose logs neo4j")
                        console.print("  • Verify container is running: docker ps")
                        console.print("  • Try restarting: docker compose restart")
                        return
            
            if not connection_successful:
                return

            # Generate MCP configuration
            creds = {
                "uri": DEFAULT_NEO4J_URI,
                "username": DEFAULT_NEO4J_USERNAME,
                "password": password
            }

            _generate_mcp_json(creds)
            
            console.print("\n[bold green]🎉 Setup complete![/bold green]")
            console.print("Neo4j is running at:")
            console.print("  • Web interface: http://localhost:7474")
            console.print("  • Bolt connection: neo4j://localhost:7687")
            console.print("\n[cyan]Useful commands:[/cyan]")
            console.print("  • Stop: docker compose down")
            console.print("  • Restart: docker compose restart")
            console.print("  • View logs: docker compose logs neo4j")
            
    except Exception as e:
        console.print(f"[bold red]❌ Failed to start Neo4j Docker container:[/bold red] {e}")
        console.print("[cyan]Try checking the logs with: docker compose logs neo4j[/cyan]")

def setup_local_binary():
    """Automates the installation and configuration of Neo4j on Ubuntu/Debian."""
    os_name = platform.system()
    console.print(f"Detected Operating System: [bold yellow]{os_name}[/bold yellow]")

    if os_name != "Linux" or not os.path.exists("/etc/debian_version"):
        console.print("[yellow]Automated installer is designed for Debian-based systems (like Ubuntu).[/yellow]")
        console.print(f"For other systems, please follow the manual installation guide: [bold blue]https://neo4j.com/docs/operations-manual/current/installation/[/bold blue]")
        return

    console.print("[bold]Starting automated Neo4j installation for Ubuntu/Debian.[/bold]")
    console.print("[yellow]This will run several commands with 'sudo'. You will be prompted for your password.[/yellow]")
    confirm_q = [{"type": "confirm", "message": "Do you want to proceed?", "name": "proceed", "default": True}]
    if not prompt(confirm_q).get("proceed"):
        return

    # Install latest Neo4j version instead of pinning to a specific version
    # This prevents version conflicts and ensures users get the latest stable release
    install_commands = [
        ("Creating keyring directory", ["sudo", "mkdir", "-p", "/etc/apt/keyrings"]),
        ("Adding Neo4j GPG key", "wget -qO- https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor --yes -o /etc/apt/keyrings/neotechnology.gpg", True),
        ("Adding Neo4j repository", "echo 'deb [signed-by=/etc/apt/keyrings/neotechnology.gpg] https://debian.neo4j.com stable 5' | sudo tee /etc/apt/sources.list.d/neo4j.list > /dev/null", True),
        ("Updating apt sources", ["sudo", "apt-get", "-qq", "update"]),
        ("Installing latest Neo4j and Cypher Shell", ["sudo", "apt-get", "install", "-qq", "-y", "neo4j", "cypher-shell"])
    ]

    for desc, cmd, use_shell in [(c[0], c[1], c[2] if len(c) > 2 else False) for c in install_commands]:
        console.print(f"\n[bold]Step: {desc}...[/bold]")
        if not run_command(cmd, console, shell=use_shell):
            console.print(f"[bold red]Failed on step: {desc}. Aborting installation.[/bold red]")
            return
            
    console.print("\n[bold green]Neo4j installed successfully![/bold green]")
    
    console.print("\n[bold]Please set the initial password for the 'neo4j' user.""")
    
    new_password = ""
    while True:
        questions = [
            {"type": "password", "message": "Enter a new password for Neo4j:", "name": "password"},
            {"type": "password", "message": "Confirm the new password:", "name": "password_confirm"},
        ]
        passwords = prompt(questions)
        if not passwords: return # User cancelled
        new_password = passwords.get("password")
        if new_password and new_password == passwords.get("password_confirm"):
            break
        console.print("[red]Passwords do not match or are empty. Please try again.[/red]")

    console.print("\n[bold]Stopping Neo4j to set the password...""")
    if not run_command(["sudo", "systemctl", "stop", "neo4j"], console):
        console.print("[bold red]Could not stop Neo4j service. Aborting.[/bold red]")
        return
        
    console.print("\n[bold]Setting initial password using neo4j-admin...""")
    pw_command = ["sudo", "-u", "neo4j", "neo4j-admin", "dbms", "set-initial-password", new_password]
    if not run_command(pw_command, console, check=True):
        console.print("[bold red]Failed to set the initial password. Please check the logs.[/bold red]")
        run_command(["sudo", "systemctl", "start", "neo4j"], console)
        return
    
    console.print("\n[bold]Starting Neo4j service...""")
    if not run_command(["sudo", "systemctl", "start", "neo4j"], console):
        console.print("[bold red]Failed to start Neo4j service after setting password.[/bold red]")
        return

    console.print("\n[bold]Enabling Neo4j service to start on boot...""")
    if not run_command(["sudo", "systemctl", "enable", "neo4j"], console):
        console.print("[bold yellow]Could not enable Neo4j service. You may need to start it manually after reboot.[/bold yellow]")

    console.print("[bold green]Password set and service started.[/bold green]")
    
    console.print("\n[yellow]Waiting 10 seconds for the database to become available...""")
    time.sleep(10)

    creds = {
        "uri": "neo4j://localhost:7687",
        "username": "neo4j",
        "password": new_password
    }
    _generate_mcp_json(creds)
    console.print("\n[bold green]All done! Your local Neo4j instance is ready to use.[/bold green]")
