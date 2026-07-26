"""
Project-level configuration management for CodeGraphContext.
Handles managing .cgc directory and project-specific settings like custom prompts.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

# Project config directory and file
PROJECT_CONFIG_DIR_NAME = ".cgc"
PROJECT_CONFIG_FILE_NAME = "config.json"


def get_project_root() -> Path:
    """Get the current working directory as project root."""
    return Path.cwd()


def get_project_config_dir(project_root: Optional[Path] = None) -> Path:
    """Get the .cgc directory path for the project."""
    if project_root is None:
        project_root = get_project_root()
    return project_root / PROJECT_CONFIG_DIR_NAME


def get_project_config_file(project_root: Optional[Path] = None) -> Path:
    """Get the config.json file path within .cgc directory."""
    return get_project_config_dir(project_root) / PROJECT_CONFIG_FILE_NAME


def ensure_project_config_dir(project_root: Optional[Path] = None) -> Path:
    """Ensure .cgc directory exists and return its path."""
    config_dir = get_project_config_dir(project_root)
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_project_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load project configuration from .cgc/config.json.
    Returns an empty config structure if file doesn't exist.
    """
    config_file = get_project_config_file(project_root)
    
    if not config_file.exists():
        return {"prompts": []}
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Ensure prompts field exists
            if "prompts" not in config:
                config["prompts"] = []
            return config
    except json.JSONDecodeError as e:
        console.print(f"[yellow]Warning: Invalid JSON in {config_file}: {e}[/yellow]")
        return {"prompts": []}
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
        return {"prompts": []}


def save_project_config(config: Dict[str, Any], project_root: Optional[Path] = None):
    """Save project configuration to .cgc/config.json."""
    ensure_project_config_dir(project_root)
    config_file = get_project_config_file(project_root)
    
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        console.print(f"[red]Error saving project config: {e}[/red]")
        raise


def add_prompt_file(prompt_path: str, project_root: Optional[Path] = None) -> bool:
    """
    Add a custom prompt file to the project configuration.
    Validates that the file exists and prevents duplicates.
    Stores paths relative to project root.
    
    Returns True if successful, False otherwise.
    """
    if project_root is None:
        project_root = get_project_root()
    
    # Convert to Path object and resolve
    prompt_file = Path(prompt_path)
    
    # Check if file exists
    if not prompt_file.exists():
        console.print(f"[red]❌ File not found: {prompt_path}[/red]")
        return False
    
    if not prompt_file.is_file():
        console.print(f"[red]❌ Not a file: {prompt_path}[/red]")
        return False
    
    # Make path relative to project root if it's absolute and within project
    try:
        if prompt_file.is_absolute():
            try:
                relative_path = prompt_file.relative_to(project_root)
                prompt_path_str = str(relative_path).replace("\\", "/")
            except ValueError:
                # File is outside project root, store as absolute
                prompt_path_str = str(prompt_file.resolve()).replace("\\", "/")
        else:
            prompt_path_str = str(prompt_file).replace("\\", "/")
    except Exception:
        prompt_path_str = str(prompt_file).replace("\\", "/")
    
    # Load current config
    config = load_project_config(project_root)
    
    # Check for duplicates
    if prompt_path_str in config["prompts"]:
        console.print(f"[yellow]⚠ Prompt file already registered: {prompt_path_str}[/yellow]")
        return False
    
    # Add to config
    config["prompts"].append(prompt_path_str)
    save_project_config(config, project_root)
    
    console.print(f"[green]✅ Added prompt file: {prompt_path_str}[/green]")
    return True


def list_prompt_files(project_root: Optional[Path] = None) -> List[str]:
    """
    Get list of registered prompt files.
    Returns list of prompt file paths.
    """
    config = load_project_config(project_root)
    return config.get("prompts", [])


def remove_prompt_file(prompt_path: str, project_root: Optional[Path] = None) -> bool:
    """
    Remove a prompt file from the project configuration.
    
    Returns True if successful, False otherwise.
    """
    if project_root is None:
        project_root = get_project_root()
    
    # Normalize the path for comparison
    prompt_file = Path(prompt_path)
    
    # Try both relative and absolute versions
    try:
        if prompt_file.is_absolute():
            try:
                relative_path = prompt_file.relative_to(project_root)
                prompt_path_normalized = str(relative_path).replace("\\", "/")
            except ValueError:
                prompt_path_normalized = str(prompt_file.resolve()).replace("\\", "/")
        else:
            prompt_path_normalized = str(prompt_file).replace("\\", "/")
    except Exception:
        prompt_path_normalized = str(prompt_file).replace("\\", "/")
    
    # Load current config
    config = load_project_config(project_root)
    
    # Try to remove - check both the normalized path and original
    original_length = len(config["prompts"])
    config["prompts"] = [p for p in config["prompts"] if p not in (prompt_path, prompt_path_normalized)]
    
    if len(config["prompts"]) == original_length:
        console.print(f"[yellow]⚠ Prompt file not found in config: {prompt_path}[/yellow]")
        return False
    
    save_project_config(config, project_root)
    console.print(f"[green]✅ Removed prompt file: {prompt_path}[/green]")
    return True


def get_prompt_file_contents(project_root: Optional[Path] = None) -> List[str]:
    """
    Load contents of all registered prompt files.
    Skips files that don't exist and logs warnings.
    
    Returns list of prompt file contents in order.
    """
    if project_root is None:
        project_root = get_project_root()
    
    prompt_files = list_prompt_files(project_root)
    contents = []
    
    for prompt_path in prompt_files:
        # Resolve path relative to project root
        prompt_file = Path(prompt_path)
        if not prompt_file.is_absolute():
            prompt_file = project_root / prompt_file
        
        # Try to read file
        try:
            if not prompt_file.exists():
                logger.warning(f"Skipping missing prompt file: {prompt_path}")
                continue
            
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    contents.append(content)
        except Exception as e:
            logger.warning(f"Error reading prompt file {prompt_path}: {e}")
            continue
    
    return contents
