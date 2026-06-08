# src/codegraphcontext/tools/scip_indexer.py
"""
scip_indexer.py
---------------
SCIP-based indexing pipeline. Only activated when SCIP_INDEXER=true in config.

SCIP (Semantic Code Intelligence Protocol) is a language-agnostic protocol that
uses actual compiler / type-checker tooling (e.g. Pyright for Python, tsc for
TypeScript) to produce a single `index.scip` protobuf file containing:
  - Every symbol definition (function, class, variable) with its file + line
  - Every symbol reference, mapping back to its definition
  - Type signatures, docstrings, and symbol kinds

This gives us compiler-level accuracy for CALLS and INHERITS edges instead of
the heuristic imports_map approach used in Tree-sitter mode.

Workflow (called by GraphBuilder.build_graph_from_path_async when enabled):
  1. ScipIndexer.run(path) → runs the appropriate scip-<lang> CLI, returns path to index.scip
  2. ScipIndexParser.parse(index_scip_path) → returns {nodes, edges} dicts
  3. indexing.persistence.GraphWriter writes nodes + edges via the same Cypher MERGE queries as Tree-sitter mode.
  4. Tree-sitter supplement pass adds: cyclomatic_complexity, source text, decorators.

Supported SCIP indexers and their install commands:
  python     → pip install scip-python   (uses Pyright)
  typescript → npm install -g @sourcegraph/scip-typescript
  javascript → npm install -g @sourcegraph/scip-typescript  (same binary, uses --infer-tsconfig for JS-only projects)
  go         → go install github.com/sourcegraph/scip-go/cmd/scip-go@latest
  rust       → cargo install scip-rust (or rustup component add rust-analyzer)
  java       → https://github.com/sourcegraph/scip-java
  c / c++    → scip-clang (JSON compilation database: compile_commands.json)
  csharp     → scip-dotnet (dotnet tool install --global scip-dotnet)

JavaScript indexing notes:
  - Pure JS projects (no tsconfig.json): scip-typescript index --infer-tsconfig
  - Mixed JS/TS projects (tsconfig.json present): scip-typescript index  (tsconfig covers .js via allowJs)
  - Add @types/* packages as devDependencies for better type inference quality.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.debug_log import error_logger, info_logger, warning_logger
from ..utils.path_ignore import file_path_has_ignore_dir_segment

# ---------------------------------------------------------------------------
# SCIP indexer orchestration
# ---------------------------------------------------------------------------

# Maps file extension → (language name, scip CLI binary name, install hint, docker image)
EXTENSION_TO_SCIP: Dict[str, Tuple[str, str, str, str]] = {
    ".py":    ("python",     "scip-python",     "pip install scip-python", "sourcegraph/scip-python"),
    ".ipynb": ("python",     "scip-python",     "pip install scip-python", "sourcegraph/scip-python"),
    ".ts":    ("typescript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".tsx":   ("typescript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".js":    ("javascript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".jsx":   ("javascript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".mjs":   ("javascript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".cjs":   ("javascript", "scip-typescript", "npm install -g @sourcegraph/scip-typescript", "sourcegraph/scip-typescript"),
    ".go":    ("go",         "scip-go",         "go install github.com/sourcegraph/scip-go/...@latest", "sourcegraph/scip-go"),
    ".rs":    ("rust",       "scip-rust",       "cargo install scip-rust", "sourcegraph/scip-rust"),
    ".java":  ("java",       "scip-java",       "see https://github.com/sourcegraph/scip-java", "sourcegraph/scip-java"),
    ".kt":    ("kotlin",     "scip-java",       "see https://github.com/sourcegraph/scip-java", "sourcegraph/scip-java"),
    ".scala": ("scala",      "scip-java",       "see https://github.com/sourcegraph/scip-java", "sourcegraph/scip-java"),
    ".dart":  ("dart",       "scip_dart",       "dart pub global activate scip_dart", "dart:stable"),
    ".cpp":   ("cpp",        "scip-clang",      "brew install llvm", "sourcegraph/scip-clang:sha-1704d3d"),
    ".hpp":   ("cpp",        "scip-clang",      "brew install llvm", "sourcegraph/scip-clang:sha-1704d3d"),
    ".hh":    ("cpp",        "scip-clang",      "brew install llvm", "sourcegraph/scip-clang:sha-1704d3d"),
    ".c":     ("c",          "scip-clang",      "brew install llvm", "sourcegraph/scip-clang:sha-1704d3d"),
    ".h":     ("cpp",        "scip-clang",      "brew install llvm", "sourcegraph/scip-clang:sha-1704d3d"),
    ".cs":    ("csharp",     "scip-dotnet",     "dotnet tool install --global scip-dotnet", "sourcegraph/scip-dotnet"),
    ".php":   ("php",        "scip-php",        "composer global require davidrjenni/scip-php", "davidrjenni/scip-php"),
    ".rb":    ("ruby",       "scip-ruby",       "gem install scip-ruby", ""),
    ".swift": ("swift",      "scip-swift",      "brew install scip-swift", ""),
    ".ex":    ("elixir",     "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
    ".exs":   ("elixir",     "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
    ".hs":    ("haskell",    "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
    ".lua":   ("lua",        "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
    ".pl":    ("perl",       "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
    ".pm":    ("perl",       "scip-ctags",      "go install github.com/sourcegraph/scip-ctags/cmd/scip-ctags@latest", "sourcegraph/scip-ctags"),
}


def is_scip_available(lang: str) -> bool:
    """Check whether the SCIP indexer (binary or docker) for this language is available."""
    has_docker = shutil.which("docker") is not None
    for ext, (l, binary, _, docker_image) in EXTENSION_TO_SCIP.items():
        if l == lang:
            if shutil.which(binary) is not None:
                return True
            if has_docker and docker_image:
                return True
    return False


def detect_project_lang(path: Path, scip_languages: List[str]) -> Optional[str]:
    """
    Detect the primary language of a project folder by counting files.
    Only returns a language if it is in the user's SCIP_LANGUAGES list.
    """
    if not path.is_dir():
        ext = path.suffix
        lang = EXTENSION_TO_SCIP.get(ext, (None, None, None, None))[0]
        return lang if lang in scip_languages else None

    counts: Dict[str, int] = {}
    for ext, (lang, _, _, _) in EXTENSION_TO_SCIP.items():
        if lang not in scip_languages:
            continue
        counts[lang] = counts.get(lang, 0) + sum(
            1 for _ in path.rglob(f"*{ext}") if not file_path_has_ignore_dir_segment(Path(_), path)
        )

    if not counts:
        return None

    # Return the most frequent language
    return max(counts, key=counts.get)


class ScipIndexer:
    """
    Handles running the external SCIP indexer binaries.
    Takes a project path and language, runs the appropriate CLI, and
    returns the path to the resulting index.scip file.
    """

    def run(self, project_path: Path, lang: str, output_dir: Path) -> Optional[Path]:
        """
        Run the SCIP indexer for `lang` on `project_path`.
        Returns path to index.scip, or None if the indexer failed / is not installed.
        """
        binary, expected_binary, install_hint, docker_image = self._get_binary(lang)
        output_file = output_dir / "index.scip"
        
        if binary:
            cmd = self._build_command(lang, binary, project_path, output_file, scratch_dir=output_dir)
            if not cmd:
                warning_logger(f"No SCIP command template defined for language: {lang}")
                return None

            info_logger(f"Running local SCIP indexer: {' '.join(str(c) for c in cmd)}")
            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(project_path),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0 and output_file.exists():
                    info_logger(f"SCIP index written to {output_file}")
                    return output_file
                warning_logger(f"Local SCIP indexer failed (code {result.returncode}). stderr: {result.stderr[:500]}")
            except Exception as e:
                warning_logger(f"Local SCIP indexer failed: {e}")

        # Fallback to Docker
        if docker_image and shutil.which("docker"):
            info_logger(f"Attempting SCIP indexing via Docker ({docker_image})...")
            try:
                # 1. Pre-run: for Go we often need 'go mod tidy'
                if lang == "go":
                    info_logger("Running 'go mod tidy' inside container first...")
                    subprocess.run(
                        ["docker", "run", "--rm", "-v", f"{project_path.resolve()}:/src", "-w", "/src", docker_image, "go", "mod", "tidy"],
                        capture_output=True, timeout=120
                    )

                # 2. Run indexer
                docker_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{project_path.resolve()}:/src",
                    "-v", f"{output_dir.resolve()}:/out",
                    "-w", "/src",
                    docker_image,
                ]
                
                # Build argv using real host paths (compdb discovery, resolved compdb, C# csproj).
                # Map those paths to /src and /out for the container after building.
                internal_cmd = self._build_command(
                    lang, expected_binary, project_path.resolve(), output_file, scratch_dir=output_dir
                )
                if internal_cmd and lang in ("cpp", "c"):
                    repl = []
                    for arg in internal_cmd:
                        s = str(arg)
                        if s.startswith("--compdb-path="):
                            hp = s.split("=", 1)[1]
                            hp2 = ScipIndexer._compdb_host_paths_to_container(
                                hp, project_path.resolve(), output_dir
                            )
                            repl.append(f"--compdb-path={hp2}")
                        else:
                            repl.append(arg)
                    internal_cmd = repl
                if lang == "go" and not binary:
                    # Specific override for scip-go if binary not found locally
                    internal_cmd = ["scip-go", "index", ".", "--output", "/out/index.scip"]
                elif lang == "dart":
                    # Dart docker image doesn't have scip_dart pre-installed
                    internal_cmd = ["bash", "-c", "dart pub global activate scip_dart && dart pub get && dart pub global run scip_dart ./"]
                elif lang in ("cpp", "c"):
                    # sourcegraph/scip-clang image has scip-clang as its entrypoint;
                    # strip the binary name (first element) since it's the entrypoint.
                    # Map host project + output mount paths into the container.
                    internal_cmd = internal_cmd[1:]
                    proj_h = str(project_path.resolve())
                    out_h = str(output_dir.resolve())
                    mapped: List[str] = []
                    for arg in internal_cmd:
                        s = str(arg)
                        if s.startswith("--compdb-path="):
                            v = s.split("=", 1)[1]
                            v = v.replace(proj_h, "/src").replace(out_h, "/out")
                            mapped.append(f"--compdb-path={v}")
                        else:
                            mapped.append(s.replace(proj_h, "/src").replace(out_h, "/out"))
                    internal_cmd = mapped
                elif lang == "csharp":
                    proj_h = str(project_path.resolve())
                    out_h = str(output_dir.resolve())
                    internal_cmd = [str(a).replace(proj_h, "/src").replace(out_h, "/out") for a in internal_cmd]
                
                docker_cmd.extend(internal_cmd)
                
                info_logger(f"Running Docker command: {' '.join(docker_cmd)}")
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    if output_file.exists():
                        info_logger(f"SCIP index written to {output_file} via Docker")
                        return output_file
                    
                    # Workaround: Some SCIP indexers (like scip-rust) ignore --output and write to CWD
                    cwd_index = project_path / "index.scip"
                    if cwd_index.exists():
                        if cwd_index.resolve() != output_file.resolve():
                            shutil.move(str(cwd_index), str(output_file))
                        info_logger(f"SCIP index written to {output_file} via Docker (moved from project root)")
                        return output_file
                error_logger(f"Docker SCIP indexing failed (code {result.returncode}). stderr: {result.stderr[:500]}")
            except Exception as e:
                error_logger(f"Docker SCIP indexing failed: {e}")

        if not binary:
            warning_logger(f"SCIP indexer for '{lang}' not found locally or in Docker. Install with: {install_hint}")
        return None

    def _get_binary(self, lang: str) -> Tuple[Optional[str], str, str, Optional[str]]:
        for ext, (l, binary, install_hint, docker_image) in EXTENSION_TO_SCIP.items():
            if l == lang:
                found = shutil.which(binary)
                return found, binary, install_hint, docker_image
        return None, lang, "unknown language", None

    @staticmethod
    def _find_compdb(project_path: Path) -> Optional[str]:
        """Search for compile_commands.json in common locations relative to project_path."""
        candidates = [
            project_path / "compile_commands.json",
            project_path / "build" / "compile_commands.json",
        ]
        for p in project_path.glob("cmake-build-*/compile_commands.json"):
            candidates.append(p)
        for p in project_path.glob("out/*/compile_commands.json"):
            candidates.append(p)
        for c in candidates:
            if c.is_file():
                return str(c.resolve())
        return None

    @staticmethod
    def _resolve_compdb_paths(
        compdb_path: str, project_path: Path, scratch_dir: Optional[Path]
    ) -> str:
        """Ensure all 'directory' fields in the compile_commands.json are absolute.

        scip-clang requires absolute paths.  If every entry is already
        absolute we return the original path unchanged.  Otherwise we
        write a resolved copy under scratch_dir (or project_path) and
        return its path.
        """
        base_dir = scratch_dir if scratch_dir is not None else project_path
        try:
            with open(compdb_path, "r") as f:
                entries = json.load(f)
        except Exception:
            return compdb_path

        needs_rewrite = False
        for entry in entries:
            d = entry.get("directory", "")
            if not os.path.isabs(d):
                needs_rewrite = True
                break

        if not needs_rewrite:
            return compdb_path

        resolved_entries = []
        for entry in entries:
            e = dict(entry)
            d = e.get("directory", ".")
            if not os.path.isabs(d):
                e["directory"] = str((project_path / d).resolve())
            resolved_entries.append(e)

        base_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = str((base_dir / "cgc_compile_commands.json").resolve())
        with open(resolved_path, "w") as f:
            json.dump(resolved_entries, f, indent=2)
        return resolved_path

    @staticmethod
    def _compdb_host_paths_to_container(
        compdb_host_path: str, project_host: Path, out_dir_host: Path
    ) -> str:
        """Rewrite compile_commands.json so directory/file use /src paths for Docker."""
        proj_r = str(project_host.resolve())
        with open(compdb_host_path, "r") as f:
            entries = json.load(f)
        for e in entries:
            d = e.get("directory", "")
            if isinstance(d, str) and d.startswith(proj_r):
                rest = d[len(proj_r) :].lstrip("/\\")
                e["directory"] = "/src/" + rest if rest else "/src"
            fn = e.get("file", "")
            if isinstance(fn, str) and os.path.isabs(fn) and fn.startswith(proj_r):
                rest = fn[len(proj_r) :].lstrip("/\\")
                e["file"] = "/src/" + rest if rest else "/src"
        out_path = out_dir_host / "cgc_compile_commands.docker.json"
        with open(out_path, "w") as f:
            json.dump(entries, f, indent=2)
        return str(out_path.resolve())

    @staticmethod
    def _find_csharp_project(project_path: Path) -> Optional[Path]:
        """Find the first .sln or .csproj file for scip-dotnet."""
        for sln in project_path.glob("*.sln"):
            return sln
        for csproj in project_path.rglob("*.csproj"):
            if not file_path_has_ignore_dir_segment(csproj, project_path):
                return csproj
        return None

    def _build_command(
        self,
        lang: str,
        binary: str,
        project_path: Path,
        output_file: Path,
        scratch_dir: Optional[Path] = None,
    ) -> Optional[List]:
        """Build the CLI command for each supported SCIP indexer."""
        out = str(output_file)

        if lang == "python":
            return [binary, "index", ".", "--output", out]

        elif lang == "typescript":
            return [binary, "index", "--output", out]

        elif lang == "javascript":
            has_tsconfig = (project_path / "tsconfig.json").exists()
            if has_tsconfig:
                return [binary, "index", "--output", out]
            else:
                return [binary, "index", "--infer-tsconfig", "--output", out]

        elif lang == "go":
            return [binary, "index", ".", "--output", out]

        elif lang == "rust":
            return [binary, "index", "--output", out]

        elif lang == "dart":
            # For local installations, 'binary' is usually just 'scip_dart' or we run via 'dart pub global run scip_dart ./'
            # We assume 'binary' is resolved or we rely on 'dart'
            return ["dart", "pub", "global", "run", "scip_dart", "./"]

        elif lang == "java":
            return [binary, "index", "--output", out]

        elif lang in ("cpp", "c"):
            compdb = self._find_compdb(project_path)
            if not compdb:
                warning_logger(
                    f"[SCIP] No compile_commands.json found under {project_path.resolve()}. "
                    "scip-clang requires a JSON compilation database (real compile commands per .c/.cpp file). "
                    "Create one with CMake (-DCMAKE_EXPORT_COMPILE_COMMANDS=ON), or capture builds with "
                    "Bear (https://github.com/rizsotto/Bear). "
                    "Without it SCIP cannot run for C/C++; CGC falls back to Tree-sitter. "
                    'See README section "SCIP indexing (optional)".'
                )
                return None
            resolved = self._resolve_compdb_paths(compdb, project_path, scratch_dir)
            cmd = [binary, f"--compdb-path={resolved}", f"--index-output-path={out}"]
            return cmd

        elif lang == "csharp":
            csproj = self._find_csharp_project(project_path)
            if csproj:
                csproj_abs = csproj.resolve()
                wd = str(csproj_abs.parent)
                return [
                    binary,
                    "index",
                    str(csproj_abs),
                    "--working-directory",
                    wd,
                    "--output",
                    out,
                ]
            return [binary, "index", "--output", out]

        elif lang == "php":
            return [binary, "index", "--project-root", str(project_path), "--output", out]

        elif binary == "scip-ctags":
            return [binary, "index", "--output", out]

        return None


class ScipIndexParser:
    """
    Parses an index.scip (Protobuf) file and extracts function calls,
    definitions, and relationships.
    """

    def parse(self, index_scip_path: Path, project_path: Path) -> Dict[str, Any]:
        try:
            from . import scip_pb2  # type: ignore
        except Exception as e:
            error_logger(f"Failed to import codegraphcontext.tools.scip_pb2: {e}")
            return {}

        try:
            with open(index_scip_path, "rb") as f:
                index = scip_pb2.Index()
                index.ParseFromString(f.read())
        except Exception as e:
            error_logger(f"Failed to parse SCIP index at {index_scip_path}: {e}")
            return {}

        symbol_def_table: Dict[str, Dict] = {}

        for doc in index.documents:
            for occ in doc.occurrences:
                if occ.symbol.startswith("local "):
                    continue
                role = getattr(occ, "symbol_roles", getattr(occ, "role", 0))
                if role & 1: # Definition
                    symbol_def_table[occ.symbol] = {
                        "file": doc.relative_path,
                        "line": occ.range[0] + 1 if occ.range else 0,
                    }
                    
                # Rust trait implementation extraction from symbol string
                # Pattern: ...impl#[StructName][TraitName]...
                import re
                impl_match = re.search(r"impl#\[([^\]]+)\]\[([^\]]+)\]", occ.symbol)
                if impl_match:
                    struct_name = impl_match.group(1)
                    trait_name = impl_match.group(2)
                    # We store this mapping globally to apply later
                    if "rust_impls" not in symbol_def_table:
                        symbol_def_table["rust_impls"] = {}
                    if struct_name not in symbol_def_table["rust_impls"]:
                        symbol_def_table["rust_impls"][struct_name] = set()
                    symbol_def_table["rust_impls"][struct_name].add(trait_name)

        for doc in index.documents:
            for sym_info in doc.symbols:
                if sym_info.symbol in symbol_def_table:
                    symbol_def_table[sym_info.symbol]["display_name"] = sym_info.display_name
                    symbol_def_table[sym_info.symbol]["documentation"] = "\n".join(sym_info.documentation)
                    symbol_def_table[sym_info.symbol]["kind"] = sym_info.kind
                    
                    bases = []
                    for rel in sym_info.relationships:
                        if rel.is_implementation:
                            bases.append(rel.symbol)
                    symbol_def_table[sym_info.symbol]["bases"] = bases

        for sym_info in index.external_symbols:
            if sym_info.symbol in symbol_def_table:
                symbol_def_table[sym_info.symbol]["display_name"] = sym_info.display_name
                symbol_def_table[sym_info.symbol]["documentation"] = "\n".join(sym_info.documentation)
                symbol_def_table[sym_info.symbol]["kind"] = sym_info.kind

        # Load source lines BEFORE kind inference so we can inspect source
        # to distinguish interfaces/traits from classes for indexers that
        # report Kind 0 for all symbols (e.g. scip-php).
        files_data: Dict[str, Dict] = {}
        doc_source_lines: Dict[str, List[str]] = {}
        for doc in index.documents:
            src_path = project_path / doc.relative_path
            try:
                doc_source_lines[doc.relative_path] = src_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                doc_source_lines[doc.relative_path] = []

        for sym, info in symbol_def_table.items():
            if sym == "rust_impls":
                continue
            if info.get("kind", 0) == 0:
                file_path = info.get("file", "")
                line_num = info.get("line", 0)
                src_lines = doc_source_lines.get(file_path, [])
                ck = self._infer_cxx_zero_kind(sym, line_num, src_lines)
                if ck:
                    info["kind"] = ck
                    continue
                if sym.endswith("#"):
                    kind = 7  # Default: class
                    if sym.startswith("scip-go") or sym.startswith("rust-analyzer"):
                        kind = 49  # Struct
                    else:
                        # Check source to distinguish class/interface/trait
                        source = src_lines
                        if 0 < line_num <= len(source):
                            src_line = source[line_num - 1].strip().lower()
                            if src_line.startswith("interface "):
                                kind = 20  # Interface
                            elif src_line.startswith("trait "):
                                kind = 53  # Trait
                    info["kind"] = kind
                elif sym.endswith("()."):
                    info["kind"] = 26 if "#" in sym else 17
            
            # Apply Rust implementations if available
            rust_impls = symbol_def_table.get("rust_impls", {})
            name = self._name_from_symbol(sym)
            if name in rust_impls and info.get("kind") in (7, 18, 20, 49, 53, 54):
                info["bases"] = list(set(info.get("bases", []) + list(rust_impls[name])))

        for doc in index.documents:
            rel_path = doc.relative_path
            abs_path = str((project_path / rel_path).resolve())
            source_lines = doc_source_lines.get(rel_path, [])

            file_data: Dict[str, Any] = {
                "functions": [], "classes": [], "variables": [], "imports": [],
                "function_calls_scip": [], "module_level_calls_scip": [],
                "path": abs_path, "lang": self._lang_from_path(rel_path),
                "is_dependency": False,
            }

            definition_symbols_in_doc = []
            for occ in doc.occurrences:
                role = getattr(occ, "symbol_roles", getattr(occ, "role", 0))
                if role & 1:
                    definition_symbols_in_doc.append(occ)

            for occ in doc.occurrences:
                sym = occ.symbol
                if sym.startswith("local ") or sym == "rust_impls": continue
                line = occ.range[0] + 1 if occ.range else 0
                role = getattr(occ, "symbol_roles", getattr(occ, "role", 0))

                if role & 1:  # Definition
                    defn = symbol_def_table.get(sym, {})
                    kind = defn.get("kind", 0)
                    if kind == 0:
                        ck = self._infer_cxx_zero_kind(sym, line, source_lines)
                        if ck:
                            kind = ck
                    if kind == 0:
                        # Check method before function: methods have # in symbol
                        if sym.endswith("().") and "#" in sym:
                            kind = 26  # Method
                        elif sym.endswith("()."):
                            kind = 17  # Function
                        elif sym.endswith("#"):
                            # Check source to distinguish class/interface/trait
                            src = doc_source_lines.get(rel_path, [])
                            src_line = src[line - 1].strip().lower() if 0 < line <= len(src) else ""
                            if src_line.startswith("interface "):
                                kind = 20
                            elif src_line.startswith("trait "):
                                kind = 53
                            elif sym.startswith("scip-go") or sym.startswith("rust-analyzer"):
                                kind = 49
                            else:
                                kind = 7
                    
                    name = self._name_from_symbol(sym)
                    args, return_type = self._parse_signature(defn.get("display_name", ""), kind)

                    node = {
                        "name": name, "line_number": line, "end_line": line,
                        "docstring": defn.get("documentation") or None,
                        "lang": file_data["lang"], "is_dependency": False,
                        "return_type": return_type, "args": args,
                    }

                    if kind in (26, 17):
                        node.update({"cyclomatic_complexity": 1, "decorators": [], "context": None, "class_context": None})
                        file_data["functions"].append(node)
                    elif kind == 7:
                        node["bases"] = [self._name_from_symbol(b) for b in defn.get("bases", [])]
                        node["context"] = None
                        file_data["classes"].append(node)
                    elif kind == 20 or kind == 54: # Interface or Protocol
                        node["bases"] = [self._name_from_symbol(b) for b in defn.get("bases", [])]
                        node["context"] = None
                        if "interfaces" not in file_data: file_data["interfaces"] = []
                        file_data["interfaces"].append(node)
                    elif kind == 18: # Enum
                        node["context"] = None
                        if "enums" not in file_data: file_data["enums"] = []
                        file_data["enums"].append(node)
                    elif kind == 49: # Struct
                        node["bases"] = [self._name_from_symbol(b) for b in defn.get("bases", [])]
                        node["context"] = None
                        if "structs" not in file_data: file_data["structs"] = []
                        file_data["structs"].append(node)
                    elif kind == 53: # Trait
                        node["bases"] = [self._name_from_symbol(b) for b in defn.get("bases", [])]
                        node["context"] = None
                        if "traits" not in file_data: file_data["traits"] = []
                        file_data["traits"].append(node)
                    elif kind in (61, 15):
                        node.update({"value": None, "type": return_type, "context": None, "class_context": None})
                        file_data["variables"].append(node)

                else: # Reference
                    if sym not in symbol_def_table: continue
                    callee_info = symbol_def_table[sym]
                    r = list(occ.range)
                    ref_line_idx = r[0]
                    if len(r) == 4:
                        col_end = r[3]
                    elif len(r) == 3:
                        col_end = r[2]
                    else:
                        col_end = r[1] if len(r) > 1 else 0
                    src_line = source_lines[ref_line_idx] if ref_line_idx < len(source_lines) else ""
                    char_after = src_line[col_end:col_end + 1] if col_end < len(src_line) else ""

                    if char_after != "(": continue

                    caller_sym = self._find_enclosing_definition(line, definition_symbols_in_doc)
                    edge = {
                        "callee_symbol": sym, "callee_file": str((project_path / callee_info["file"]).resolve()),
                        "callee_line": callee_info["line"], "callee_name": self._name_from_symbol(sym),
                        "callee_kind": callee_info.get("kind", 0), "ref_line": line, "caller_file": abs_path,
                    }

                    if caller_sym:
                        caller_info = symbol_def_table.get(caller_sym, {})
                        edge.update({"caller_symbol": caller_sym, "caller_line": caller_info.get("line", 0)})
                        file_data["function_calls_scip"].append(edge)
                    else:
                        edge.update({"caller_symbol": None, "caller_line": 0})
                        file_data["module_level_calls_scip"].append(edge)

            files_data[abs_path] = file_data

        return {"files": files_data, "symbol_table": symbol_def_table}

    def _name_from_symbol(self, symbol: str) -> str:
        import re
        # scip-clang appends a hash in parentheses to disambiguate overloads / template args
        s = re.sub(r"\([0-9a-fA-F]{4,}\)\.?$", "", symbol)
        # Strip parameter descriptors: .($param), .($p1).($p2), etc.
        s = re.sub(r"\.\(\$?[^)]*\)", "", s)
        s = s.rstrip(".#")
        # Remove function/method call markers: ()
        s = re.sub(r"\(\)\.?$", "", s)
        parts = re.split(r"[/#]", s)
        name = parts[-1] if parts else symbol
        name = re.sub(r"^`([^`]+)`$", r"\1", name)
        # Handle space-separated package descriptors (PHP: "project 1.0.0 Animal")
        if " " in name:
            name = name.rsplit(" ", 1)[-1]
        return name

    def _infer_cxx_zero_kind(self, sym: str, line: int, source_lines: List[str]) -> int:
        """Infer SCIP SymbolKind when indexer reports 0 (scip-clang). Returns SCIP kind int."""
        import re

        if not sym.startswith("cxx "):
            return 0
        if sym.endswith("/"):
            return 0
        # Methods: Type#name(hash).
        if "#" in sym and "(" in sym and sym.rstrip(".").endswith(")"):
            return 26
        if sym.endswith("().") and "#" in sym:
            return 26
        if sym.endswith("()."):
            return 17
        # Free functions / operators with hash suffix: foo(deadbeef).
        if re.search(r"\([0-9a-fA-F]{4,}\)\.$", sym) and "#" not in sym:
            return 17
        if sym.endswith("#"):
            src_line = ""
            if 0 < line <= len(source_lines):
                src_line = source_lines[line - 1].strip().lower()
            if "enum " in src_line or src_line.startswith("enum"):
                return 18
            if src_line.startswith("union "):
                return 49
            if src_line.startswith("struct "):
                return 49
            if src_line.startswith("class "):
                return 7
            return 7
        return 0

    def _lang_from_path(self, rel_path: str) -> str:
        ext = Path(rel_path).suffix
        if ext in EXTENSION_TO_SCIP:
            return EXTENSION_TO_SCIP[ext][0]
        return "unknown"

    def _parse_signature(self, display_name: str, kind: int) -> Tuple[List[str], Optional[str]]:
        import re
        args: List[str] = []
        return_type: Optional[str] = None
        if not display_name: return args, return_type
        if "->" in display_name:
            parts = display_name.rsplit("->", 1)
            return_type = parts[1].strip().rstrip(":")
        param_match = re.search(r"\(([^)]*)\)", display_name)
        if param_match:
            for param in param_match.group(1).split(","):
                name = param.strip().split(":")[0].split("=")[0].strip().lstrip("*")
                if name: args.append(name)
        return args, return_type

    def _find_enclosing_definition(self, ref_line: int, definition_occurrences: list) -> Optional[str]:
        best_enclosing: Optional[str] = None
        best_enclosing_start = -1
        for occ in definition_occurrences:
            if occ.symbol.endswith("/"): continue
            er = list(getattr(occ, "enclosing_range", []))
            if not er: continue
            enc_start, enc_end = (er[0] + 1, er[2] + 1) if len(er) == 4 else (er[0] + 1, er[0] + 1)
            if enc_start <= ref_line <= enc_end and enc_start > best_enclosing_start:
                best_enclosing = occ.symbol
                best_enclosing_start = enc_start
        return best_enclosing
