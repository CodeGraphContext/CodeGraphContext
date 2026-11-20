# src/codegraphcontext/tools/indexing/resolution/python_import_targets.py
"""What a name bound by a Python import denotes.

Self-contained: it reads the parsed files of one link run and depends on the standard
library only. A class base or a metaclass is followed from the binding of its root to
the module's file, then to the definition, through package ``__init__`` re-exports,
module-level re-imports and ``*`` imports (up to MAX_REEXPORT_HOPS files). The answer
is a target:

* ``Found(path, name, label, line)`` — the one top-level definition it reaches;
* ``External(name)`` — the module is not in the repository (stdlib, a package);
* ``Unresolved(name)`` — an in-repository module that reaches no definition of the
  name (``may_export``: one that cannot be proven absent), or several definitions
  (``ambiguous``): never guessed;
* ``Module(...)`` — the name is a module;
* ``UNBOUND`` — no import binds it (a builtin or a global).

The bindings are derived from the parsed import records (``record_bindings``), scoped
by each record's ``context``; ``from m import *`` modules come from the parser's
``py_star_imports``.

``alias_prefixes`` (optional, none by default): import-system aliases
(``{"vendor.plugins.": ""}``: a spec ``vendor.plugins.x`` also names the directory
``x`` of an import root).
"""

from __future__ import annotations

import ast
import os
import posixpath
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


# ── paths ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _resolved_posix(path: str) -> str:
    """Memoized ``Path(path).resolve().as_posix()``.

    The CALLS pass resolves the same handful of paths hundreds of thousands of
    times; ``Path.resolve()`` hits the filesystem (``realpath``/``lstat``) on
    every call. The mapping from a path string to its resolved POSIX form is
    deterministic for the duration of an index run, so memoizing it is exact.
    ``build_function_call_groups`` clears this cache on entry to stay fresh
    across runs in long-lived processes.
    """
    return Path(path).resolve().as_posix()


def _repo_relative_posix(path: str, repo_root: Optional[str]) -> str:
    """*path* from the repository directory down (``<repo dir name>/<path in repo>``)."""
    if not repo_root:
        return path
    root = _resolved_posix(repo_root).rstrip("/")
    if not root or not path.startswith(root + "/"):
        return path
    parent = root.rsplit("/", 1)[0]
    return path[len(parent) + 1:] if parent else path.lstrip("/")


# ── Python modules ───────────────────────────────────────────────────────────

def _package_chain(root: str) -> List[str]:
    """The packages *root* sits in: the names of its parent directories, outermost
    first, while each holds an ``__init__.py`` (``["pkg"]`` for a repository at
    ``<pkg>/<repo>`` with ``<pkg>/__init__.py``); empty for a root whose parent is no
    package. The repository directory's own name is already part of every stem."""
    out: List[str] = []
    parent = posixpath.dirname(root.rstrip("/")) if root else ""
    while parent and parent != "/" and os.path.isfile(posixpath.join(parent, "__init__.py")):
        out.insert(0, posixpath.basename(parent))
        parent = posixpath.dirname(parent)
    return [c for c in out if c]


class PythonModules:
    """Which absolute Python module specs name a file (or package directory) of the
    repository: ``a.b`` names ``<root>/a/b.py``, ``<root>/a/b/__init__.py`` or the
    namespace package ``<root>/a/b/``, where an import root is the repository root or
    any directory that is no package. Stems start with the repository directory's name
    (a package indexed alone is ``<pkg>/…``); a repository nested in a package is also
    reached through it (``_package_chain``).

    *alias_prefixes*: import-system aliases — a spec starting with a key also names the
    module of the rest under the value's prefix (none by default)."""

    def __init__(self, all_file_data: List[Dict[str, Any]], alias_prefixes: Optional[Mapping[str, str]] = None):
        self.alias_prefixes: Dict[str, str] = dict(alias_prefixes or {})
        # every module stem and package directory, by its last component; and the
        # package directories (an __init__.py): an import root is never inside one
        stems: Set[str] = set()
        self._packages: Set[str] = set()
        # module stem -> the files implementing it (`<stem>.py`, `<stem>/__init__.py`)
        self._stem_files: Dict[str, List[str]] = defaultdict(list)
        per_root: Dict[str, List[List[str]]] = defaultdict(list)
        for fd in all_file_data:
            path = _resolved_posix(fd.get("path") or "")
            if not path.endswith((".py", ".pyi")):
                continue
            root = _resolved_posix(fd.get("repo_path") or "")
            rel = _repo_relative_posix(path, root) if root else path.lstrip("/")
            parts = [p for p in rel.rsplit(".", 1)[0].split("/") if p]
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
                self._packages.add("/".join(parts))
            for end in range(1, len(parts) + 1):
                stems.add("/".join(parts[:end]))
            per_root[root].append(parts)
            self._stem_files["/".join(parts)].append(path)
        for root, all_parts in per_root.items():
            # a repository nested in a PACKAGE is imported through that package too:
            # `pkg.repo.util` for <pkg>/<repo>/util.py
            chain = _package_chain(root)
            if not chain:
                continue
            for end in range(1, len(chain) + 1):
                stems.add("/".join(chain[:end]))
                self._packages.add("/".join(chain[:end]))
            for parts in all_parts:
                full = chain + parts
                if parts and "/".join(parts) in self._packages:
                    self._packages.add("/".join(full))
                for end in range(len(chain) + 1, len(full) + 1):
                    stems.add("/".join(full[:end]))
                self._stem_files["/".join(full)] = self._stem_files["/".join(parts)]
        self._by_last: Dict[str, List[str]] = defaultdict(list)
        for stem in stems:
            self._by_last[stem.rsplit("/", 1)[-1]].append(stem)
        self._cache: Dict[str, bool] = {}

    def _below_root(self, stem: str, path: str) -> bool:
        """*stem* is *path* strictly below an import root (a directory that is no package)."""
        return stem.endswith("/" + path) and stem[: -len(path) - 1] not in self._packages

    def _names(self, path: str) -> bool:
        """Some stem is *path* below an import root: the repository root, or a directory
        that is no package (``pkg/tools/json.py`` is ``pkg.tools.json``, never the
        stdlib ``json``)."""
        stems = self._by_last.get(path.rsplit("/", 1)[-1], ())
        return any(stem == path or self._below_root(stem, path) for stem in stems)

    def files(self, module: str) -> Tuple[str, ...]:
        """The repository files an ABSOLUTE module spec names (``a.b`` -> every
        ``<import root>/a/b.py`` / ``<import root>/a/b/__init__.py``); several when
        several import roots hold one. Below an import root first: a spec whose first
        segment is the repository directory's own name (``proj.x`` for ``<proj>/x.py``)
        names a file only when no import root holds the module — so a repository
        checked out as ``…/pkg`` resolves ``pkg.utils`` to ``<repo>/pkg/utils.py`` as
        one checked out as ``…/proj`` does. No alias prefix is applied here."""
        path = module.replace(".", "/")
        stems = self._by_last.get(path.rsplit("/", 1)[-1], ())
        below = {f for stem in stems if self._below_root(stem, path) for f in self._stem_files.get(stem, ())}
        if below:
            return tuple(sorted(below))
        return tuple(sorted({f for stem in stems if stem == path for f in self._stem_files.get(stem, ())}))

    def in_repo(self, module: Optional[str]) -> bool:
        """*module* (``a.b.c``) names a repository module; a relative spec always does
        (it is resolved against the importer), an unknown one (None) is assumed to."""
        if module is None or module.startswith("."):
            return True
        got = self._cache.get(module)
        if got is None:
            path = module.replace(".", "/")
            got = self._names(path) or any(
                module.startswith(prefix) and len(module) > len(prefix)
                and self._names((repl + module[len(prefix):]).replace(".", "/"))
                for prefix, repl in self.alias_prefixes.items())
            self._cache[module] = got
        return got


def _python_module_stem(module: str, importer: str) -> Optional[Tuple[bool, str]]:
    """``(absolute?, stem)`` a Python module spec names: a relative ``..pkg.mod`` from
    *importer* -> (True, ``/abs/dir/pkg/mod``); an absolute ``a.b.c`` -> (False,
    ``a/b/c``), matched as a path suffix below the repository."""
    if not module:
        return None
    dots = len(module) - len(module.lstrip("."))
    rest = module[dots:].replace(".", "/")
    if dots:
        base = posixpath.dirname(_resolved_posix(importer))
        for _ in range(dots - 1):
            base = posixpath.dirname(base)
        return True, (base + "/" + rest) if rest else base
    return False, rest


# ── import bindings ──────────────────────────────────────────────────────────

#: ``(local, module, imported name or None, scope start, scope end)``; start / end None
#: for a module-level import.
Binding = Tuple[str, Optional[str], Optional[str], Optional[int], Optional[int]]


def bindings_at(bindings: Iterable[tuple], name: str, line: Optional[int]) -> list:
    """The import bindings *name* denotes at *line*: those of the innermost enclosing
    function that imports it, else the module's (empty when no import binds it there)."""
    hits = [b for b in bindings if b[0] == name]
    if not hits:
        return []
    if line is not None:
        scoped = [b for b in hits if b[3] is not None and b[4] is not None and b[3] <= line <= b[4]]
        if scoped:
            inner = min(b[4] - b[3] for b in scoped)
            return [b for b in scoped if b[4] - b[3] == inner]
    return [b for b in hits if b[3] is None]


def _record_scope(record: Dict[str, Any],
                  spans: Dict[str, List[Tuple[int, int]]]) -> Optional[Tuple[Optional[int], Optional[int]]]:
    """The scope an import record binds its name in: ``(None, None)`` at module level,
    the enclosing function's lines, or None — a class-body import (a class attribute:
    no name of the module or of a function) or a function this parse has no span of."""
    ctx = record.get("context")
    kind = ctx[1] if isinstance(ctx, (list, tuple)) and len(ctx) > 1 else None
    if kind is None:
        return None, None
    if kind != "function_definition" and kind != "lambda":
        return None
    line = record.get("line_number")
    cands = [(s, e) for s, e in spans.get(ctx[0], ()) if isinstance(line, int) and s <= line <= e]
    return min(cands, key=lambda se: se[1] - se[0]) if cands else None


def record_bindings(file_data: Dict[str, Any]) -> List[Binding]:
    """The import bindings of a file, derived from its import records:
    ``from M import n as a`` -> ``a ↦ (M, n)``; ``import a.b`` -> ``a ↦ (a,
    None)``; ``import a.b as m`` -> ``m ↦ (a.b, None)`` — scoped by the record's
    ``context`` (a function's import binds in that function; a class-body import binds
    no name). Records keep one import per module and file, so an import repeated in a
    second function is seen in the first only."""
    spans: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for fn in file_data.get("functions") or ():
        s, e = fn.get("line_number"), fn.get("end_line")
        if fn.get("name") and not fn.get("is_synthetic") and isinstance(s, int) and isinstance(e, int):
            spans[fn["name"]].append((s, e))
    out: List[Binding] = []
    for imp in file_data.get("imports") or ():
        name = imp.get("name")
        if not name:
            continue
        scope = _record_scope(imp, spans)
        if scope is None:
            continue
        source = imp.get("source")
        if source is not None:
            out.append((imp.get("alias") or name, source, imp.get("imported_name") or name) + scope)
        elif imp.get("alias"):
            out.append((imp["alias"], name, None) + scope)
        else:
            root = name.split(".")[0]
            out.append((root, root, None) + scope)
    return out


# ── targets ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Found:
    """The import names the top-level definition *name* of *path*. *label* / *line*:
    the node label and line of that definition — its one ``class`` / ``def`` statement,
    else its LAST top-level assignment (the binding an importer sees once the module has
    run); None when unknown (a JS target). *lines*: ``((label, line), …)`` — the last
    top-level definition line per node label of the name there."""
    path: str
    name: str
    label: Optional[str] = None
    line: Optional[int] = None
    lines: Tuple[Tuple[str, int], ...] = ()

    def line_of(self, label: Optional[str]) -> Optional[int]:
        """The line of the top-level definition of kind *label* (None: unknown)."""
        if label is not None and label == self.label:
            return self.line
        return dict(self.lines).get(label) if label is not None else None


@dataclass(frozen=True)
class External:
    """The import names a module no file of the repository implements; *name* is the
    name imported there (``Component as C`` -> ``Component``)."""
    name: str


@dataclass(frozen=True)
class Unresolved:
    """An in-repository module that defines / re-exports no such name (*may_export*: it
    cannot be proven absent — a ``*`` import of a module this run cannot read, a module
    ``__getattr__``, an ``__all__`` entry without a definition, a namespace package), or
    several candidates (*ambiguous*: two top-level definitions, two import roots, two
    ``*`` modules): never guessed. *candidates*: then the file of each definition."""
    name: str
    may_export: bool = False
    ambiguous: bool = False
    candidates: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Module:
    """The name is a module, not a symbol. *key*: ``("spec", "a.b")`` for an absolute
    spec, ``("dir", "/abs/a/b")`` for one resolved against its importer; *files*: the
    module's files (none for a namespace package)."""
    key: Tuple[str, str]
    files: Tuple[str, ...]


class _Unbound:
    """No import binds the name (a builtin, a global, a typo)."""

    def __repr__(self) -> str:
        return "UNBOUND"


UNBOUND = _Unbound()

#: Re-exports followed (``pkg/__init__.py`` -> ``pkg/base.py`` -> …).
MAX_REEXPORT_HOPS = 3

#: Top-level Python definitions an import can name, by parsed-record key.
_PY_DEF_KEYS = (("classes", "Class"), ("functions", "Function"), ("variables", "Variable"))


def _join_module(module: str, name: str) -> str:
    """``from <module> import <name>`` as the submodule spec ``<module>.<name>``."""
    return f"{module}{name}" if module.endswith(".") else f"{module}.{name}"


def _prefer_py(files: Iterable[str]) -> Tuple[str, ...]:
    """Sorted, with a ``.pyi`` stub dropped where its ``.py`` module is there too."""
    got = set(files)
    return tuple(sorted(f for f in got if not (f.endswith(".pyi") and f[:-1] in got)))


def _literal_names(value: Any) -> Optional[FrozenSet[str]]:
    """The names of a literal ``__all__`` value (``['A', 'B']``), else None."""
    if not isinstance(value, str):
        return None
    try:
        got = ast.literal_eval(value)
    except (ValueError, SyntaxError, MemoryError, RecursionError, TypeError):
        return None
    if isinstance(got, (list, tuple)) and all(isinstance(n, str) for n in got):
        return frozenset(got)
    return None


def _candidates(hits: Iterable[Any]) -> Tuple[str, ...]:
    """The files of several targets (a module: its first file), sorted."""
    return tuple(sorted(h.path if isinstance(h, Found) else (h.files[0] if h.files else h.key[1]) for h in hits))


def definition_target(path: str, name: str, defs: Sequence[Tuple[str, Optional[int]]]) -> Any:
    """The target of a name *path* defines at one scope (*defs*: ``[(label, line)]``):
    its one ``class`` / ``def`` statement — several are ambiguous (a conditional
    definition is never guessed) — unless a later assignment replaces that binding,
    in which case use its last assignment (a Variable)."""
    statements = [(label, line) for label, line in defs if label != "Variable"]
    if len(statements) > 1:
        return Unresolved(name, ambiguous=True, candidates=(path,) * len(statements))
    last: Dict[str, int] = {}
    for label, line in defs:
        if line is not None:
            last[label] = max(last.get(label, line), line)
    lines = tuple(sorted(last.items()))
    if statements:
        label, line = statements[0]
        # A later assignment replaces the class/function binding exposed to
        # importers. Match its Variable occurrence rather than the stale class.
        variable_line = last.get("Variable")
        if variable_line is not None and line is not None and variable_line > line:
            return Found(path, name, "Variable", variable_line, lines)
        return Found(path, name, label, line, lines)
    return Found(path, name, "Variable", last.get("Variable"), lines)


@dataclass
class _Surface:
    """What a Python module's top level makes importable from it."""
    defs: Dict[str, List[Tuple[str, Optional[int]]]]               # name -> [(label, line)] definitions
    imports: Dict[str, List[Tuple[Optional[str], Optional[str]]]]  # name -> [(module, imported)]
    stars: Tuple[str, ...]                                         # `from m import *` modules
    exports: Optional[FrozenSet[str]]                              # a literal `__all__` (None: none)
    open_names: FrozenSet[str]                                     # `__all__` names (maybe no definition)
    dynamic: bool                                                  # a module `__getattr__` (PEP 562)


class PythonImportTargets:
    """What a name bound by a Python import denotes, for one link run.

    Built from the run's parsed files alone: their paths and repository roots, import
    records, ``py_star_imports`` and top-level classes / functions / variables. Results
    are cached per (file, name); surfaces are built once per file.
    """

    def __init__(self, all_file_data: List[Dict[str, Any]], modules: Optional[PythonModules] = None, *,
                 alias_prefixes: Optional[Mapping[str, str]] = None):
        self.modules = modules if modules is not None else PythonModules(all_file_data, alias_prefixes)
        self._fd: Dict[str, Dict[str, Any]] = {}
        # every directory holding a Python file (a namespace package has no file)
        self._dirs: Set[str] = set()
        for fd in all_file_data:
            path = _resolved_posix(fd.get("path") or "")
            if path.endswith((".py", ".pyi")):
                self._fd[path] = fd
                d = posixpath.dirname(path)
                while d and d not in self._dirs and d != "/":
                    self._dirs.add(d)
                    d = posixpath.dirname(d)
        self._surfaces: Dict[str, _Surface] = {}
        self._follow_cache: Dict[Tuple[str, str, int], Any] = {}
        self._module_cache: Dict[Tuple[str, str], Any] = {}
        self._bindings_cache: Dict[str, list] = {}

    # ── bindings ──
    def bindings(self, file_data: Dict[str, Any], name: str,
                 line: Optional[int]) -> List[Tuple[Optional[str], Optional[str]]]:
        """``[(module, imported name or None)]`` of the imports binding *name* at *line*
        of the file: the innermost enclosing function's, else the module's."""
        return [(b[1], b[2]) for b in bindings_at(self._file_bindings(file_data), name, line)]

    def _file_bindings(self, file_data: Dict[str, Any]) -> List[Binding]:
        path = _resolved_posix(file_data.get("path") or "")
        got = self._bindings_cache.get(path)
        if got is None:
            got = self._bindings_cache[path] = record_bindings(file_data)
        return got

    # ── modules ──
    def _alias_files(self, spec: str) -> List[str]:
        files = list(self.modules.files(spec))
        for prefix, repl in self.modules.alias_prefixes.items():
            if spec.startswith(prefix) and len(spec) > len(prefix):
                files += self.modules.files(repl + spec[len(prefix):])
        return files

    def _spec_module(self, spec: str, importer: str) -> Any:
        """The module *spec* names from *importer* (Module or External); cached per spec
        (a relative one per importing directory)."""
        key = (spec, posixpath.dirname(importer) if spec.startswith(".") else "")
        got = self._module_cache.get(key)
        if got is None:
            got = self._module_cache[key] = self._spec_module_uncached(spec, importer)
        return got

    def _spec_module_uncached(self, spec: str, importer: str) -> Any:
        if spec.startswith("."):
            want = _python_module_stem(spec, importer)
            return self._dir_module(want[1]) if want else Unresolved(spec)
        files = _prefer_py(self._alias_files(spec))
        if files or self.modules.in_repo(spec):
            return Module(("spec", spec), files)
        return External(spec.rsplit(".", 1)[-1])

    def _dir_module(self, stem: str) -> Module:
        cands = [stem + ".py", stem + "/__init__.py", stem + ".pyi", stem + "/__init__.pyi"]
        return Module(("dir", stem), _prefer_py(c for c in cands if c in self._fd))

    def _is_module(self, module: Any) -> bool:
        """A module of the repository: one with files, or a namespace package (a
        directory of Python files without ``__init__.py``)."""
        if not isinstance(module, Module):
            return False
        if module.files:
            return True
        kind, key = module.key
        return key in self._dirs if kind == "dir" else self.modules.in_repo(key)

    def _submodule(self, module: Module, name: str, importer: str) -> Optional[Module]:
        """``module.name`` when that is a module of the repository (a namespace package
        too), else None."""
        kind, key = module.key
        if kind == "spec":
            sub = self._spec_module(_join_module(key, name), importer)
        else:
            sub = self._dir_module(key + "/" + name)
        return sub if self._is_module(sub) else None

    # ── surfaces ──
    def surface(self, path: str) -> _Surface:
        got = self._surfaces.get(path)
        if got is None:
            got = self._surfaces[path] = self._surface_uncached(path)
        return got

    def _surface_uncached(self, path: str) -> _Surface:
        fd = self._fd.get(path) or {}
        defs: Dict[str, List[Tuple[str, Optional[int]]]] = {}
        exports: Optional[FrozenSet[str]] = None
        all_values = []
        for key, label in _PY_DEF_KEYS:
            for item in fd.get(key) or ():
                name = item.get("name")
                if (not name or item.get("context") or item.get("class_context")
                        or item.get("is_synthetic") or name == "<module>"):
                    continue
                line = item.get("line_number")
                defs.setdefault(name, []).append((label, line if isinstance(line, int) else None))
                if name == "__all__" and label == "Variable":
                    all_values.append(item.get("value"))
        if len(all_values) == 1:
            exports = _literal_names(all_values[0])
        imports: Dict[str, List[Tuple[Optional[str], Optional[str]]]] = {}
        for local, module, imported, start, _end in self._file_bindings(fd):
            if start is None:
                imports.setdefault(local, []).append((module, imported))
        open_names = frozenset(exports or ())
        dynamic = any(label == "Function" for label, _l in defs.get("__getattr__", ()))
        return _Surface(defs, imports, tuple(fd.get("py_star_imports") or ()), exports,
                        open_names, dynamic)

    # ── resolution ──
    def resolve(self, file_data: Dict[str, Any], dotted: str, line: Optional[int] = None) -> Any:
        """The target of the (dotted) name *dotted* used at *line* of the file: its root
        is looked up in the file's import bindings; UNBOUND when none binds it."""
        parts = [p for p in dotted.split(".") if p]
        if not parts:
            return UNBOUND
        binds = self.bindings(file_data, parts[0], line)
        if not binds:
            return UNBOUND
        importer = _resolved_posix(file_data.get("path") or "")
        results = {self._binding_target(importer, module, imported, parts, 0) for module, imported in binds}
        if len(results) == 1:
            return next(iter(results))
        display = parts[-1] if len(parts) > 1 else (binds[0][1] or parts[0])
        if all(isinstance(r, External) for r in results):
            return External(display)
        # bindings that disagree (try / except ImportError): the one that runs decides
        return Unresolved(display, may_export=True)

    def resolve_unbound(self, file_data: Dict[str, Any], name: str) -> Any:
        """A name no import binds: what the file's ``*`` imports supply, else UNBOUND (a
        builtin or global — never a same-named definition found elsewhere)."""
        importer = _resolved_posix(file_data.get("path") or "")
        stars = tuple(file_data.get("py_star_imports") or ())
        if not stars:
            return UNBOUND
        got = self._through_stars(importer, stars, name, 0)
        return UNBOUND if isinstance(got, Unresolved) and not got.may_export else got

    def _binding_target(self, importer: str, module: Optional[str], imported: Optional[str],
                        parts: List[str], hops: int) -> Any:
        display = parts[-1] if len(parts) > 1 else (imported or parts[0])
        if not module:
            return Unresolved(display)
        if imported is None:
            obj = self._spec_module(module, importer)
        else:
            sub = self._spec_module(_join_module(module, imported), importer)
            if self._is_module(sub):
                obj = sub
            else:
                base = self._spec_module(module, importer)
                if isinstance(base, External):
                    return External(display if len(parts) > 1 else imported)
                obj = self._member(base, imported, importer, hops)
        return self._walk(obj, parts[1:], importer, hops, display)

    def _walk(self, obj: Any, rest: List[str], importer: str, hops: int, display: str) -> Any:
        for seg in rest:
            if isinstance(obj, External):
                return External(display)
            if not isinstance(obj, Module):
                return Unresolved(display)          # a member of a class / value: chained
            sub = self._submodule(obj, seg, importer)
            obj = sub if sub is not None else self._member(obj, seg, importer, hops)
        if isinstance(obj, Unresolved) and obj.name != display:
            return Unresolved(display, obj.may_export, obj.ambiguous, obj.candidates)
        return obj

    def _member(self, module: Module, name: str, importer: str, hops: int) -> Any:
        """What *name* is in *module* (any of its files: exactly one answer wins). A
        namespace package (a directory without ``__init__.py``) has no file that could
        define the name: its attributes come from submodules or are set at run time, so
        a name it lacks is never provably absent (``may_export``)."""
        if not module.files:
            return Unresolved(name, True)
        results = {self._follow(f, name, hops) for f in module.files}
        hits = {r for r in results if isinstance(r, (Found, Module))}
        if len(hits) == 1:
            return next(iter(hits))
        unresolved = [r for r in results if isinstance(r, Unresolved)]
        may_export = any(r.may_export for r in unresolved)
        if len(hits) > 1:
            return Unresolved(name, may_export, True, _candidates(hits))
        if results and all(isinstance(r, External) for r in results):
            return next(iter(results)) if len(results) == 1 else Unresolved(name)
        ambiguous = [r for r in unresolved if r.ambiguous]
        return Unresolved(name, may_export, bool(ambiguous), tuple(c for r in ambiguous for c in r.candidates))

    def _follow(self, path: str, name: str, hops: int) -> Any:
        key = (path, name, hops)
        if key not in self._follow_cache:
            self._follow_cache[key] = None          # a cycle reads as Unresolved
            self._follow_cache[key] = self._follow_uncached(path, name, hops)
        got = self._follow_cache[key]
        return Unresolved(name) if got is None else got

    def _follow_uncached(self, path: str, name: str, hops: int) -> Any:
        surface = self.surface(path)
        defs = surface.defs.get(name)
        if defs:
            return definition_target(path, name, defs)
        if hops >= MAX_REEXPORT_HOPS:
            return Unresolved(name)
        binds = surface.imports.get(name)
        if binds:
            results = {self._binding_target(path, module, imported, [name], hops + 1)
                       for module, imported in binds}
            if len(results) == 1:
                return next(iter(results))
            # re-imports that disagree (try / except ImportError): the one that runs decides
            return Unresolved(name, may_export=True)
        if surface.stars:
            got = self._through_stars(path, surface.stars, name, hops + 1)
            if not (isinstance(got, Unresolved) and not got.may_export and not got.ambiguous):
                return got
        # a module `__getattr__`, a name `__all__` lists: the name may exist at run time
        # without a definition this parse records
        if surface.dynamic or name in surface.open_names:
            return Unresolved(name, may_export=True)
        return Unresolved(name)

    def _star_exports(self, module: Module, name: str) -> bool:
        """``from module import *`` binds *name*: the module's literal ``__all__`` lists
        it, or — none — the name does not start with ``_``. A namespace package: unknown."""
        if not module.files:
            return True
        for f in module.files:
            exports = self.surface(f).exports
            if exports is not None:
                if name in exports:
                    return True
            elif not name.startswith("_"):
                return True
        return False

    def _through_stars(self, path: str, stars: Sequence[str], name: str, hops: int) -> Any:
        """*name* as the ``*`` imports of *path* supply it: one Found wins; a module
        outside the repository may supply it too (``may_export``), which makes it
        Unresolved; several Founds are ambiguous."""
        hits, may_export = set(), False
        for spec in stars:
            mod = self._spec_module(spec, path)
            if isinstance(mod, External):
                if not name.startswith("_"):
                    may_export = True
                continue
            if not isinstance(mod, Module) or not self._star_exports(mod, name):
                continue
            got = self._member(mod, name, path, hops)
            if isinstance(got, (Found, Module)):
                hits.add(got)
            elif isinstance(got, External) or (isinstance(got, Unresolved) and got.may_export):
                may_export = True
        if len(hits) == 1 and not may_export:
            return next(iter(hits))
        return Unresolved(name, may_export, len(hits) > 1, _candidates(hits) if len(hits) > 1 else ())
