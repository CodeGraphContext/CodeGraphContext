# src/codegraphcontext/tools/indexing/resolution/inheritance.py
"""Resolve class inheritance into INHERITS row payloads (no DB I/O for non-C# batch)."""

import re
from bisect import bisect_right
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .calls import import_path_in_candidate
from .python_import_targets import (
    UNBOUND,
    External,
    Found,
    PythonImportTargets,
    Unresolved,
    _resolved_posix,
    definition_target,
)


#: Languages whose class bases resolve through the file's own imports
#: (resolution/python_import_targets.py). Every other language keeps the import-path
#: substring test of resolve_inheritance_link.
_PY_IMPORT_BOUND_LANGS = frozenset({"python"})


# Child construct list -> node label: the 8 kinds that can declare inheritance.
_INHERIT_KEY_TO_LABEL = {
    "classes": "Class",
    "structs": "Struct",
    "traits": "Trait",
    "interfaces": "Interface",
    "mixins": "Mixin",
    "enums": "Enum",
    "extensions": "Extension",
    "variables": "Variable",
}

# All construct lists whose nodes can be an INHERITS parent, mapped to their label.
# Matches the 12 labels the writer enumerates. Used to attach exact child/parent
# labels to rows and to detect the rare (name, path) collisions where more than one
# node kind shares a name+path — those stay ambiguous so the writer falls back to
# full enumeration (keeping the produced edge set identical).
_NODE_KEY_TO_LABEL = {
    "classes": "Class",
    "traits": "Trait",
    "interfaces": "Interface",
    "structs": "Struct",
    "enums": "Enum",
    "unions": "Union",
    "records": "Record",
    "mixins": "Mixin",
    "extensions": "Extension",
    "modules": "Module",
    "objects": "Object",
    "variables": "Variable",
}


def _build_node_label_index(
    all_file_data: List[Dict[str, Any]],
) -> Dict[str, Dict[str, set]]:
    """Map normalized path -> {name -> set(labels)} across all inheritance-eligible
    node kinds. A (path, name) with exactly one label lets the writer target that
    label directly; multiple labels leaves it ambiguous (writer enumerates)."""
    index: Dict[str, Dict[str, set]] = {}
    for file_data in all_file_data:
        fpath = str(Path(file_data["path"]).resolve().as_posix())
        per_file = index.setdefault(fpath, {})
        for key, label in _NODE_KEY_TO_LABEL.items():
            for item in file_data.get(key, []):
                name = item.get("name")
                if name:
                    per_file.setdefault(name, set()).add(label)
    return index


def resolve_inheritance_link(
    class_item: Dict[str, Any],
    base_class_str: str,
    caller_file_path: str,
    local_class_names: set,
    local_imports: dict,
    imports_map: dict,
    child_label: Optional[str] = None,
    node_label_index: Optional[Dict[str, Dict[str, set]]] = None,
    repo_root: Optional[str] = None,
    *,
    import_target: Optional[Callable[[str], Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a single inheritance link. Returns row dict or None.

    *repo_root*: see ``calls.import_path_in_candidate`` — import-path matching
    looks at candidate paths relative to the repository, not where it lives.

    *import_target* (Python): the base's target (``python_import_targets``: ``Found`` /
    ``External`` / ``Unresolved`` / ``Module`` / ``UNBOUND``) — the definition of the
    class's own file its scope sees, else what the file's imports name: the module's
    file, through re-exports, under the DECLARED name (``Base as DBBase`` -> ``Base``).
    A ``Found`` row carries the definition's line (``parent_line``: the writer pins the
    parent node by it). Anything the repository does not define, or defines several
    times, is an ExternalClass of the imported name: never a path substring, the first
    of several candidates, or a unique same-named class of the repository (a builtin
    ``Exception``). Without it (every other language) the import-path substring test
    decides.
    """
    import re
    if base_class_str == "object":
        return None

    if not base_class_str:
        return None

    # Unwrap JS/TS mixins like Swimmable(Flyable(Person)) -> Person
    m = re.search(r'([A-Za-z0-9_.]+)(?:\s*\))*$', base_class_str)
    if m:
        base_class_str = m.group(1)

    resolved_path = None
    target_class_name = base_class_str.split(".")[-1]
    found: Optional[Found] = None
    found_label: Optional[str] = None

    if import_target is not None:
        # the same-file rule is the target's too (scope-aware: build_inheritance_and_csharp_files)
        target = import_target(base_class_str)
        if isinstance(target, Found):
            labels = (node_label_index or {}).get(target.path, {}).get(target.name)
            if labels and target.label is not None and target.label not in labels:
                # the definition is no INHERITS parent (a function): a nested class or a
                # function-local variable of that name there is ANOTHER definition —
                # an ExternalClass of the name, never an edge onto the namesake
                target_class_name = target.name
            elif node_label_index is None or labels:
                resolved_path, target_class_name, found = target.path, target.name, target
                # several kinds may share the name in that file: the target names one
                # definition — its own kind
                found_label = target.label if labels and target.label in labels else None
            else:
                # a definition no INHERITS parent can be (a function): the writer would
                # match no node — an ExternalClass of that name, as for any other
                target_class_name = target.name
        elif isinstance(target, (External, Unresolved)):
            target_class_name = target.name
    elif "." in base_class_str:
        lookup_name = base_class_str.split(".")[0]
        if lookup_name in local_imports:
            full_import_name = local_imports[lookup_name]
            possible_paths = imports_map.get(target_class_name, [])
            for path in possible_paths:
                if import_path_in_candidate(full_import_name, path, repo_root):
                    resolved_path = path
                    break
    else:
        lookup_name = base_class_str
        if lookup_name in local_class_names:
            resolved_path = caller_file_path
        elif lookup_name in local_imports:
            full_import_name = local_imports[lookup_name]
            possible_paths = imports_map.get(target_class_name, [])
            for path in possible_paths:
                if import_path_in_candidate(full_import_name, path, repo_root):
                    resolved_path = path
                    break
        elif lookup_name in imports_map:
            possible_paths = imports_map[lookup_name]
            if len(possible_paths) == 1:
                resolved_path = possible_paths[0]

    # Pin the child label only when this (path, name) is a single node kind. If more
    # than one kind shares it, leave it off so the writer enumerates (byte-identical).
    child_lbl = None
    if child_label:
        if node_label_index is None:
            child_lbl = child_label
        else:
            present = node_label_index.get(caller_file_path, {}).get(class_item["name"])
            if present and len(present) == 1 and child_label in present:
                child_lbl = child_label

    def _with_labels(row: Dict[str, Any], parent_path: str) -> Dict[str, Any]:
        if child_lbl:
            row["child_label"] = child_lbl
        if node_label_index is not None:
            plabels = node_label_index.get(parent_path, {}).get(target_class_name)
            if plabels and len(plabels) == 1:
                row["parent_label"] = next(iter(plabels))
            elif found_label is not None:
                # several kinds share the name in that file: the target names one
                # definition, of this kind
                row["parent_label"] = found_label
            line = found.line_of(row.get("parent_label")) if found is not None else None
            if line is not None:
                # the writer matches a parent by (name, path): a nested class, a
                # function-local variable or a second definition of that name in the
                # file would receive the edge too — pin the definition's line
                row["parent_line"] = line
        return row

    if resolved_path:
        return _with_labels({
            "child_name": class_item["name"],
            "path": caller_file_path,
            "parent_name": target_class_name,
            "resolved_parent_file_path": resolved_path,
            "confidence_label": "EXTRACTED",
        }, resolved_path)
    return _with_labels({
        "child_name": class_item["name"],
        "path": caller_file_path,
        "parent_name": target_class_name,
        "resolved_parent_file_path": "__external__",
        "confidence_label": "INFERRED",
    }, "__external__")


def python_base_target(targets: PythonImportTargets, file_data: Dict[str, Any], base: str,
                       line: Optional[int]) -> Any:
    """What a Python base (or metaclass) expression names through the file's imports: the
    binding of its root, else — a bare name no import binds — what the file's ``*``
    imports supply (UNBOUND: a builtin / global)."""
    got = targets.resolve(file_data, base, line)
    if got is UNBOUND and "." not in base:
        got = targets.resolve_unbound(file_data, base)
    return got


class _Span(tuple):
    """``(start, end, kind, name)`` of a function or class body: a scope."""
    __slots__ = ()

    @property
    def kind(self) -> str:
        return self[2]


#: A definition whose scope this parse cannot place (visible from nowhere).
_NOWHERE = _Span((0, -1, "none", ""))


class _SpanTree:
    """A file's scope spans by their lines: the spans holding a line, innermost first,
    in O(log n + depth) — spans nest (a parent holds its children's start)."""

    def __init__(self, spans: List[_Span]):
        self.spans = sorted(spans, key=lambda sp: (sp[0], -sp[1]))
        self.starts = [sp[0] for sp in self.spans]
        self.parent: List[int] = []
        stack: List[int] = []
        for i, sp in enumerate(self.spans):
            while stack and self.spans[stack[-1]][1] < sp[0]:
                stack.pop()
            self.parent.append(stack[-1] if stack else -1)
            stack.append(i)

    def holding(self, line: int) -> List[_Span]:
        i = bisect_right(self.starts, line) - 1
        out: List[_Span] = []
        while i >= 0:
            if self.spans[i][1] >= line:
                out.append(self.spans[i])
            i = self.parent[i]
        return out


class _FileScopes:
    """Where the definitions of one Python file bind their names, for the same-file rule
    of INHERITS (scope-aware): a base names a definition of the class's own file only
    when Python scoping makes it visible at the class statement —

    * a definition of the module, or of the scope the class statement sits in, that
      PRECEDES the class statement (the base is evaluated when the class statement runs:
      ``class Foo(Foo)`` names an earlier ``Foo``, never itself); a class nested in
      class bodies only runs with the OUTERMOST class statement, so a module definition
      must precede that one;
    * any definition of an enclosing FUNCTION, and of the module when the class sits in
      a function (closures; a class body is no enclosing scope of what it contains);

    never a function-local namesake of another function, a nested class of another
    class, a definition after a module-level class. The innermost scope wins; there,
    several ``class`` statements are ambiguous (``definition_target``).

    Records carry their enclosing scope (``context``); functions and class bodies are
    placed by their lines."""

    def __init__(self, file_data: Dict[str, Any]):
        self._fd = file_data
        self._tree: Optional[_SpanTree] = None          # built on first use
        self._own_methods: Dict[Tuple[str, int], Set[_Span]] = {}
        self._class_spans: Dict[Tuple[int, str], Set[_Span]] = {}
        # the file's INHERITS-able definitions by name, indexed on the first lookup;
        # each name's scopes are placed on its first lookup (most names are never a base)
        self._items: Optional[Dict[str, List[Tuple[Dict[str, Any], str]]]] = None
        self._defs: Dict[str, List[Tuple[str, int, Any]]] = {}

    def _spans(self) -> _SpanTree:
        """The function and class body spans of the file, by line."""
        if self._tree is None:
            spans: List[_Span] = []
            for fn in self._fd.get("functions") or ():
                s, e = fn.get("line_number"), fn.get("end_line")
                if not fn.get("name") or fn.get("is_synthetic") or not isinstance(s, int) or not isinstance(e, int):
                    continue
                span = _Span((s, e, "function", fn["name"]))
                spans.append(span)
                if fn.get("class_context") and isinstance(fn.get("class_context_line"), int):
                    self._own_methods.setdefault((fn["class_context"], fn["class_context_line"]), set()).add(span)
            for cls in self._fd.get("classes") or ():
                s, e = cls.get("line_number"), cls.get("end_line")
                if cls.get("name") and isinstance(s, int) and isinstance(e, int):
                    span = _Span((s, e, "class", cls["name"]))
                    spans.append(span)
                    self._class_spans.setdefault((s, cls["name"]), set()).add(span)
            self._tree = _SpanTree(spans)
        return self._tree

    def defs_of(self, name: str) -> List[Tuple[str, int, Any]]:
        """``[(label, line, scope)]`` of the file's definitions of *name*."""
        got = self._defs.get(name)
        if got is None:
            got = self._defs[name] = [(label, item["line_number"], self.scope_of(item, label))
                                      for item, label in self._items_of(name)]
        return got

    def _items_of(self, name: str) -> List[Tuple[Dict[str, Any], str]]:
        """The file's definitions of *name*: ``(record, label)``."""
        if self._items is None:
            items: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
            for key, label in _INHERIT_KEY_TO_LABEL.items():
                for item in self._fd.get(key) or ():
                    nm = item.get("name")
                    if nm and isinstance(item.get("line_number"), int):
                        items.setdefault(nm, []).append((item, label))
            self._items = items
        return self._items.get(name, [])

    def _enclosing(self, line: int, own: Set[_Span]) -> List[_Span]:
        """The spans holding *line*, innermost first, except *own*."""
        return [sp for sp in self._spans().holding(line) if sp not in own]

    def _own(self, item: Dict[str, Any], label: str) -> Set[_Span]:
        self._spans()
        line = item.get("line_number")
        own = set(self._class_spans.get((line, item.get("name")), ())) if label != "Variable" else set()
        return own | self._own_methods.get((item.get("name"), line), set())

    def scope_of(self, item: Dict[str, Any], label: str) -> Any:
        """The scope *item* binds its name in: None (the module), a span, or _NOWHERE."""
        if not item.get("context") and not item.get("class_context"):
            return None
        chain = self._enclosing(item.get("line_number"), self._own(item, label))
        return chain[0] if chain else _NOWHERE

    def chain(self, item: Dict[str, Any], label: str) -> List[_Span]:
        """The scopes enclosing the class statement *item*, innermost first."""
        if self.scope_of(item, label) is None:
            return []
        return self._enclosing(item.get("line_number"), self._own(item, label))

    def target(self, path: str, name: str, item: Dict[str, Any], label: str) -> Any:
        """The definition of *name* the class statement *item* sees in its own file
        (``Found`` / ambiguous ``Unresolved``), else None."""
        defs = self.defs_of(name)
        if not defs:
            return None
        line = item.get("line_number")
        chain = self.chain(item, label)
        # a class nested in class bodies only is created with its outermost class
        closure = any(sp.kind == "function" for sp in chain)
        best: Optional[int] = None
        seen: List[Tuple[str, Optional[int]]] = []
        for dlabel, dline, scope in defs:
            if scope is _NOWHERE:
                continue
            if dlabel == label and name == item.get("name") and dline == line:
                continue                        # the class statement itself
            if scope is None:
                rank = len(chain)
                ok = closure or (dline < chain[-1][0] if chain else dline < line)
            elif scope in chain:
                rank = chain.index(scope)
                ok = dline < line if rank == 0 else scope.kind == "function"
            else:
                ok = False
            if not ok:
                continue
            if best is None or rank < best:
                best, seen = rank, []
            if rank == best:
                seen.append((dlabel, dline))
        if not seen:
            return None
        return definition_target(path, name, seen)


def build_inheritance_and_csharp_files(
    all_file_data: List[Dict[str, Any]], imports_map: dict
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (inheritance_batch_rows, csharp_file_data_list).

    Python bases resolve through the file's own scopes (``_FileScopes``), then its
    imports (``python_import_targets``; the resolver is built once per call, over every
    file of *all_file_data*); every other language through
    ``resolve_inheritance_link``'s import-path test."""
    inheritance_batch: List[Dict[str, Any]] = []
    csharp_files: List[Dict[str, Any]] = []
    node_label_index = _build_node_label_index(all_file_data)
    py_targets: Optional[PythonImportTargets] = None

    for file_data in all_file_data:
        if file_data.get("lang") == "c_sharp":
            csharp_files.append(file_data)
            continue

        caller_file_path = _resolved_posix(file_data["path"])
        local_class_names = set()
        local_imports: dict = {}
        target_of: Optional[Callable[[str, Dict[str, Any], str], Any]] = None
        if (file_data.get("lang") or "").lower() in _PY_IMPORT_BOUND_LANGS:
            if py_targets is None:
                py_targets = PythonImportTargets(all_file_data)
            scopes = _FileScopes(file_data)

            def target_of(base, item, label, _t=py_targets, _fd=file_data, _path=caller_file_path,
                          _scopes=scopes):
                local = _scopes.target(_path, base, item, label) if "." not in base else None
                return local if local is not None else python_base_target(_t, _fd, base, item.get("line_number"))
        else:
            for key in _INHERIT_KEY_TO_LABEL:
                for item in file_data.get(key, []):
                    local_class_names.add(item["name"])

            local_imports = {
                imp.get("alias") or (imp.get("name") or "").split(".")[-1]: imp.get("name")
                for imp in file_data.get("imports", [])
                if imp.get("name")
            }

        for key, child_label in _INHERIT_KEY_TO_LABEL.items():
            for class_item in file_data.get(key, []):
                if not class_item.get("bases"):
                    continue
                for base_class_str in class_item["bases"]:
                    resolved = resolve_inheritance_link(
                        class_item,
                        base_class_str,
                        caller_file_path,
                        local_class_names,
                        local_imports,
                        imports_map,
                        child_label=child_label,
                        node_label_index=node_label_index,
                        repo_root=file_data.get("repo_path"),
                        import_target=None if target_of is None else (
                            lambda base, _item=class_item, _label=child_label: target_of(base, _item, _label)),
                    )
                    if resolved:
                        inheritance_batch.append(resolved)

    return inheritance_batch, csharp_files


def _expand_go_interface_methods(
    iface_name: str,
    interface_methods: Dict[str, set],
    embedded_bases: Dict[str, List[str]],
    cache: Dict[str, set],
) -> set:
    if iface_name in cache:
        return cache[iface_name]
    required = set(interface_methods.get(iface_name, set()))
    for base in embedded_bases.get(iface_name, []):
        required |= _expand_go_interface_methods(
            base, interface_methods, embedded_bases, cache
        )
    cache[iface_name] = required
    return required


def build_go_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Infer Go struct->interface IMPLEMENTS edges from method sets."""
    implements_batch: List[Dict[str, Any]] = []

    for file_data in all_file_data:
        if file_data.get("lang") != "go":
            continue

        file_path = str(Path(file_data["path"]).resolve().as_posix())
        struct_methods: Dict[str, set] = {}
        for func in file_data.get("functions", []):
            receiver_type = func.get("receiver_type") or func.get("class_context")
            if not receiver_type:
                continue
            struct_methods.setdefault(receiver_type, set()).add(func["name"])

        interface_methods: Dict[str, set] = {}
        embedded_bases: Dict[str, List[str]] = {}
        for iface in file_data.get("interfaces", []):
            iface_name = iface.get("name")
            if not iface_name:
                continue
            methods = iface.get("methods") or []
            interface_methods[iface_name] = set(methods)
            embedded_bases[iface_name] = list(iface.get("bases") or [])

        expanded_required: Dict[str, set] = {}
        for iface_name in interface_methods:
            _expand_go_interface_methods(
                iface_name, interface_methods, embedded_bases, expanded_required
            )

        for struct in file_data.get("structs", []):
            struct_name = struct.get("name")
            if not struct_name:
                continue
            available = struct_methods.get(struct_name, set())
            for iface_name, required in expanded_required.items():
                if not required or not required.issubset(available):
                    continue
                implements_batch.append({
                    "child_name": struct_name,
                    "child_label": "Struct",
                    "parent_name": iface_name,
                    "parent_label": "Interface",
                    "path": file_path,
                    "resolved_parent_file_path": file_path,
                    "confidence_label": "INFERRED",
                })

    return implements_batch


def build_haskell_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create typeclass instance IMPLEMENTS edges (data type -> typeclass)."""
    implements_batch: List[Dict[str, Any]] = []

    for file_data in all_file_data:
        if file_data.get("lang") != "haskell":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        for instance in file_data.get("typeclass_instances", []):
            child_name = instance.get("implementing_type")
            parent_name = instance.get("typeclass")
            if not child_name or not parent_name:
                continue
            implements_batch.append({
                "child_name": child_name,
                "child_label": "Class",
                "parent_name": parent_name,
                "parent_label": "Class",
                "path": file_path,
                "resolved_parent_file_path": file_path,
                "confidence_label": "INFERRED",
            })

    return implements_batch


def build_partial_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link C# partial class declarations across files."""
    partial_of_batch: List[Dict[str, Any]] = []
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for file_data in all_file_data:
        if file_data.get("lang") not in ("csharp", "c_sharp"):
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        namespace = file_data.get("namespace") or file_data.get("package") or ""
        for cls in file_data.get("classes", []):
            if not cls.get("is_partial"):
                continue
            key = f"{namespace}::{cls.get('name')}"
            groups.setdefault(key, []).append({
                "name": cls.get("name"),
                "path": file_path,
                "line_number": cls.get("line_number"),
            })

    for entries in groups.values():
        if len(entries) < 2:
            continue
        entries.sort(
            key=lambda row: (
                "_Part" in Path(row["path"]).name or "_part" in Path(row["path"]).name,
                row.get("line_number") or 0,
            )
        )
        primary = entries[0]
        for part in entries[1:]:
            partial_of_batch.append({
                "child_name": part["name"],
                "child_label": "Class",
                "parent_name": primary["name"],
                "parent_label": "Class",
                "path": part["path"],
                "resolved_parent_file_path": primary["path"],
                "confidence_label": "INFERRED",
            })

    return partial_of_batch


def build_part_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link Dart library part files to their library root file."""
    part_of_batch: List[Dict[str, Any]] = []
    seen: set = set()

    part_of_re = re.compile(r"^\s*part\s+of\s+['\"]([^'\"]+)['\"]\s*;", re.MULTILINE)

    for file_data in all_file_data:
        if file_data.get("lang") != "dart":
            continue
        links = list(file_data.get("library_parts", []) or [])
        file_path = Path(file_data["path"])
        if not links and file_path.exists():
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            match = part_of_re.search(text)
            if match:
                links.append({
                    "main_file": str((file_path.parent / match.group(1)).resolve()),
                    "part_file": str(file_path.resolve()),
                    "direction": "part_of",
                })
        for link in links:
            if link.get("direction") != "part_of":
                continue
            child_path = str(Path(link["part_file"]).resolve())
            parent_path = str(Path(link["main_file"]).resolve())
            key = (child_path, parent_path)
            if key in seen:
                continue
            seen.add(key)
            part_of_batch.append({
                "child_path": child_path,
                "parent_path": parent_path,
            })

    return part_of_batch


def _parse_decorator_name(dec_raw: str) -> str:
    dec = dec_raw.strip()
    if dec.startswith("@"):
        dec = dec[1:]
    return dec.split("(")[0].strip()


def _resolve_decorator_path(
    decorator_name: str,
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
) -> str:
    caller_path = str(Path(caller_file_path).resolve().as_posix())
    if decorator_name in local_names:
        return caller_path
    if decorator_name in local_imports:
        imported = local_imports[decorator_name]
        if not isinstance(imported, str) or not imported:
            return caller_path
        lookup = imported.split(".")[-1]
        paths = imports_map.get(lookup, imports_map.get(imported, []))
        if len(paths) == 1:
            return str(Path(paths[0]).resolve().as_posix())
    paths = imports_map.get(decorator_name, [])
    if len(paths) == 1:
        return str(Path(paths[0]).resolve().as_posix())
    return caller_path


def build_decorated_by_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Build DECORATED_BY rows from parsed decorator metadata on functions/classes."""
    decorated_by_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_names = {
            item["name"]
            for key in ("functions", "classes")
            for item in file_data.get(key, [])
            if item.get("name")
        }
        # Parsed imports carry `name` / `full_import_name`; there is no `source`
        # key, so this mapped every imported symbol to None and made
        # _resolve_decorator_path bail out to the caller's own file before it
        # could consult imports_map. Mirrors the working construction in
        # build_inheritance_links above.
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        for entity_key, context_field in (("functions", "class_context"), ("classes", None)):
            for item in file_data.get(entity_key, []):
                decorators = item.get("decorators") or []
                if not decorators:
                    continue
                decorated_context = item.get(context_field) if context_field else None
                for dec_raw in decorators:
                    dec_name = _parse_decorator_name(dec_raw)
                    if not dec_name:
                        continue
                    dec_path = _resolve_decorator_path(
                        dec_name, caller_file_path, local_names, local_imports, imports_map
                    )
                    key = (
                        item["name"],
                        caller_file_path,
                        item["line_number"],
                        decorated_context or "",
                        dec_name,
                        dec_path,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    decorated_by_batch.append({
                        "decorated_name": item["name"],
                        "decorated_path": caller_file_path,
                        "decorated_line": item["line_number"],
                        "decorated_context": decorated_context or "",
                        "decorator_name": dec_name,
                        "decorator_path": dec_path,
                        "line_number": item["line_number"],
                    })

    return decorated_by_batch


def build_metaclass_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Build METACLASS rows from Python class metaclass= specifications."""
    metaclass_batch: List[Dict[str, Any]] = []
    seen: set = set()
    targets: Optional[PythonImportTargets] = None

    for file_data in all_file_data:
        if file_data.get("lang") != "python":
            continue
        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_class_names = {c["name"] for c in file_data.get("classes", [])}
        # Parsed imports carry `name` / `full_import_name`; there is no `source`
        # key, so this mapped every imported symbol to None and made
        # _resolve_decorator_path bail out to the caller's own file before it
        # could consult imports_map. Mirrors the working construction in
        # build_inheritance_links above.
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        scopes: Optional[_FileScopes] = None
        for class_item in file_data.get("classes", []):
            meta_name = class_item.get("metaclass")
            if not meta_name:
                continue
            parent_name = meta_name
            parent_line = None
            target = None
            if "." not in meta_name and meta_name in local_class_names:
                # the definition of the class's own file its scope sees (scope-aware, as
                # for INHERITS): a module-level `class Meta(type)`, never a Django-style
                # inner `class Meta:` of another class
                if scopes is None:
                    scopes = _FileScopes(file_data)
                target = scopes.target(caller_file_path, meta_name, class_item, "Class")
            if target is None:
                # no same-file definition is visible there: what the file's imports name
                if targets is None:
                    # built on the first imported metaclass only (most runs have none)
                    targets = PythonImportTargets(all_file_data)
                target = python_base_target(targets, file_data, meta_name, class_item.get("line_number"))
            if isinstance(target, Found) and target.label == "Class":
                # the class the file's import names: METACLASS links Class to Class,
                # under its declared name, pinned to its line
                resolved_path, parent_name, parent_line = target.path, target.name, target.line
            else:
                resolved_path = _resolve_decorator_path(
                    meta_name,
                    caller_file_path,
                    local_class_names,
                    local_imports,
                    imports_map,
                )
            key = (class_item["name"], caller_file_path, parent_name, resolved_path)
            if key in seen:
                continue
            seen.add(key)
            row = {
                "child_name": class_item["name"],
                "path": caller_file_path,
                "parent_name": parent_name,
                "resolved_parent_file_path": resolved_path,
                "line_number": class_item["line_number"],
                "confidence_label": "EXTRACTED",
            }
            if parent_line is not None:
                row["parent_line"] = parent_line
            metaclass_batch.append(row)

    return metaclass_batch


def build_companion_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link Kotlin companion objects to their enclosing class."""
    companion_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "kotlin":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        classes_by_name = {
            cls["name"]: cls for cls in file_data.get("classes", []) if cls.get("name")
        }

        for obj in file_data.get("objects", []):
            if obj.get("node_type") != "companion_object":
                continue
            owner_name = obj.get("class_context")
            if not owner_name:
                continue
            owner = classes_by_name.get(owner_name)
            if not owner:
                continue
            key = (obj["name"], file_path, obj["line_number"], owner_name, owner["line_number"])
            if key in seen:
                continue
            seen.add(key)
            companion_batch.append({
                "companion_name": obj["name"],
                "companion_path": file_path,
                "companion_line": obj["line_number"],
                "owner_name": owner_name,
                "owner_path": file_path,
                "owner_line": owner["line_number"],
            })

    return companion_batch


def build_embeds_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create Go struct embedding EMBEDS edges."""
    embeds_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "go":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        struct_names = {s["name"] for s in file_data.get("structs", []) if s.get("name")}

        for struct in file_data.get("structs", []):
            struct_name = struct.get("name")
            if not struct_name:
                continue
            for base in struct.get("bases") or []:
                if not base:
                    continue
                base_name = base.split(".")[-1]
                if base_name not in struct_names:
                    continue
                key = (struct_name, file_path, base_name)
                if key in seen:
                    continue
                seen.add(key)
                embeds_batch.append({
                    "child_name": struct_name,
                    "parent_name": base_name,
                    "path": file_path,
                    "resolved_parent_file_path": file_path,
                    "line_number": struct.get("line_number", 0),
                })

    return embeds_batch


def _resolve_type_name(
    type_name: str,
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
) -> Tuple[str, str]:
    """Resolve a bare Kotlin type name to a file path plus a confidence
    label, reusing _resolve_decorator_path's resolution order (local
    names -> local imports -> unique global import). Confidence is
    EXTRACTED when that resolution actually found something (either a
    same-file declaration or a real import target), INFERRED when it
    fell all the way back to guessing the caller's own file."""
    resolved_path = _resolve_decorator_path(
        type_name, caller_file_path, local_names, local_imports, imports_map
    )
    caller_path = str(Path(caller_file_path).resolve().as_posix())
    if type_name in local_names or resolved_path != caller_path:
        return resolved_path, "EXTRACTED"
    return resolved_path, "INFERRED"


def build_binds_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Resolve Hilt @Binds/@Provides functions on @Module classes/objects
    into BINDS row payloads for write_binds_links.

    @Binds: source = the function's return_type, target = the single
    arg_types entry (the abstract method's one parameter). Both are
    known statically -- no need to consult function_calls.

    @Provides: source = the function's return_type, target = the type
    constructed in the function body. Kotlin has no `new` keyword, so a
    constructor call is indistinguishable at the syntax level from any
    other call -- function_calls records it with call_kind "call" like
    every other invocation. We locate candidate calls by matching a
    call's context (function name, "function_declaration", function
    line_number) and class_context (enclosing class/object name) back
    to the @Provides function, then require the call's name to resolve
    to a known type (local class/interface/object or an import) so an
    incidental non-constructor call in the body isn't mistaken for the
    binding target. If more than one call in the body resolves to a
    known type, the actually-returned one is ambiguous with the
    information available -- e.g. "val logger = LoggerImpl();
    return ThingImpl(logger)" wants the last call, while
    "return ThingImpl(LoggerImpl())" wants the first (textually) -- so
    no row is emitted rather than guessing. A wrong DI edge is worse
    for impact analysis than a missing one.
    """
    binds_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "kotlin":
            continue

        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())

        # Unlike build_decorated_by_links' local_names (functions/classes
        # only), Hilt bindings routinely name an *interface* as the
        # return_type/arg_types entry, so interfaces must be included or
        # every @Binds row would incorrectly resolve to __external__/INFERRED.
        local_names = {
            item["name"]
            for key in ("classes", "interfaces", "objects")
            for item in file_data.get(key, [])
            if item.get("name")
        }
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        module_names = set()
        for key in ("classes", "objects"):
            for item in file_data.get(key, []):
                for dec_raw in item.get("decorators") or []:
                    if _parse_decorator_name(dec_raw) == "Module":
                        module_names.add(item.get("name"))
                        break

        if not module_names:
            continue

        function_calls = file_data.get("function_calls") or []

        for func in file_data.get("functions", []):
            class_context = func.get("class_context")
            if not class_context or class_context not in module_names:
                continue

            dec_names = {_parse_decorator_name(d) for d in (func.get("decorators") or [])}
            return_type = func.get("return_type")

            if "Binds" in dec_names:
                provider = "Binds"
                arg_types = func.get("arg_types") or []
                if not return_type or len(arg_types) != 1 or not arg_types[0]:
                    continue
                target_type = arg_types[0]
            elif "Provides" in dec_names:
                provider = "Provides"
                if not return_type:
                    continue
                func_name = func.get("name")
                func_line = func.get("line_number")
                candidates = []
                for call in function_calls:
                    ctx = call.get("context") or []
                    call_class_ctx = call.get("class_context") or []
                    if (
                        len(ctx) >= 3
                        and ctx[0] == func_name
                        and ctx[2] == func_line
                        and len(call_class_ctx) >= 1
                        and call_class_ctx[0] == class_context
                    ):
                        call_name = call.get("name")
                        if call_name and (
                            call_name in local_names
                            or call_name in local_imports
                            or call_name in imports_map
                        ):
                            candidates.append(call_name)
                if not candidates:
                    continue
                if len(candidates) > 1:
                    # More than one type-resolvable call in the body -- e.g.
                    # "val logger = LoggerImpl(); return ThingImpl(logger)"
                    # (wanted call is last) vs "return ThingImpl(LoggerImpl())"
                    # (wanted call is first, textually). Neither a first- nor
                    # last-line tie-break is correct in general with the
                    # information available in function_calls, and a wrong DI
                    # edge is worse than a missing one for impact analysis.
                    # Skip rather than guess, mirroring the @Binds arity check
                    # above.
                    continue
                target_type = candidates[0]
            else:
                continue

            source_path, source_conf = _resolve_type_name(
                return_type, caller_file_path, local_names, local_imports, imports_map
            )
            target_path, target_conf = _resolve_type_name(
                target_type, caller_file_path, local_names, local_imports, imports_map
            )
            confidence_label = (
                "EXTRACTED" if source_conf == "EXTRACTED" and target_conf == "EXTRACTED" else "INFERRED"
            )

            key = (return_type, source_path, target_type, target_path, func.get("line_number"), provider)
            if key in seen:
                continue
            seen.add(key)

            binds_batch.append({
                "source_name": return_type,
                "source_path": source_path,
                "target_name": target_type,
                "target_path": target_path,
                "line_number": func.get("line_number"),
                "provider": provider,
                "confidence_label": confidence_label,
            })

    return binds_batch


def build_previews_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Build PREVIEWS rows: a @Preview-annotated Compose function exists
    only to render some composable, so link it to each composable it
    calls, resolved from function_calls.

    Decorator matching reuses _parse_decorator_name (as build_decorated_by_links
    and build_binds_links do) to strip the leading "@" and any "(...)"
    arguments down to the bare annotation name, then compares it for
    equality against "Preview". This is the word-boundary-safe equivalent
    of kotlin.py's anchored `^@Preview\\b` regex for is_composable: because
    the comparison is exact-match rather than substring/prefix, "Preview"
    != "PreviewParameter" and "Preview" != "PreviewScreenSizes", so those
    unrelated annotations are correctly excluded without a parallel
    annotation-name parser.

    Name resolution reuses _resolve_decorator_path, same as build_binds_links
    reuses it via _resolve_type_name.

    A candidate call target is only emitted once it is confirmed to be an
    actual @Composable function (via a global (name, path) -> is_composable
    index built up front) -- otherwise an incidental non-composable call in
    a preview function's body (e.g. a logging call) would be mistaken for
    the previewed composable.

    Annotation-echo filtering (backstop): KOTLIN_QUERIES["calls"] captures
    constructor_invocation nodes, and any annotation with arguments --
    "@Preview(showBackground = true)", "@Query(...)", "@InstallIn(...)" --
    is syntactically a constructor_invocation. The Kotlin parser used to
    record the annotation itself as a phantom entry in function_calls,
    sharing the annotated function's context (issue #1602). That is now
    filtered at source by KotlinTreeSitterParser._is_within_annotation, so
    no echo should reach this builder.

    The rejection below is kept as a backstop rather than removed, because
    a composable_index membership check alone would not be enough if an
    echo ever returned: it only fails to match by coincidence, when no
    @Composable function happens to be named e.g. "Preview" or "Query". If
    one existed with that exact name and were resolvable from this file,
    the phantom would pass the composable_index check and produce a bogus
    PREVIEWS edge to a composable the preview function never actually
    calls. Rejecting any candidate whose name matches one of the *same
    function's own* decorator names (also via _parse_decorator_name) closes
    that gap deterministically -- a real call to a composable can never be
    named identically to one of its own annotations, so this can only ever
    reject an echo, never a genuine call. It costs one set lookup per
    candidate and is pinned by
    test_annotation_echo_is_rejected_even_when_a_same_named_composable_exists,
    which feeds it hand-built rows rather than parser output.
    """
    previews_batch: List[Dict[str, Any]] = []
    seen: set = set()

    # Global index of composable functions by (name, resolved path), built
    # once so a call resolved through an import can be confirmed to
    # actually target a @Composable function rather than any function
    # sharing that name.
    composable_index: set = set()
    for file_data in all_file_data:
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        for func in file_data.get("functions", []):
            if func.get("is_composable") and func.get("name"):
                composable_index.add((func["name"], file_path))

    for file_data in all_file_data:
        if file_data.get("lang") != "kotlin":
            continue

        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_names = {
            item["name"] for item in file_data.get("functions", []) if item.get("name")
        }
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }
        function_calls = file_data.get("function_calls") or []

        for func in file_data.get("functions", []):
            decorators = func.get("decorators") or []
            if not any(_parse_decorator_name(dec) == "Preview" for dec in decorators):
                continue

            preview_name = func.get("name")
            preview_line = func.get("line_number")
            if not preview_name or preview_line is None:
                continue

            # Backstop only: the parser no longer emits annotation echoes
            # into function_calls (#1602), but rejecting any candidate whose
            # name matches one of this function's own decorator names keeps
            # the exclusion holding regardless of what else is named in the
            # indexed codebase -- see the docstring.
            own_decorator_names = {_parse_decorator_name(d) for d in decorators}

            for call in function_calls:
                ctx = call.get("context") or ()
                if len(ctx) < 3 or ctx[0] != preview_name or ctx[2] != preview_line:
                    continue
                call_name = call.get("name")
                if not call_name:
                    continue
                if call_name in own_decorator_names:
                    continue

                resolved_path = _resolve_decorator_path(
                    call_name, caller_file_path, local_names, local_imports, imports_map
                )
                if (call_name, resolved_path) not in composable_index:
                    continue

                key = (preview_name, caller_file_path, preview_line, call_name, resolved_path)
                if key in seen:
                    continue
                seen.add(key)

                previews_batch.append({
                    "preview_name": preview_name,
                    "preview_path": caller_file_path,
                    "preview_line": preview_line,
                    "composable_name": call_name,
                    "composable_path": resolved_path,
                    "line_number": preview_line,
                    # Kept for shape-parity with the other builders in this
                    # module (all of which carry a confidence_label) and in
                    # case a future PREVIEWS schema change adds the column,
                    # but PREVIEWS currently has no confidence_label column
                    # and write_previews_links does not set it -- this
                    # value is always "EXTRACTED" (every row here has
                    # already been positively confirmed against
                    # composable_index) and is not currently persisted.
                    "confidence_label": "EXTRACTED",
                })

    return previews_batch


def build_elixir_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create defimpl -> defprotocol IMPLEMENTS edges for Elixir modules."""
    implements_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "elixir":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        for module in file_data.get("modules", []):
            if module.get("type") != "defimpl":
                continue
            full_name = module.get("name") or ""
            if "." not in full_name:
                continue
            impl_name, for_type = full_name.rsplit(".", 1)
            key = (for_type, file_path, impl_name, module.get("line_number", 0))
            if key in seen:
                continue
            seen.add(key)
            implements_batch.append({
                "child_name": for_type,
                "child_label": "Module",
                "parent_name": impl_name,
                "parent_label": "Module",
                "path": file_path,
                "resolved_parent_file_path": file_path,
                "line_number": module.get("line_number", 0),
                "confidence_label": "EXTRACTED",
            })

    return implements_batch
