# src/codegraphcontext/tools/package_resolver.py
import importlib.util
import stdlibs
from pathlib import Path
import subprocess
from typing import Optional

from ..utils.debug_log import debug_log

def _get_python_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Python package.
    Uses importlib.util.find_spec() to locate the module without executing its code.
    """
    try:
        debug_log(f"Getting local path for Python package: {package_name}")
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return None
        if spec.origin and spec.origin != "frozen":
            module_file = Path(spec.origin)
            if module_file.name == '__init__.py':
                return str(module_file.parent)
            elif package_name in stdlibs.module_names:
                return str(module_file)
            else:
                return str(module_file.parent)
        elif spec.submodule_search_locations:
            locations = list(spec.submodule_search_locations)
            if locations:
                return str(Path(locations[0]))
        return None
    except (ModuleNotFoundError, ValueError):
        return None
    except Exception as e:
        debug_log(f"Error getting local path for {package_name}: {e}")
        return None

def _get_npm_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Node.js package using `npm root`.
    """
    try:
        debug_log(f"Getting local path for npm package: {package_name}")
        local_path = Path(f"./node_modules/{package_name}")
        if local_path.exists():
            return str(local_path.resolve())

        result = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True)
        if result.returncode == 0:
            global_root = result.stdout.strip()
            package_path = Path(global_root) / package_name
            if package_path.exists():
                return str(package_path.resolve())
        return None
    except Exception as e:
        debug_log(f"Error getting npm package path for {package_name}: {e}")
        return None

def _get_typescript_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a TypeScript package.
    TypeScript packages are typically npm packages, so this uses the same logic as npm.
    """
    try:
        debug_log(f"Getting local path for TypeScript package: {package_name}")
        
        # Check local node_modules first
        local_path = Path(f"./node_modules/{package_name}")
        if local_path.exists():
            return str(local_path.resolve())

        # Check global npm packages
        result = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            global_root = result.stdout.strip()
            package_path = Path(global_root) / package_name
            if package_path.exists():
                return str(package_path.resolve())
        
        return None
    except subprocess.TimeoutExpired:
        debug_log(f"npm command timed out for {package_name}")
        return None
    except Exception as e:
        debug_log(f"Error getting TypeScript package path for {package_name}: {e}")
        return None

def _get_java_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Java package (JAR).
    Searches in Maven and Gradle cache directories.
    
    Args:
        package_name: Package name in format "groupId:artifactId" (e.g., "com.google.code.gson:gson")
                     or just "artifactId" for simple search.
    """
    try:
        debug_log(f"Getting local path for Java package: {package_name}")
        
        # Parse package name - expect format "groupId:artifactId" or just "artifactId"
        if ':' in package_name:
            group_id, artifact_id = package_name.split(':', 1)
            # Convert group_id dots to path separators (e.g., com.google.gson -> com/google/gson)
            group_path = group_id.replace('.', '/')
        else:
            # If only artifact_id provided, search for it
            artifact_id = package_name
            group_path = None
        
        search_paths = []
        
        # Maven repository (~/.m2/repository)
        maven_repo = Path.home() / ".m2" / "repository"
        if maven_repo.exists():
            if group_path:
                # Search for specific group/artifact
                package_path = maven_repo / group_path / artifact_id
                if package_path.exists():
                    # Find the latest version directory
                    version_dirs = [d for d in package_path.iterdir() if d.is_dir()]
                    if version_dirs:
                        # Sort by name (assumes semantic versioning) and get the latest
                        latest_version = sorted(version_dirs, key=lambda x: x.name)[-1]
                        return str(latest_version.resolve())
            else:
                # Search for artifact_id in the entire Maven repo
                search_paths.append(maven_repo)
        
        # Gradle cache (~/.gradle/caches/modules-2/files-2.1)
        gradle_cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
        if gradle_cache.exists():
            if group_path:
                group_id_full = group_id if ':' in package_name else None
                if group_id_full:
                    package_path = gradle_cache / group_id_full / artifact_id
                    if package_path.exists():
                        # Find the latest version directory
                        version_dirs = [d for d in package_path.iterdir() if d.is_dir()]
                        if version_dirs:
                            latest_version = sorted(version_dirs, key=lambda x: x.name)[-1]
                            # Gradle stores files in hash subdirectories
                            hash_dirs = [d for d in latest_version.iterdir() if d.is_dir()]
                            if hash_dirs:
                                return str(hash_dirs[0].resolve())
            else:
                search_paths.append(gradle_cache)
        
        # If group_path wasn't provided or not found, search in the cache directories
        if not group_path or search_paths:
            for base_path in search_paths:
                for jar_file in base_path.rglob(f"*{artifact_id}*.jar"):
                    return str(jar_file.parent.resolve())
        
        # Check local lib directories
        local_lib_paths = [
            Path("./lib"),
            Path("./libs"),
            Path("/usr/local/lib/java"),
            Path("/opt/java/lib"),
        ]
        
        for lib_path in local_lib_paths:
            if not lib_path.exists():
                continue
            
            # Look for JAR files matching the artifact name
            for jar_file in lib_path.glob(f"*{artifact_id}*.jar"):
                return str(jar_file.resolve())
        
        return None
    except Exception as e:
        debug_log(f"Error getting Java package path for {package_name}: {e}")
def _get_c_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a C package.
    """
    try:
        debug_log(f"Getting local path for C package: {package_name}")
        
        # Try using pkg-config to find the package
        try:
            result = subprocess.run(
                ["pkg-config", "--variable=includedir", package_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                include_dir = Path(result.stdout.strip())
                package_path = include_dir / package_name
                if package_path.exists():
                    return str(package_path.resolve())
                if include_dir.exists():
                    return str(include_dir.resolve())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            debug_log(f"pkg-config not available or timed out for {package_name}")
        
        # Search in standard system include directories
        common_include_paths = [
            "/usr/include",
            "/usr/local/include",
            "/opt/homebrew/include",
            "/opt/local/include",
            Path.home() / ".local" / "include",
        ]
        
        for base_path in common_include_paths:
            base_path = Path(base_path)
            if not base_path.exists():
                continue
            
            # Check if package exists as a directory
            package_dir = base_path / package_name
            if package_dir.exists() and package_dir.is_dir():
                return str(package_dir.resolve())
            
            # Check for header files with package name
            header_file = base_path / f"{package_name}.h"
            if header_file.exists():
                return str(header_file.resolve())
        
        # Check current directory for local installations
        local_package = Path(f"./{package_name}")
        if local_package.exists():
            return str(local_package.resolve())
        
        return None
    except Exception as e:
        debug_log(f"Error getting C package path for {package_name}: {e}")
        return None
    
def _get_ruby_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Ruby gem.
    """
    try:
        debug_log(f"Getting local path for Ruby gem: {package_name}")
        result = subprocess.run(
            ["gem", "which", package_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gem_path = Path(result.stdout.strip())
            if gem_path.exists():
                lib_dir = gem_path.parent if gem_path.is_file() else gem_path
                # If we are inside a gem (…/gems/foo-x.y.z/lib/foo.rb), prefer the lib/ dir:
                if (lib_dir.name == "lib") and lib_dir.is_dir():
                    return str(lib_dir.resolve())
                # Try parent/lib in case `gem which` returned .../lib/foo.rb
                if (lib_dir / "lib").is_dir():
                    return str((lib_dir / "lib").resolve())
                # Fallback: just return the directory containing the file (stdlib case like 'json')
                return str(lib_dir.resolve())
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        debug_log(f"gem command not available or timed out for {package_name}")
        return None
    except Exception as e:
        debug_log(f"Error getting Ruby gem path for {package_name}: {e}")
        return None

def _get_go_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Go package using `go list`.
    Tries multiple approaches in sequence to handle different package scenarios:
      1) package dir:   go list -f '{{.Dir}}' <pkg>             (works for stdlib, GOPATH, or module subpackages)
      2) module root:   go list -m -f '{{.Dir}}' <module>       (works for full module paths)
      3) force mod:     go list -mod=mod -f '{{.Dir}}' <pkg>    (works when outside a module context)
      4) GOROOT check:  for standard library packages
      5) GOPATH check:  for packages in GOPATH
    """

    def _first_existing_dir(output: str) -> Optional[str]:
        for line in (l.strip().strip("'\"") for l in output.splitlines() if l.strip()):
            p = Path(line)
            if p.exists() and p.is_dir():
                return str(p.resolve())
        return None

    try:
        debug_log(f"Getting local path for Go package: {package_name}")
        
        # 1. Package directory (works for stdlib, GOPATH, or subpackages)
        cp = subprocess.run(
            ["go", "list", "-f", "{{.Dir}}", package_name],
            capture_output=True, text=True, timeout=15
        )
        if cp.returncode == 0:
            d = _first_existing_dir(cp.stdout)
            if d:
                return d

        # 2. Module root directory (where go.mod lives)
        cp2 = subprocess.run(
            ["go", "list", "-m", "-f", "{{.Dir}}", package_name],
            capture_output=True, text=True, timeout=15
        )
        if cp2.returncode == 0:
            d = _first_existing_dir(cp2.stdout)
            if d:
                debug_log(f"Found Go module {package_name} at {d}")
                return d

        # 3. Retry forcing module mode
        cp3 = subprocess.run(
            ["go", "list", "-mod=mod", "-f", "{{.Dir}}", package_name],
            capture_output=True, text=True, timeout=15
        )
        if cp3.returncode == 0:
            d = _first_existing_dir(cp3.stdout)
            if d:
                return d
        
        # 4. Check in GOROOT for standard library packages
        try:
            cp4 = subprocess.run(
                ["go", "env", "GOROOT"],
                capture_output=True, text=True, timeout=5
            )
            if cp4.returncode == 0:
                goroot = cp4.stdout.strip()
                if goroot:
                    std_lib_path = Path(goroot) / "src" / package_name
                    if std_lib_path.exists() and std_lib_path.is_dir():
                        return str(std_lib_path.resolve())
        except Exception as e:
            debug_log(f"Error checking GOROOT for {package_name}: {e}")
        
        # 5. Check in GOPATH as fallback
        try:
            cp5 = subprocess.run(
                ["go", "env", "GOPATH"],
                capture_output=True, text=True, timeout=5
            )
            if cp5.returncode == 0:
                gopath = cp5.stdout.strip()
                if gopath:
                    gopath_lib_path = Path(gopath) / "src" / package_name
                    if gopath_lib_path.exists() and gopath_lib_path.is_dir():
                        debug_log(f"Found Go package in GOPATH {package_name} at {gopath_lib_path}")
                        return str(gopath_lib_path.resolve())
        except Exception as e:
            debug_log(f"Error checking GOPATH for {package_name}: {e}")

        debug_log(f"Could not find Go package: {package_name}")
        return None

    except (subprocess.TimeoutExpired, FileNotFoundError):
        debug_log(f"go command not available or timed out for {package_name}")
        return None
    except Exception as e:
        debug_log(f"Error getting Go package path for {package_name}: {e}")
        return None

def _get_php_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting local path for PHP package: {package_name}")
        
        local_vendor = Path("./vendor") / package_name
        if local_vendor.exists() and local_vendor.is_dir():
            return str(local_vendor.resolve())
        
        current_dir = Path.cwd()
        for parent in [current_dir] + list(current_dir.parents):
            vendor_path = parent / "vendor" / package_name
            if vendor_path.exists() and vendor_path.is_dir():
                return str(vendor_path.resolve())
            
            if (parent / "composer.json").exists():
                break
        
        composer_home = Path.home() / ".composer" / "vendor" / package_name
        if composer_home.exists() and composer_home.is_dir():
            return str(composer_home.resolve())
        
        composer_global = Path.home() / ".config" / "composer" / "vendor" / package_name
        if composer_global.exists() and composer_global.is_dir():
            return str(composer_global.resolve())
        
        return None
    except Exception as e:
        debug_log(f"Error getting PHP package path for {package_name}: {e}")
        return None



def _get_dart_package_path(package_name: str) -> Optional[str]:
    """
    Finds the local installation path of a Dart package.
    Uses 'dart pub cache list' or looks in PUB_CACHE.
    """
    try:
        import os
        debug_log(f"Getting local path for Dart package: {package_name}")
        
        # Check environment variable
        pub_cache = os.environ.get("PUB_CACHE")
        if not pub_cache:
            pub_cache = str(Path.home() / ".pub-cache")
        
        hosted_path = Path(pub_cache) / "hosted" / "pub.dev" / package_name
        if hosted_path.exists():
            # Find the latest version if multiple exist
            versions = [d for d in hosted_path.parent.glob(f"{package_name}-*") if d.is_dir()]
            if versions:
                return str(sorted(versions)[-1].resolve())
            return str(hosted_path.resolve())
            
        return None
    except Exception as e:
        debug_log(f"Error getting Dart package path for {package_name}: {e}")
        return None

def get_local_package_path(package_name: str, language: str) -> Optional[str]:
    """
    Dispatches to the correct package path finder based on the language.
    """
    finders = {
        "python": _get_python_package_path,
        "javascript": _get_npm_package_path,
        "typescript": _get_typescript_package_path,
        "java": _get_java_package_path,
        "c": _get_c_package_path,
        "go": _get_go_package_path,  
        "ruby": _get_ruby_package_path,
        "php": _get_php_package_path,
        "cpp": _get_cpp_package_path,
        "dart": _get_dart_package_path,
    }
    finder = finders.get(language)
    if finder:
        return finder(package_name)
    return None

def _get_cpp_package_path(package_name: str) -> Optional[str]:
    """
    C++ package ka local path find karta hai.
    Pehle pkg-config try karta hai, fir common system paths check karta hai.
    """
    import subprocess
    import os

    # Try pkg-config
    try:
        result = subprocess.run(
            ["pkg-config", "--variable=includedir", package_name],
            capture_output=True,
            text=True,
            check=False
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    except FileNotFoundError:
        pass

    # Common system include/lib folders
    common_paths = [
        f"/usr/include/{package_name}",
        f"/usr/local/include/{package_name}",
        f"/usr/lib/{package_name}",
        f"/usr/local/lib/{package_name}",
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path

    return None

