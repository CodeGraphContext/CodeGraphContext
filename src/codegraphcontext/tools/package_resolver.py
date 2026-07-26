import importlib.util
from pathlib import Path
import subprocess
from typing import Optional
import sys
import sysconfig

from ..utils.debug_log import debug_log


# ----------------------------
# SAFE STDLIB CHECK (REPLACES stdlibs module)
# ----------------------------

def _is_stdlib_module(module_name: str) -> bool:
    """Check if module is part of Python stdlib."""
    try:
        if module_name in sys.builtin_module_names:
            return True

        stdlib_path = sysconfig.get_paths().get("stdlib")
        if stdlib_path:
            module_path = importlib.util.find_spec(module_name)
            if module_path and module_path.origin:
                return str(module_path.origin).startswith(stdlib_path)
    except Exception:
        pass
    return False


# ----------------------------
# PYTHON
# ----------------------------

def _get_python_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting local path for Python package: {package_name}")

        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return None

        if spec.origin and spec.origin != "frozen":
            module_file = Path(spec.origin)

            if module_file.name == "__init__.py":
                return str(module_file.parent)

            if _is_stdlib_module(package_name):
                return str(module_file)

            return str(module_file.parent)

        if spec.submodule_search_locations:
            locations = list(spec.submodule_search_locations)
            if locations:
                return str(Path(locations[0]))

        return None

    except Exception as e:
        debug_log(f"Error getting Python package path for {package_name}: {e}")
        return None


# ----------------------------
# NPM / JS
# ----------------------------

def _get_npm_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting local path for npm package: {package_name}")

        local_path = Path("./node_modules") / package_name
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
        debug_log(f"Error npm package path {package_name}: {e}")
        return None


def _get_typescript_package_path(package_name: str) -> Optional[str]:
    return _get_npm_package_path(package_name)


# ----------------------------
# JAVA
# ----------------------------

def _get_java_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting local path for Java package: {package_name}")

        if ":" in package_name:
            group_id, artifact_id = package_name.split(":", 1)
            group_path = group_id.replace(".", "/")
        else:
            artifact_id = package_name
            group_path = None
            group_id = None

        maven_repo = Path.home() / ".m2" / "repository"

        if maven_repo.exists():
            if group_path:
                package_path = maven_repo / group_path / artifact_id
                if package_path.exists():
                    versions = [d for d in package_path.iterdir() if d.is_dir()]
                    if versions:
                        return str(sorted(versions)[-1].resolve())

            for jar in maven_repo.rglob(f"*{artifact_id}*.jar"):
                return str(jar.parent.resolve())

        return None

    except Exception as e:
        debug_log(f"Error Java package path {package_name}: {e}")
        return None


# ----------------------------
# C / C++
# ----------------------------

def _get_c_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting local path for C package: {package_name}")

        try:
            result = subprocess.run(
                ["pkg-config", "--variable=includedir", package_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                path = Path(result.stdout.strip())
                if path.exists():
                    return str(path.resolve())
        except Exception:
            pass

        for base in ["/usr/include", "/usr/local/include"]:
            p = Path(base) / package_name
            if p.exists():
                return str(p.resolve())

        return None

    except Exception as e:
        debug_log(f"Error C package path {package_name}: {e}")
        return None


def _get_cpp_package_path(package_name: str) -> Optional[str]:
    return _get_c_package_path(package_name)


# ----------------------------
# GO
# ----------------------------

def _get_go_package_path(package_name: str) -> Optional[str]:
    try:
        debug_log(f"Getting Go package: {package_name}")

        result = subprocess.run(
            ["go", "list", "-f", "{{.Dir}}", package_name],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            p = Path(result.stdout.strip())
            if p.exists():
                return str(p.resolve())

        return None

    except Exception as e:
        debug_log(f"Error Go package {package_name}: {e}")
        return None


# ----------------------------
# RUBY
# ----------------------------

def _get_ruby_package_path(package_name: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["gem", "which", package_name],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            p = Path(result.stdout.strip())
            if p.exists():
                return str(p.parent.resolve())

        return None

    except Exception:
        return None


# ----------------------------
# PHP
# ----------------------------

def _get_php_package_path(package_name: str) -> Optional[str]:
    vendor = Path("./vendor") / package_name
    if vendor.exists():
        return str(vendor.resolve())
    return None


# ----------------------------
# DART
# ----------------------------

def _get_dart_package_path(package_name: str) -> Optional[str]:
    try:
        pub_cache = Path.home() / ".pub-cache"
        path = pub_cache / "hosted" / "pub.dev" / package_name
        if path.exists():
            return str(path.resolve())
        return None
    except Exception:
        return None


# ----------------------------
# DISPATCHER
# ----------------------------

def get_local_package_path(package_name: str, language: str) -> Optional[str]:
    finders = {
        "python": _get_python_package_path,
        "javascript": _get_npm_package_path,
        "typescript": _get_typescript_package_path,
        "java": _get_java_package_path,
        "c": _get_c_package_path,
        "cpp": _get_cpp_package_path,
        "go": _get_go_package_path,
        "ruby": _get_ruby_package_path,
        "php": _get_php_package_path,
        "dart": _get_dart_package_path,
    }

    finder = finders.get(language)
    if finder:
        return finder(package_name)

    return None