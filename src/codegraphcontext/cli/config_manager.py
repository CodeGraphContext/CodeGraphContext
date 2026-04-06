"""
Configuration management for CodeGraphContext.
Handles reading, writing, and validating configuration settings.
Also manages the context system (config.yaml) alongside the existing .env file.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.table import Table
import os
import yaml

console = Console()

# Configuration file location
CONFIG_DIR = Path.home() / ".codegraphcontext"
CONFIG_FILE = CONFIG_DIR / ".env"

# Database credential keys (stored in same .env file but not managed as config)
DATABASE_CREDENTIAL_KEYS = {"NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"}

# Default configuration values
DEFAULT_CONFIG = {
    "DEFAULT_DATABASE": "falkordb",
    "FALKORDB_PATH": str(CONFIG_DIR / "global" / "db" / "falkordb"),
    "FALKORDB_SOCKET_PATH": str(CONFIG_DIR / "global" / "db" / "falkordb.sock"),
    "INDEX_VARIABLES": "true",
    "ALLOW_DB_DELETION": "false",
    "DEBUG_LOGS": "false",
    "DEBUG_LOG_PATH": str(Path.home() / "mcp_debug.log"),
    "ENABLE_APP_LOGS": "CRITICAL",
    "LIBRARY_LOG_LEVEL": "WARNING",
    "LOG_FILE_PATH": str(CONFIG_DIR / "logs" / "cgc.log"),
    "MAX_FILE_SIZE_MB": "10",
    "IGNORE_TEST_FILES": "false",
    "IGNORE_HIDDEN_FILES": "true",
    "ENABLE_AUTO_WATCH": "false",
    "COMPLEXITY_THRESHOLD": "10",
    "MAX_DEPTH": "unlimited",
    "PARALLEL_WORKERS": "4",
    "CACHE_ENABLED": "true",
    "IGNORE_DIRS": "node_modules,venv,.venv,env,.env,dist,build,target,out,.git,.idea,.vscode,__pycache__",
    "INDEX_SOURCE": "true",
    # SCIP indexer feature flag (default off — existing Tree-sitter behaviour unchanged)
    "SCIP_INDEXER": "false",
    "SCIP_LANGUAGES": "python,typescript,go,rust,java",
    "SKIP_EXTERNAL_RESOLUTION": "false",
}

# Configuration key descriptions
CONFIG_DESCRIPTIONS = {
    "DEFAULT_DATABASE": "Default database backend (neo4j|falkordb|kuzudb)",
    "FALKORDB_PATH": "Path to FalkorDB database file",
    "FALKORDB_SOCKET_PATH": "Path to FalkorDB Unix socket",
    "INDEX_VARIABLES": "Index variable nodes in the graph (lighter graph if false)",
    "ALLOW_DB_DELETION": "Allow full database deletion commands",
    "DEBUG_LOGS": "Enable debug logging (for development/troubleshooting)",
    "DEBUG_LOG_PATH": "Path to debug log file",
    "ENABLE_APP_LOGS": "Application log level (DEBUG|INFO|WARNING|ERROR|CRITICAL|DISABLED)",
    "LIBRARY_LOG_LEVEL": "Log level for third-party libraries (neo4j, asyncio, urllib3) (DEBUG|INFO|WARNING|ERROR|CRITICAL)",
    "LOG_FILE_PATH": "Path to application log file",
    "MAX_FILE_SIZE_MB": "Maximum file size to index (in MB)",
    "IGNORE_TEST_FILES": "Skip test files during indexing",
    "IGNORE_HIDDEN_FILES": "Skip hidden files/directories",
    "ENABLE_AUTO_WATCH": "Automatically watch directory after indexing",
    "COMPLEXITY_THRESHOLD": "Cyclomatic complexity warning threshold",
    "MAX_DEPTH": "Maximum directory depth for indexing (unlimited or number)",
    "PARALLEL_WORKERS": "Number of parallel indexing workers",
    "CACHE_ENABLED": "Enable caching for faster re-indexing",
    "IGNORE_DIRS": "Comma-separated list of directory names to ignore during indexing",
    "INDEX_SOURCE": "Store full source code in graph database (for faster indexing use false, for better performance use true)",
    "SCIP_INDEXER": "Use SCIP-based indexing for higher accuracy call/inheritance resolution (requires scip-<lang> tools installed)",
    "SCIP_LANGUAGES": "Comma-separated languages to index via SCIP when SCIP_INDEXER=true (python,typescript,go,rust,java)",
    "SKIP_EXTERNAL_RESOLUTION": "Skip resolution attempts for external library method calls (recommended for enterprise large Java/Spring codebases)",
}

# Valid values for each config key
CONFIG_VALIDATORS = {
    "DEFAULT_DATABASE": ["neo4j", "falkordb", "falkordb-remote", "kuzudb"],
    "INDEX_VARIABLES": ["true", "false"],
    "ALLOW_DB_DELETION": ["true", "false"],
    "DEBUG_LOGS": ["true", "false"],
    "ENABLE_APP_LOGS": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "DISABLED"],
    "LIBRARY_LOG_LEVEL": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    "IGNORE_TEST_FILES": ["true", "false"],
    "IGNORE_HIDDEN_FILES": ["true", "false"],
    "ENABLE_AUTO_WATCH": ["true", "false"],
    "CACHE_ENABLED": ["true", "false"],
    "INDEX_SOURCE": ["true", "false"],
    "SCIP_INDEXER": ["true", "false"],
    "SKIP_EXTERNAL_RESOLUTION": ["true", "false"],
}
DEFAULT_CGCIGNORE_PATTERNS = """\
# Default .cgcignore patterns
# Lines starting with # are comments; blank lines are ignored.
# Patterns follow .gitignore syntax.

node_modules/
venv/
.venv/
env/
.env/
dist/
build/
target/
out/
.git/
.idea/
.vscode/
__pycache__/
*.pyc
*.pyo
*.egg-info/
.tox/
.mypy_cache/
.pytest_cache/
coverage/
.next/
"""


def ensure_config_dir(path: Path = CONFIG_DIR):
    """
    Ensure that the configuration directory exists.
    Creates the directory and a logs subdirectory if they do not already exist.
    """
    path.mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(parents=True, exist_ok=True)


def ensure_global_cgcignore() -> bool:
    """Create ``~/.codegraphcontext/global/.cgcignore`` with sensible defaults
    if it does not already exist.  Returns True when a new file was created."""
    cgcignore_path = CONFIG_DIR / "global" / ".cgcignore"
    if cgcignore_path.exists():
        return False
    cgcignore_path.parent.mkdir(parents=True, exist_ok=True)
    cgcignore_path.write_text(DEFAULT_CGCIGNORE_PATTERNS)
    return True



def load_config() -> Dict[str, str]:
    """
    Load configuration with priority support.
    Priority order (highest to lowest):
    1. Environment variables
    2. Local .env file (in current or parent directories)
    3. Global ~/.codegraphcontext/.env
    
    Note: Does NOT create config directory - caller must call ensure_config_dir() first if needed.
    """
    # Start with defaults
    config = DEFAULT_CONFIG.copy()
    
    # Load global config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        except Exception as e:
            console.print(f"[red]Error loading global config: {e}[/red]")
    
    # Load local .env file if it exists (overrides global)
    local_env = find_local_env()
    if local_env and local_env.exists():
        try:
            with open(local_env, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        # Only override if it's a config key (not database credentials in local file)
                        if key in DEFAULT_CONFIG or key in DATABASE_CREDENTIAL_KEYS:
                            config[key] = value.strip()
        except Exception as e:
            console.print(f"[yellow]Warning: Error loading local .env: {e}[/yellow]")
    
    # Environment variables have highest priority
    for key in DEFAULT_CONFIG.keys():
        env_value = os.getenv(key)
        if env_value is not None:
            config[key] = env_value
    
    return config


def find_local_env() -> Optional[Path]:
    """
    Find a local .env file by searching current directory and parents.
    Returns the first .env file found, or None.
    """
    current = Path.cwd()
    
    # Search up to 5 levels up
    for _ in range(5):
        # 1. Prefer .codegraphcontext/.env if it exists
        cgc_env = current / ".codegraphcontext" / ".env"
        if cgc_env.exists() and cgc_env != CONFIG_FILE:
            return cgc_env
            
        # 2. Fall back to root project .env
        env_file = current / ".env"
        if env_file.exists() and env_file != CONFIG_FILE:
            return env_file
        
        # Stop at root
        if current.parent == current:
            break
        current = current.parent
    
    return None


def save_config(config: Dict[str, str], preserve_db_credentials: bool = True):
    """
    Save configuration to file.
    If preserve_db_credentials is True, existing database credentials will be preserved.
    If preserve_db_credentials is False, credentials from config dict will be written.
    """
    ensure_config_dir()
    
    # Determine which credentials to write
    credentials_to_write = {}
    
    if preserve_db_credentials and CONFIG_FILE.exists():
        # Load existing credentials from file to preserve them
        try:
            with open(CONFIG_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        if key in DATABASE_CREDENTIAL_KEYS:
                            credentials_to_write[key] = value.strip()
        except Exception:
            pass
        # Merge credentials from the config dict (handles both new and updated values)
        for key in DATABASE_CREDENTIAL_KEYS:
            if key in config:
                credentials_to_write[key] = config[key]
    else:
        # Use credentials from the config dict being passed in
        for key in DATABASE_CREDENTIAL_KEYS:
            if key in config:
                credentials_to_write[key] = config[key]
    
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write("# CodeGraphContext Configuration\n")
            f.write(f"# Location: {CONFIG_FILE}\n\n")
            
            # Write database credentials first if they exist
            if credentials_to_write:
                f.write("# ===== Database Credentials =====\n")
                for key in sorted(DATABASE_CREDENTIAL_KEYS):
                    if key in credentials_to_write:
                        f.write(f"{key}={credentials_to_write[key]}\n")
                f.write("\n")
            
            # Write configuration settings
            f.write("# ===== Configuration Settings =====\n")
            for key, value in sorted(config.items()):
                # Skip database credentials (already written above)
                if key in DATABASE_CREDENTIAL_KEYS:
                    continue
                    
                description = CONFIG_DESCRIPTIONS.get(key, "")
                if description:
                    f.write(f"# {description}\n")
                f.write(f"{key}={value}\n\n")
        
        console.print(f"[green]✅ Configuration saved to {CONFIG_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")


def validate_config_value(key: str, value: str) -> tuple[bool, Optional[str]]:
    """
    Validate a configuration value.
    Returns (is_valid, error_message)
    """
    # Skip validation for database credentials (they have their own validation elsewhere)
    if key in DATABASE_CREDENTIAL_KEYS:
        return True, None
    
    # Strip quotes that might be in the value
    value = value.strip().strip("'\"")
    
    # Check if key exists
    if key not in DEFAULT_CONFIG:
        available_keys = ", ".join(sorted(DEFAULT_CONFIG.keys()))
        return False, f"Unknown config key: {key}. Available keys: {available_keys}"
    
    # Validate against specific validators if they exist
    if key in CONFIG_VALIDATORS:
        valid_values = CONFIG_VALIDATORS[key]
        if value.lower() not in [v.lower() for v in valid_values]:
            return False, f"Invalid value for {key}. Must be one of: {', '.join(valid_values)}"
    
    # Specific validation for numeric values
    if key == "MAX_FILE_SIZE_MB":
        try:
            size = int(value)
            if size <= 0:
                return False, "MAX_FILE_SIZE_MB must be a positive number"
        except ValueError:
            return False, "MAX_FILE_SIZE_MB must be a number"
    
    if key == "COMPLEXITY_THRESHOLD":
        try:
            threshold = int(value)
            if threshold <= 0:
                return False, "COMPLEXITY_THRESHOLD must be a positive number"
        except ValueError:
            return False, "COMPLEXITY_THRESHOLD must be a number"
    
    if key == "PARALLEL_WORKERS":
        try:
            workers = int(value)
            if workers <= 0 or workers > 32:
                return False, "PARALLEL_WORKERS must be between 1 and 32"
        except ValueError:
            return False, "PARALLEL_WORKERS must be a number"
    
    if key == "MAX_DEPTH":
        if value.lower() != "unlimited":
            try:
                depth = int(value)
                if depth <= 0:
                    return False, "MAX_DEPTH must be 'unlimited' or a positive number"
            except ValueError:
                return False, "MAX_DEPTH must be 'unlimited' or a number"
    
    if key in ("LOG_FILE_PATH", "DEBUG_LOG_PATH"):
        # Validate path is writable
        log_path = Path(value)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Cannot create log directory: {e}"
    
    if key in ("FALKORDB_PATH", "FALKORDB_SOCKET_PATH"):
        # Validate path is writable
        db_path = Path(value)
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Cannot create directory for {key}: {e}"
        
        # Check if parent directory is writable
        if not os.access(db_path.parent, os.W_OK):
            return False, f"Directory {db_path.parent} is not writable"
    
    return True, None


def get_config_value(key: str) -> Optional[str]:
    """Get a specific configuration value."""
    config = load_config()
    return config.get(key)


def set_config_value(key: str, value: str) -> bool:
    """Set a configuration value. Returns True if successful.

    The special key ``mode`` is delegated to :func:`set_context_mode` so
    that ``cgc config set mode named`` works as expected.
    """
    if key.lower() == "mode":
        return set_context_mode(value.lower())

    # Ensure config directory exists
    ensure_config_dir()
    
    # Validate
    is_valid, error_msg = validate_config_value(key, value)
    if not is_valid:
        console.print(f"[red]❌ {error_msg}[/red]")
        return False
    
    # Load, update, and save
    config = load_config()
    config[key] = value
    save_config(config)
    
    console.print(f"[green]✅ Set {key} = {value}[/green]")
    return True


def reset_config():
    """Reset configuration to defaults (preserves database credentials)."""
    ensure_config_dir()
    save_config(DEFAULT_CONFIG.copy(), preserve_db_credentials=True)
    console.print("[green]✅ Configuration reset to defaults[/green]")
    console.print("[cyan]Note: Database credentials were preserved[/cyan]")



_FIRST_RUN_MARKER = CONFIG_DIR / ".first_run_done"


def _print_welcome_banner() -> None:
    """Print a one-time welcome message explaining the context system."""
    console.print()
    console.print("[bold green]Welcome to CodeGraphContext![/bold green]")
    console.print()
    console.print("CGC organises your code graphs using [bold]contexts[/bold]:")
    console.print("  [cyan]global[/cyan]    - One shared graph for all projects (default)")
    console.print("  [cyan]per-repo[/cyan]  - Each repo gets its own .codegraphcontext/ folder")
    console.print("  [cyan]named[/cyan]     - Create named workspaces (e.g. cgc index . --context MyProject)")
    console.print()
    console.print("Switch modes anytime:  [dim]cgc context mode <global|per-repo|named>[/dim]")
    console.print("Or:                    [dim]cgc config set mode <global|per-repo|named>[/dim]")
    console.print()


def ensure_first_run_bootstrap() -> bool:
    """Run one-time setup for brand-new installs.

    Creates default config files, the global .cgcignore, and prints a
    welcome banner.  Returns True when bootstrap was performed.
    """
    if _FIRST_RUN_MARKER.exists():
        return False

    ensure_config_dir()
    ensure_global_cgcignore()
    # Ensure config.yaml exists (triggers creation with defaults)
    load_context_config()
    _print_welcome_banner()

    # Stamp so we don't repeat
    _FIRST_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _FIRST_RUN_MARKER.write_text("1")
    return True


def ensure_config_file():
    """
    Create default .env config file on first run if it does not exist.
    """
    ensure_config_dir()

    if CONFIG_FILE.exists():
        return False  # file already exists

    save_config(DEFAULT_CONFIG.copy(), preserve_db_credentials=False)
    return True  # file was created




def show_config():
    """Display current configuration in a nice table."""
    created = ensure_config_file()
    if created:
        console.print(
            f"[green]🆕 Created default configuration at {CONFIG_FILE}[/green]\n"
        )
    config = load_config()
    
    # Separate database credentials from configuration
    db_creds = {k: v for k, v in config.items() if k in DATABASE_CREDENTIAL_KEYS}
    config_settings = {k: v for k, v in config.items() if k not in DATABASE_CREDENTIAL_KEYS}
    
    # Show database credentials if they exist
    if db_creds:
        console.print("\n[bold cyan]Database Credentials[/bold cyan]")
        db_table = Table(show_header=True, header_style="bold magenta")
        db_table.add_column("Credential", style="cyan", width=20)
        db_table.add_column("Value", style="green", width=30)
        
        for key in sorted(db_creds.keys()):
            value = db_creds[key]
            # Mask password
            if "PASSWORD" in key:
                value = "********" if value else "(not set)"  
            db_table.add_row(key, value)
        
        console.print(db_table)
    
    # Show configuration settings
    console.print("\n[bold cyan]Configuration Settings[/bold cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan", width=25)
    table.add_column("Value", style="green", width=20)
    table.add_column("Description", style="dim", width=50)
    
    for key in sorted(config_settings.keys()):
        value = config_settings[key]
        description = CONFIG_DESCRIPTIONS.get(key, "")
        
        # Highlight non-default values
        if value != DEFAULT_CONFIG.get(key):
            value_style = "[bold yellow]" + value + "[/bold yellow]"
        else:
            value_style = value
        
        table.add_row(key, value_style, description)
    
    console.print(table)
    console.print(f"\n[cyan]Config file: {CONFIG_FILE}[/cyan]")


# =============================================================================
# CONTEXT SYSTEM  (config.yaml)
# =============================================================================

CONTEXT_CONFIG_FILE = CONFIG_DIR / "config.yaml"
_LEGACY_CONTEXT_CONFIG_FILE = CONFIG_DIR / "cgc_config.yaml"

# Valid mode values
VALID_MODES = ["global", "per-repo", "named"]


@dataclass
class ContextInfo:
    """Metadata for a single named context."""
    name: str
    database: str = "falkordb"          # neo4j | falkordb | kuzudb
    db_path: str = ""                    # resolved at init if empty
    repos: List[str] = field(default_factory=list)
    cgcignore_path: str = ""            # resolved at init if empty


@dataclass
class ContextConfig:
    """Top-level structure stored in ~/.codegraphcontext/config.yaml."""
    version: int = 1
    mode: str = "global"                 # global | per-repo | named
    default_context: str = ""           # used when mode=named and no --context flag
    contexts: Dict[str, ContextInfo] = field(default_factory=dict)


def _default_db_path(context_name: str, database: str) -> str:
    """Return the canonical DB path for a named context."""
    return str(CONFIG_DIR / "contexts" / context_name / "db" / database)


_LEGACY_FALKORDB_PATH = CONFIG_DIR / "global" / "falkordb.db"


def _default_global_db_path(database: str) -> str:
    """Return the canonical DB path for the global context.

    New layout: ``~/.codegraphcontext/global/db/<backend>/``
    For backward-compat, if the legacy flat path exists we keep using it.
    """
    if database == "falkordb" and _LEGACY_FALKORDB_PATH.exists():
        return str(_LEGACY_FALKORDB_PATH)
    return str(CONFIG_DIR / "global" / "db" / database)


def _migrate_legacy_config_yaml() -> None:
    """Rename cgc_config.yaml -> config.yaml if the old name exists and the new one does not."""
    if _LEGACY_CONTEXT_CONFIG_FILE.exists() and not CONTEXT_CONFIG_FILE.exists():
        import shutil
        shutil.copy2(_LEGACY_CONTEXT_CONFIG_FILE, CONTEXT_CONFIG_FILE)
        console.print(f"[dim]Migrated {_LEGACY_CONTEXT_CONFIG_FILE.name} -> {CONTEXT_CONFIG_FILE.name}[/dim]")


def load_context_config() -> ContextConfig:
    """
    Load ~/.codegraphcontext/config.yaml.
    Returns a ContextConfig with defaults if the file does not exist.
    """
    _migrate_legacy_config_yaml()

    if not CONTEXT_CONFIG_FILE.exists():
        cfg = ContextConfig()
        save_context_config(cfg)
        return cfg

    try:
        with open(CONTEXT_CONFIG_FILE, "r") as f:
            raw = yaml.safe_load(f) or {}

        contexts: Dict[str, ContextInfo] = {}
        for name, meta in raw.get("contexts", {}).items():
            meta = meta or {}
            db = meta.get("database", "falkordb")
            ctx = ContextInfo(
                name=name,
                database=db,
                db_path=meta.get("db_path") or _default_db_path(name, db),
                repos=[str(r) for r in meta.get("repos", [])],
                cgcignore_path=meta.get("cgcignore_path") or str(
                    CONFIG_DIR / "contexts" / name / ".cgcignore"
                ),
            )
            contexts[name] = ctx

        return ContextConfig(
            version=raw.get("version", 1),
            mode=raw.get("mode", "global"),
            default_context=raw.get("default_context", ""),
            contexts=contexts,
        )
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config.yaml: {e}. Using defaults.[/yellow]")
        return ContextConfig()


def save_context_config(cfg: ContextConfig) -> None:
    """Persist ContextConfig to ~/.codegraphcontext/config.yaml."""
    ensure_config_dir()

    contexts_raw: Dict[str, Any] = {}
    for name, ctx in cfg.contexts.items():
        contexts_raw[name] = {
            "database": ctx.database,
            "db_path": ctx.db_path,
            "repos": ctx.repos,
            "cgcignore_path": ctx.cgcignore_path,
        }

    raw = {
        "version": cfg.version,
        "mode": cfg.mode,
        "default_context": cfg.default_context,
        "contexts": contexts_raw,
    }

    try:
        with open(CONTEXT_CONFIG_FILE, "w") as f:
            yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        console.print(f"[red]Error saving config.yaml: {e}[/red]")


# ---------------------------------------------------------------------------
# Context Resolution
# ---------------------------------------------------------------------------

@dataclass
class ResolvedContext:
    """Result of resolve_context() — everything needed to instantiate the DB."""
    mode: str             # global | per-repo | named
    context_name: str     # empty for global / per-repo
    database: str         # neo4j | falkordb | kuzudb
    db_path: str          # absolute path to the DB directory
    cgcignore_path: str   # path to the applicable .cgcignore
    is_local: bool = False  # True when a local .codegraphcontext/ was found


def find_local_cgc_dir(start: Optional[Path] = None) -> Optional[Path]:
    """
    Check *start* (default: cwd) for a ``.codegraphcontext/`` directory that
    belongs to a repo (i.e. is NOT the global ``~/.codegraphcontext``).
    Returns the directory path or None.
    """
    current = start or Path.cwd()
    global_dir = CONFIG_DIR.resolve()

    candidate = current / ".codegraphcontext"
    if candidate.exists() and candidate.resolve() != global_dir:
        return candidate
    return None


def resolve_context(
    cli_context: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> ResolvedContext:
    """
    Determine which context / DB to use.

    Resolution order (highest priority first):
      1. --context <name>  CLI flag
      2. Local .codegraphcontext/ directory (per-repo)
      3. Global config.yaml: mode + default_context
      4. Ultimate fallback: global mode, default DB
    """
    cfg = load_context_config()
    cwd = cwd or Path.cwd()

    # --- 1. Explicit CLI flag ---
    if cli_context:
        ctx = cfg.contexts.get(cli_context)
        db = ctx.database if ctx else "falkordb"
        db_path = ctx.db_path if ctx else _default_db_path(cli_context, db)
        cgcignore = (
            ctx.cgcignore_path
            if ctx
            else str(CONFIG_DIR / "contexts" / cli_context / ".cgcignore")
        )
        return ResolvedContext(
            mode="named",
            context_name=cli_context,
            database=db,
            db_path=db_path,
            cgcignore_path=cgcignore,
        )

    # --- 2. Local .codegraphcontext/ in repo ---
    local_cgc = find_local_cgc_dir(cwd)
    
    # If we are in per-repo mode and no local folder was found, create it in CWD
    if local_cgc is None and cfg.mode == "per-repo":
        local_cgc = cwd / ".codegraphcontext"
        local_cgc.mkdir(parents=True, exist_ok=True)
        (local_cgc / "db").mkdir(exist_ok=True)
        
        # Copy global .env into local context for easy per-repo tweaking
        import shutil
        if CONFIG_FILE.exists():
            shutil.copy2(CONFIG_FILE, local_cgc / ".env")
            
        console.print(f"[dim]Auto-initialized per-repo context at {local_cgc}[/dim]")

    if local_cgc is not None:
        # Read local config.yaml if present
        local_yaml = local_cgc / "config.yaml"
        local_db = "falkordb"
        if local_yaml.exists():
            try:
                with open(local_yaml) as f:
                    local_raw = yaml.safe_load(f) or {}
                local_db = local_raw.get("database", "falkordb")
            except Exception:
                pass
        db_path = str(local_cgc / "db" / local_db)
        cgcignore = str(local_cgc / ".cgcignore")
        return ResolvedContext(
            mode="per-repo",
            context_name="",
            database=local_db,
            db_path=db_path,
            cgcignore_path=cgcignore,
            is_local=True,
        )

    # --- 3. Global config.yaml ---
    if cfg.mode == "named":
        ctx_name = cfg.default_context
        ctx = cfg.contexts.get(ctx_name) if ctx_name else None
        db = ctx.database if ctx else "falkordb"
        db_path = ctx.db_path if ctx else _default_db_path(ctx_name, db) if ctx_name else ""
        if not db_path:
            # No default context set — fall through to global
            pass
        else:
            cgcignore = (
                ctx.cgcignore_path
                if ctx
                else str(CONFIG_DIR / "contexts" / ctx_name / ".cgcignore")
            )
            return ResolvedContext(
                mode="named",
                context_name=ctx_name,
                database=db,
                db_path=db_path,
                cgcignore_path=cgcignore,
            )

    # --- 4. Global fallback ---
    db = load_config().get("DEFAULT_DATABASE", "falkordb")
    return ResolvedContext(
        mode="global",
        context_name="",
        database=db,
        db_path=_default_global_db_path(db),
        cgcignore_path=str(CONFIG_DIR / "global" / ".cgcignore"),
    )


# ---------------------------------------------------------------------------
# Context CRUD helpers
# ---------------------------------------------------------------------------

def create_context(
    name: str,
    database: str = "falkordb",
    db_path: Optional[str] = None,
) -> bool:
    """Create a new named context. Returns True on success."""
    cfg = load_context_config()
    if name in cfg.contexts:
        console.print(f"[yellow]Context '{name}' already exists.[/yellow]")
        return False

    resolved_db_path = db_path or _default_db_path(name, database)
    cgcignore = str(CONFIG_DIR / "contexts" / name / ".cgcignore")

    # Ensure the context directories exist (create parent of db_path so DBs can create their files/dirs)
    Path(resolved_db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cgcignore).parent.mkdir(parents=True, exist_ok=True)

    cfg.contexts[name] = ContextInfo(
        name=name,
        database=database,
        db_path=resolved_db_path,
        repos=[],
        cgcignore_path=cgcignore,
    )
    save_context_config(cfg)
    console.print(f"[green]✅ Created context '{name}' (DB: {database})[/green]")
    console.print(f"   [dim]DB path: {resolved_db_path}[/dim]")
    return True


def delete_context(name: str) -> bool:
    """Delete a named context from the registry. Returns True on success."""
    cfg = load_context_config()
    if name not in cfg.contexts:
        console.print(f"[red]Context '{name}' not found.[/red]")
        return False
    del cfg.contexts[name]
    if cfg.default_context == name:
        cfg.default_context = ""
    save_context_config(cfg)
    console.print(f"[green]✅ Deleted context '{name}'[/green]")
    console.print("[dim]Note: DB files were NOT deleted. Remove manually if needed.[/dim]")
    return True


def register_repo_in_context(context_name: str, repo_path: str, auto_create: bool = False) -> bool:
    """Add a repo path to a named context (idempotent).

    When *auto_create* is True the context is silently created with default
    settings if it does not yet exist, matching the UX of
    ``cgc index ./frontend --context ProjectAB`` "just working".
    """
    cfg = load_context_config()
    ctx = cfg.contexts.get(context_name)
    if ctx is None:
        if not auto_create:
            console.print(f"[red]Context '{context_name}' not found. Create it first with 'cgc context create {context_name}'.[/red]")
            return False
        create_context(context_name)
        cfg = load_context_config()
        ctx = cfg.contexts.get(context_name)
        if ctx is None:
            return False
    resolved = str(Path(repo_path).resolve())
    if resolved not in ctx.repos:
        ctx.repos.append(resolved)
        save_context_config(cfg)
    return True


def set_context_mode(mode: str) -> bool:
    """Set the global CGC mode. Returns True on success."""
    if mode not in VALID_MODES:
        console.print(f"[red]Invalid mode '{mode}'. Must be one of: {', '.join(VALID_MODES)}[/red]")
        return False
    cfg = load_context_config()
    cfg.mode = mode
    save_context_config(cfg)
    console.print(f"[green]✅ Mode set to '{mode}'[/green]")
    return True


def set_default_context(name: str) -> bool:
    """Set the default named context used when no --context flag is given."""
    cfg = load_context_config()
    if name and name not in cfg.contexts:
        console.print(f"[red]Context '{name}' not found. Create it first.[/red]")
        return False
    cfg.default_context = name
    save_context_config(cfg)
    console.print(f"[green]✅ Default context set to '{name}'[/green]")
    return True


def list_contexts() -> List[ContextInfo]:
    """Return all named contexts."""
    cfg = load_context_config()
    return list(cfg.contexts.values())
