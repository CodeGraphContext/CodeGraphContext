import sys
import os
import time
import signal
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("falkor_worker")

# Global to handle shutdown
db_instance = None

def handle_signal(signum, frame):
    logger.info(f"Received signal {signum}. Stopping FalkorDB worker...")
    sys.exit(0)

def run_worker():
    global db_instance
    
    # Get configuration from env
    db_path = os.getenv('FALKORDB_PATH')
    socket_path = os.getenv('FALKORDB_SOCKET_PATH')
    
    if not db_path or not socket_path:
        logger.error("Missing configuration. FALKORDB_PATH and FALKORDB_SOCKET_PATH must be set.")
        sys.exit(1)
        
    # Ensure dir exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting FalkorDB Lite worker...")
    logger.info(f"DB Path: {db_path}")
    logger.info(f"Socket: {socket_path}")
    
    try:
        import platform
        
        if platform.system() == "Windows":
            raise RuntimeError(
                "CodeGraphContext uses redislite/FalkorDB, which does not support Windows.\n"
                "Please run the project using WSL or Docker."
            )
        
        from redislite.falkordb_client import FalkorDB
        
        # Determine module path for frozen bundles
        server_config = {}
        if getattr(sys, 'frozen', False):
            mei_pass = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            exe_dir  = os.path.dirname(sys.executable)
            
            # All known locations PyInstaller may extract falkordb.so to
            potential_paths = [
                # Standard redislite layout
                os.path.join(mei_pass, 'redislite', 'bin', 'falkordb.so'),
                # falkordblite scripts layout
                os.path.join(mei_pass, 'falkordblite.scripts', 'falkordb.so'),
                # Root of the bundle (add_binary with '.' target)
                os.path.join(mei_pass, 'falkordb.so'),
                # Alongside the executable itself
                os.path.join(exe_dir, 'falkordb.so'),
                # redislite data dir variant
                os.path.join(mei_pass, 'redislite', 'falkordb.so'),
                # falkordblite.libs (shared-lib bundle)
                os.path.join(mei_pass, 'falkordblite.libs', 'falkordb.so'),
            ]
            
            module_path = None
            for p in potential_paths:
                if os.path.exists(p):
                    module_path = p
                    break
            
            if module_path:
                logger.info(f"Using FalkorDB module from bundle: {module_path}")
                server_config['loadmodule'] = module_path
            else:
                logger.error(
                    "Could not find falkordb.so in the PyInstaller bundle. "
                    "Searched: " + str(potential_paths)
                )
                # Exit with a distinct code so the parent can detect FalkorDB is
                # unavailable in this environment and fall back to KùzuDB.
                sys.exit(2)

        # Start Embedded DB
        if os.path.exists(socket_path):
            try:
                os.remove(socket_path)
            except OSError:
                pass

        db_instance = FalkorDB(db_path, unix_socket_path=socket_path, serverconfig=server_config)
        logger.info("FalkorDB Lite is running.")
        
        # Validate that FalkorDB module actually loaded by running a GRAPH.QUERY
        try:
            test_graph = db_instance.select_graph('__cgc_health_check')
            test_graph.query('RETURN 1')
            logger.info("FalkorDB GRAPH.QUERY OK.")
        except Exception as health_err:
            err_str = str(health_err).lower()
            if 'graph.query' in err_str or 'unknown command' in err_str:
                logger.error(
                    f"FalkorDB module not loaded — GRAPH.QUERY unavailable: {health_err}. "
                    "The Redis server started but the FalkorDB .so module was not loaded."
                )
                sys.exit(2)  # same exit code: parent will fall back to KùzuDB
            else:
                logger.warning(f"FalkorDB health-check warning (non-fatal): {health_err}")
        
        # Keep alive loop
        while True:
            time.sleep(1)
            
    except ImportError as e:
        logger.error(f"Failed to import redislite.falkordb_client: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"FalkorDB Worker Critical Failure: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    run_worker()
