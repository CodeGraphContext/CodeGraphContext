# cgc_entry.py
# PyInstaller entrypoint — absolute imports only (no relative imports)
import sys
import os

# When frozen by PyInstaller, sys._MEIPASS is the temp extraction dir.
# We add it to the path so codegraphcontext package is importable.
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)

    # If the process is intended to be a FalkorDB worker (spawned by cgc itself)
    if os.getenv('CGC_RUN_FALKOR_WORKER') == 'true':
        from codegraphcontext.core.falkor_worker import run_worker
        run_worker()
        sys.exit(0)

from codegraphcontext.cli.main import app

if __name__ == '__main__':
    app()
