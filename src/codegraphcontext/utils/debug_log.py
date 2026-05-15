# src/codegraphcontext/utils/debug_log.py
import os
from datetime import datetime
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
    'DISABLED': logging.CRITICAL + 10  # Higher than CRITICAL to disable all
}

def _get_config_value(key, default):
    """Helper to get config value with fallback"""
    try:
        from codegraphcontext.cli.config_manager import get_config_value
        value = get_config_value(key)
        if value is None:
            return default
        # Convert string boolean to actual boolean
        if isinstance(value, str):
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
        return value
    except Exception:
        return default

def _should_log(level_name):
    """Check if a message at the given level should be logged"""
    configured_level = _get_config_value('ENABLE_APP_LOGS', 'INFO')
    
    # Handle legacy boolean values
    if isinstance(configured_level, bool):
        return configured_level
    
    # Convert to uppercase for comparison
    configured_level = str(configured_level).upper()
    
    # If disabled, don't log anything
    if configured_level == 'DISABLED':
        return False
    
    # Get numeric levels
    configured_numeric = LOG_LEVELS.get(configured_level, logging.INFO)
    message_numeric = LOG_LEVELS.get(level_name.upper(), logging.INFO)
    
    # Log if message level >= configured level
    return message_numeric >= configured_numeric

def debug_log(message):
    """Write debug message to a file if DEBUG_LOGS is enabled"""
    # Check if debug logging is enabled via config
    debug_mode = _get_config_value('DEBUG_LOGS', False)
    if not debug_mode:
        return
    
    # Get debug log path from config
    debug_file = _get_config_value('DEBUG_LOG_PATH', os.path.expanduser("~/mcp_debug.log"))
    
    # Ensure parent directory exists
    Path(debug_file).parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(debug_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()

def info_logger(msg):
    """Log info message if log level allows"""
    if _should_log('INFO'):
        return logger.info(msg)

def error_logger(msg):
    """Log error message if log level allows"""
    if _should_log('ERROR'):
        return logger.error(msg)
    
def warning_logger(msg):
    """Log warning message if log level allows"""
    if _should_log('WARNING'):
        return logger.warning(msg)
    
def debug_logger(msg):
    """Log debug message if log level allows"""
    if _should_log('DEBUG'):
        return logger.debug(msg)
