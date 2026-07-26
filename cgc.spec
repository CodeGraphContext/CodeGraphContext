# cgc.spec
# Multi-platform PyInstaller build spec for CodeGraphContext
# Supports: Linux (x86_64/Aarch64), Windows, macOS

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# ── Environment Detection ──────────────────────────────────────────────────
is_win = sys.platform == 'win32'
is_mac = sys.platform == 'darwin'
is_linux = sys.platform == 'linux' or sys.platform == 'linux2'

# Find site-packages dynamically using the 'site' module
import site
prefix = Path(sys.prefix)
search_paths = [prefix]
# Add standard site-packages locations
try:
    search_paths.extend([Path(p) for p in site.getsitepackages()])
except AttributeError:
    # Getsitepackages not available in some venv configs
    pass
# Add user-local site-packages
search_paths.append(Path(site.getusersitepackages()))
# Ensure we only have unique, existing paths
search_paths = list(set([p for p in search_paths if p.exists()]))

print(f"Detected Platform: {sys.platform}")
print(f"Searching for dependencies in: {[str(p) for p in search_paths]}")

# ── 1. Component Lists (Binaries, Datas, Hidden Imports) ───────────────────
binaries = []
datas = []
hidden_imports = [
    'codegraphcontext',
    'codegraphcontext.cli',
    'codegraphcontext.cli.main',
    'codegraphcontext.cli.cli_helpers',
    'codegraphcontext.cli.config_manager',
    'codegraphcontext.cli.registry_commands',
    'codegraphcontext.cli.setup_wizard',
    'codegraphcontext.cli.setup_macos',
    'codegraphcontext.cli.visualizer',
    'codegraphcontext.core',
    'codegraphcontext.core.database',
    'codegraphcontext.core.database_falkordb',
    'codegraphcontext.core.database_falkordb_remote',
    'codegraphcontext.core.database_kuzu',
    'codegraphcontext.core.falkor_worker',
    'codegraphcontext.core.jobs',
    'codegraphcontext.core.watcher',
    'codegraphcontext.core.cgc_bundle',
    'codegraphcontext.core.bundle_registry',
    'codegraphcontext.server',
    'codegraphcontext.tool_definitions',
    'codegraphcontext.prompts',
    'codegraphcontext.tools',
    'codegraphcontext.tools.code_finder',
    'codegraphcontext.tools.graph_builder',
    'codegraphcontext.tools.package_resolver',
    'codegraphcontext.tools.system',
    'codegraphcontext.tools.scip_indexer',
    'codegraphcontext.tools.scip_pb2',
    'codegraphcontext.tools.advanced_language_query_tool',
    'codegraphcontext.tools.languages',
    'codegraphcontext.tools.languages.python',
    'codegraphcontext.tools.languages.javascript',
    'codegraphcontext.tools.languages.typescript',
    'codegraphcontext.tools.languages.typescriptjsx',
    'codegraphcontext.tools.languages.java',
    'codegraphcontext.tools.languages.go',
    'codegraphcontext.tools.languages.rust',
    'codegraphcontext.tools.languages.c',
    'codegraphcontext.tools.languages.cpp',
    'codegraphcontext.tools.languages.ruby',
    'codegraphcontext.tools.languages.php',
    'codegraphcontext.tools.languages.csharp',
    'codegraphcontext.tools.languages.kotlin',
    'codegraphcontext.tools.languages.scala',
    'codegraphcontext.tools.languages.swift',
    'codegraphcontext.tools.languages.haskell',
    'codegraphcontext.tools.languages.dart',
    'codegraphcontext.tools.languages.perl',
    'codegraphcontext.tools.query_tool_languages.python_toolkit',
    'codegraphcontext.tools.query_tool_languages.javascript_toolkit',
    'codegraphcontext.tools.query_tool_languages.typescript_toolkit',
    'codegraphcontext.tools.query_tool_languages.java_toolkit',
    'codegraphcontext.tools.query_tool_languages.go_toolkit',
    'codegraphcontext.tools.query_tool_languages.rust_toolkit',
    'codegraphcontext.tools.query_tool_languages.c_toolkit',
    'codegraphcontext.tools.query_tool_languages.cpp_toolkit',
    'codegraphcontext.tools.query_tool_languages.ruby_toolkit',
    'codegraphcontext.tools.query_tool_languages.csharp_toolkit',
    'codegraphcontext.tools.query_tool_languages.scala_toolkit',
    'codegraphcontext.tools.query_tool_languages.swift_toolkit',
    'codegraphcontext.tools.query_tool_languages.haskell_toolkit',
    'codegraphcontext.tools.query_tool_languages.dart_toolkit',
    'codegraphcontext.tools.query_tool_languages.perl_toolkit',
    'codegraphcontext.tools.handlers.analysis_handlers',
    'codegraphcontext.tools.handlers.indexing_handlers',
    'codegraphcontext.tools.handlers.management_handlers',
    'codegraphcontext.tools.handlers.query_handlers',
    'codegraphcontext.tools.handlers.watcher_handlers',
    'codegraphcontext.utils.debug_log',
    'codegraphcontext.utils.tree_sitter_manager',
    'codegraphcontext.utils.visualize_graph',

    'kuzu',
    'falkordb',
    'redislite',
    'neo4j',
    'neo4j.io',
    'neo4j.auth_management',
    'neo4j.addressing',
    'neo4j.routing',
    'dotenv',
    'typer',
    'typer.core',
    'typer.main',
    'rich',
    'rich.console',
    'rich.table',
    'rich.progress',
    'rich.markup',
    'rich.panel',
    'tree_sitter',
    'tree_sitter_language_pack',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'anyio',
    'click',
    'shellingham',
    'httpx',
    'httpcore',
    'importlib',
    'asyncio',
    'pkg_resources',
    'threading',
    'subprocess',
    'socket',
    'atexit',
]


# Bin extensions by platform
ext = '*.so'
if is_win:
    ext = '*.pyd'
elif is_mac:
    ext = '*.dylib'

def find_pkg_dir(name):
    for p in sys.path:
        if not p: continue
        d = Path(p) / name
        if d.exists():
            return d
    return None

def add_binary(package_path, pattern, target_subdir=None):
    pkg_dir = find_pkg_dir(package_path)
    if pkg_dir:
        for f in pkg_dir.glob(pattern):
            if f.is_file():
                binaries.append((str(f), target_subdir or package_path))
    else:
        print(f"Warning: Could not find package directory: {package_path}")

# tree-sitter core
add_binary('tree_sitter', ext)

# tree-sitter-language-pack: ALL language bindings
add_binary('tree_sitter_language_pack/bindings', ext)

# other tree-sitter bindings
add_binary('tree_sitter_yaml', ext)
add_binary('tree_sitter_embedded_template', ext)
add_binary('tree_sitter_c_sharp', ext)

# KùzuDB complete collection
# We use find_pkg_dir to add the entire folder to datas, ensuring we don't miss any .so, .pyd, or .dylib files
kuzu_dir = find_pkg_dir('kuzu')
if kuzu_dir:
    print(f"Force bundling entire Kuzu directory: {kuzu_dir}")
    datas.append((str(kuzu_dir), 'kuzu'))
else:
    print("WARNING: Could not find 'kuzu' directory to bundle!")
# ── 2. Bundle Logic (Aggressive FalkorDB Collection) ──────────────────────────

# Native dependencies detection
def find_all_native_binaries():
    """Scans all search paths for falkordb.so and redis-server to ensure they are tracked."""
    found = []
    for path in search_paths:
        if path.exists():
            # Find falkordb.so
            for f in path.rglob('falkordb.so'):
                if f.is_file():
                    print(f"Bundling found native module: {f}")
                    found.append((str(f), '.'))
            
            # Find redislite's redis-server to ensure libcrypto/libssl dependencies are analyzed
            for f in path.rglob('redis-server'):
                if f.is_file() and 'redislite' in str(f):
                    print(f"Bundling redislite native server: {f}")
                    # Keep its original folder structure inside redislite/bin
                    found.append((str(f), 'redislite/bin'))
    return found

# Add native binaries
binaries.extend(find_all_native_binaries())

# Tricky packages collection (redislite, falkordb, falkordblite)
if not is_win:
    for pkg in ['redislite', 'falkordb', 'falkordblite']:
        try:
            t_datas, t_binaries, t_hiddenimports = collect_all(pkg)
            datas += t_datas
            binaries += t_binaries
            hidden_imports += t_hiddenimports
        except Exception as e:
            print(f"Warning: collect_all failed for {pkg}: {e}")

# stdlibs: dynamically imports py3.py, py312.py, etc. via importlib
stdlibs_dir = find_pkg_dir('stdlibs')
if stdlibs_dir:
    for f in stdlibs_dir.glob('*.py'):
        datas.append((str(f), 'stdlibs'))

# mcp package data
datas += collect_data_files('mcp', includes=['**/*'])

# mcp.json shipped with CGC
mcp_json = Path('src/codegraphcontext/mcp.json')
if mcp_json.exists():
    datas.append((str(mcp_json), 'codegraphcontext'))

# tree-sitter-language-pack: includes metadata needed at runtime
tslp_dir = find_pkg_dir('tree_sitter_language_pack')
if tslp_dir:
    datas += collect_data_files('tree_sitter_language_pack', includes=['**/*'])

# ── 3. Final Adjustments ────────────────────────────────────────────────────

# Add redislite submodules to hidden imports
hidden_imports += collect_submodules('redislite')
hidden_imports += collect_submodules('falkordb')

# Add platform-specific watchers
if is_win:
    hidden_imports.append('watchdog.observers.read_directory_changes')
elif is_linux:
    hidden_imports.append('watchdog.observers.inotify')
    hidden_imports.append('watchdog.observers.inotify_buffer')
elif is_mac:
    hidden_imports.append('watchdog.observers.fsevents')

# ── 4. Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    ['cgc_entry.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy',
        'PIL', 'cv2', 'torch', 'tensorflow', 'jupyter', 'notebook', 'IPython',
        'pydoc', 'doctest', 'xmlrpc', 'lib2to3', 'test', 'unittest.mock',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── 5. ONE-FILE EXE ──────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cgc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=not is_win,  # strip fails on windows often
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
