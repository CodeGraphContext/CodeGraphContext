# src/codegraphcontext/core/graph_snapshot.py
"""Snapshot manifests and graph diffs for `cgc snapshot` / `cgc diff` (#1312).

A *snapshot* is a lightweight JSON manifest of one index state: one record per
node and per edge carrying a stable identity, a display name, its properties and
a content digest. It is deliberately **not** a second graph and **not** a
``.cgc`` bundle — the bundle format ships full node data for re-import
(``core/cgc_bundle.py``), while a snapshot only ever has to answer "what changed
since ...?".

The snapshot format is the contract this module owns:

* ``format``: ``cgc-snapshot``, ``format_version``: 1
* nodes/edges are *lists* (deterministic on disk); identity de-duplication and
  diffing happen at read time so the on-disk bytes stay stable.
* digests exclude volatile properties (``indexed_at``) and anything the backend
  does not store on every driver (``None`` values, internal ``_``-prefixed
  fields) so two re-indexes of unchanged code produce identical records.

Everything here is pure: no Typer, no Rich, no console. The CLI layer
(``cli/snapshot_commands.py``) owns paths, printing and exit codes; it renders
these documents rather than re-deriving them.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .cgc_bundle import CGCBundle

#: Discriminator written into every snapshot file.
SNAPSHOT_FORMAT = "cgc-snapshot"
#: Bump only for breaking changes; readers reject higher versions.
SNAPSHOT_FORMAT_VERSION = 1

#: Discriminator for the document `cgc diff --json` prints on stdout.
DIFF_FORMAT = "cgc-diff"
DIFF_FORMAT_VERSION = 1

#: Discriminator for `cgc snapshot list --json`.
SNAPSHOT_LIST_FORMAT = "cgc-snapshot-list"
SNAPSHOT_LIST_FORMAT_VERSION = 1

#: Discriminator for the `cgc snapshot save --json` receipt.
SNAPSHOT_SAVE_FORMAT = "cgc-snapshot-save"
SNAPSHOT_SAVE_FORMAT_VERSION = 1

#: Set by the indexer on ``Repository`` on every index run, so it would make
#: two snapshots of byte-identical code look different (#1312).
VOLATILE_PROPERTIES = frozenset({"indexed_at"})

#: Snapshot names double as file names, so keep them boring.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

#: The whole graph, no scoping: a snapshot answers "what changed in this index".
NODE_QUERY = "MATCH (n) RETURN n, labels(n) as labels"
EDGE_QUERY = (
    "MATCH (a)-[r]->(b) "
    "RETURN a, r, b, type(r) as rel_type, "
    "labels(a) as source_labels, labels(b) as target_labels"
)

_MISSING = object()


class SnapshotError(Exception):
    """A snapshot could not be read, written or diffed. Maps to exit code 1."""


class SnapshotUsageError(SnapshotError):
    """Bad user input (name, limit, ...). Maps to exit code 2."""


class SnapshotExistsError(SnapshotError):
    """A snapshot already exists at the target path and ``--force`` was not given."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(when: Optional[datetime] = None) -> str:
    """RFC3339 UTC timestamp with a ``Z`` suffix (stable across platforms)."""
    value = when or utc_now()
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def cgc_version() -> str:
    try:
        return _package_version("codegraphcontext")
    except PackageNotFoundError:
        return "0.0.0 (dev)"


def validate_name(name: str) -> str:
    """Return *name* or raise :class:`SnapshotUsageError`.

    Names become file names under ``~/.codegraphcontext/snapshots/``, so no
    separators, no leading dot and no traversal.
    """
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SnapshotUsageError(
            f"Invalid snapshot name {name!r}: use letters, digits, '.', '_' or '-' "
            "(max 64 characters, must start with a letter or digit)"
        )
    return name


def default_snapshot_name(when: Optional[datetime] = None) -> str:
    stamp = (when or utc_now()).astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"snapshot-{stamp}"


def snapshot_path(directory: Path, name: str) -> Path:
    return Path(directory) / f"{name}.json"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, Path):
        return obj.as_posix()
    return str(obj)


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default
    )


def dump_json(payload: Any) -> str:
    """Pretty JSON for stdout, ASCII-escaped.

    ``ensure_ascii`` keeps a symbol name with an accent from turning
    ``cgc diff --json > changes.json`` into a ``UnicodeEncodeError`` on a
    non-UTF-8 code page; ``\\uXXXX`` escapes stay valid JSON for any consumer.
    """
    return json.dumps(payload, indent=2, ensure_ascii=True, default=_json_default)


def digest_payload(payload: Any) -> str:
    """Stable content digest: sha256 of the canonical JSON encoding."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def digest_properties(properties: Dict[str, Any]) -> str:
    return digest_payload(properties)


def _clean_props(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a property map for storage and digesting.

    * ``_``-prefixed keys are backend bookkeeping (``_id``, ``_label``,
      ``_src``/``_dst``) whose values move between re-indexes.
    * ``None`` means "unset" — Neo4j omits such keys entirely while embedded
      backends return them, so dropping them keeps digests comparable.
    * :data:`VOLATILE_PROPERTIES` is stamped on every index run.
    """
    cleaned: Dict[str, Any] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key in VOLATILE_PROPERTIES:
            continue
        if value is None:
            continue
        cleaned[key] = value
    return cleaned


def props_of(node_or_rel: Any) -> Dict[str, Any]:
    """Read a property map off a driver node/relationship object.

    Mirrors ``CGCBundle._node_to_dict`` (and the relationship branch of
    ``_extract_edges``) so snapshot identities match what bundle export sees.
    """
    raw: Dict[str, Any] = {}
    try:
        raw = dict(node_or_rel)
    except (TypeError, ValueError):
        raw = {}
    if not raw:
        for attr in ("_properties", "properties"):
            if hasattr(node_or_rel, attr):
                try:
                    raw = dict(getattr(node_or_rel, attr))
                except (TypeError, ValueError):
                    continue
                break
    return _clean_props(raw)


def normalize_labels(value: Any) -> List[str]:
    """Driver labels come back as a string, list, tuple or set depending on the backend."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    if isinstance(value, Iterable):
        try:
            return [str(v) for v in value]
        except TypeError:
            return [str(value)]
    return [str(value)]


def identity_of(labels: Sequence[str], properties: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(identity, primary_label)`` for a node.

    The identity is the graph's own primary key — ``CGCBundle._PK_MAP`` with the
    ``uid`` synthesis of ``CGCBundle._UID_PARTS`` — never the backend's internal
    id, which is renumbered by every re-index (and, for embedded backends, is
    literally a Python object id).

    Kùzu/Ladybug persist ``uid`` as a real property; Neo4j/FalkorDB do not, so
    the same ``uid`` is re-synthesised here from the parts the writer recorded.
    """
    label_list = list(labels or [])
    for label in label_list:
        pk_field = CGCBundle._PK_MAP.get(label)
        if not pk_field:
            continue
        if pk_field == "uid":
            if properties.get("uid") is not None:
                value = str(properties["uid"])
            else:
                parts = CGCBundle._UID_PARTS.get(label, [])
                value = "".join(
                    str(properties.get(part, 0 if part == "occurrence_index" else ""))
                    for part in parts
                )
            return f"{label}:uid:{value}", label
        if properties.get(pk_field) is not None:
            return f"{label}:{pk_field}:{properties[pk_field]}", label

    # No declared primary key: same precedence CGCBundle._node_key falls back to.
    primary = label_list[0] if label_list else "Node"
    for fallback in ("uid", "id", "path", "name"):
        if properties.get(fallback) is not None:
            return f"{primary}:{fallback}:{properties[fallback]}", primary
    return f"{primary}:anon:{digest_properties(properties)}", primary


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def display_of(primary_label: str, properties: Dict[str, Any]) -> str:
    """Human-facing qualified name for a node record.

    ``module_context``/``class_context`` prefix the bare name so two functions
    called ``build`` in different classes stay distinguishable; path-bearing
    labels (``File``, ``Repository``, ``Module``, ...) show their path/name as
    stored, because that *is* their name.
    """
    if primary_label in ("Repository", "File", "Directory", "Module", "DbTable", "Datasource"):
        return _as_text(properties.get("path")) or _as_text(properties.get("name"))
    name = _as_text(properties.get("name"))
    if not name:
        return _as_text(properties.get("path"))
    for qualifier in ("module_context", "class_context", "context"):
        prefix = _as_text(properties.get(qualifier))
        if prefix and prefix != name and prefix != "<module>":
            return f"{prefix}.{name}"
    return name


def _display_or_id(display: str, identity: str) -> str:
    return display or identity


def _unique_ids(records: List[Dict[str, Any]]) -> None:
    """Give duplicate ids a deterministic ``#2``, ``#3`` ... suffix in place.

    Duplicate identities can only come from genuinely repeated rows (two edges
    between the same pair of nodes). Sorting first keeps the numbering stable
    across runs of the same index state.
    """
    records.sort(key=lambda rec: (rec["id"], rec.get("digest", "")))
    seen: Dict[str, int] = {}
    for record in records:
        base_id = record["id"]
        count = seen.get(base_id, 0)
        seen[base_id] = count + 1
        if count:
            record["id"] = f"{base_id}#{count + 1}"


@dataclass
class Snapshot:
    """One index state, as stored on disk."""

    name: str
    created_at: str
    context: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    cgc_version: str = field(default_factory=cgc_version)
    format_version: int = SNAPSHOT_FORMAT_VERSION

    @property
    def counts(self) -> Dict[str, int]:
        return {"nodes": len(self.nodes), "edges": len(self.edges)}

    def to_document(self) -> Dict[str, Any]:
        return {
            "format": SNAPSHOT_FORMAT,
            "format_version": self.format_version,
            "name": self.name,
            "created_at": self.created_at,
            "cgc_version": self.cgc_version,
            "context": dict(self.context),
            "counts": self.counts,
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_document(), indent=2, ensure_ascii=False, default=_json_default)

    @classmethod
    def from_document(cls, data: Any, source: str = "<memory>") -> "Snapshot":
        if not isinstance(data, dict):
            raise SnapshotError(f"{source} is not a cgc snapshot manifest (expected a JSON object)")
        if data.get("format") != SNAPSHOT_FORMAT:
            raise SnapshotError(
                f"{source} is not a cgc snapshot manifest "
                f"(format={data.get('format')!r}, expected {SNAPSHOT_FORMAT!r})"
            )
        version = data.get("format_version")
        if not isinstance(version, int) or not 1 <= version <= SNAPSHOT_FORMAT_VERSION:
            raise SnapshotError(
                f"{source} uses snapshot format version {version!r}, which this "
                f"cgc build cannot read (supported: 1..{SNAPSHOT_FORMAT_VERSION})"
            )
        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise SnapshotError(f"{source} is missing its node/edge manifest")
        for kind, records in (("node", nodes), ("edge", edges)):
            for record in records:
                if not isinstance(record, dict) or "id" not in record or "digest" not in record:
                    raise SnapshotError(f"{source} has a malformed {kind} record")
        context = data.get("context")
        if not isinstance(context, dict):
            context = {}
        return cls(
            name=str(data.get("name") or ""),
            created_at=str(data.get("created_at") or ""),
            context=context,
            nodes=nodes,
            edges=edges,
            cgc_version=str(data.get("cgc_version") or ""),
            format_version=version,
        )


def load_snapshot(path: Path) -> Snapshot:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SnapshotError(f"Snapshot not found: {path}") from None
    except OSError as exc:
        raise SnapshotError(f"Cannot read snapshot {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"{path} is not valid JSON: {exc}") from exc
    return Snapshot.from_document(data, source=str(path))


def save_snapshot(snapshot: Snapshot, path: Path, force: bool = False) -> Path:
    path = Path(path)
    if path.exists() and not force:
        raise SnapshotExistsError(
            f"Snapshot {snapshot.name!r} already exists at {path} (use --force to overwrite)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp"
    try:
        tmp_path.write_text(snapshot.to_json() + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except OSError as exc:
        raise SnapshotError(f"Cannot write snapshot {path}: {exc}") from exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return path


@dataclass
class SnapshotEntry:
    """A snapshot file as listed by `cgc snapshot list`."""

    name: str
    path: Path
    snapshot: Optional[Snapshot] = None
    error: Optional[str] = None

    @property
    def created_at(self) -> str:
        return self.snapshot.created_at if self.snapshot else ""

    @property
    def counts(self) -> Dict[str, int]:
        return self.snapshot.counts if self.snapshot else {"nodes": 0, "edges": 0}

    @property
    def context(self) -> Dict[str, Any]:
        return self.snapshot.context if self.snapshot else {}


def list_snapshots(directory: Path) -> List[SnapshotEntry]:
    """Read every snapshot under *directory*, newest first.

    An unreadable file becomes an entry with ``error`` set rather than aborting
    the listing — one corrupt snapshot must not hide the rest.
    """
    directory = Path(directory)
    entries: List[SnapshotEntry] = []
    if not directory.is_dir():
        return entries
    for path in sorted(directory.glob("*.json")):
        name = path.stem
        try:
            snapshot = load_snapshot(path)
        except SnapshotError as exc:
            entries.append(SnapshotEntry(name=name, path=path, error=str(exc)))
            continue
        entries.append(SnapshotEntry(name=snapshot.name or name, path=path, snapshot=snapshot))
    entries.sort(key=lambda entry: (entry.created_at, entry.name), reverse=True)
    return entries


def build_snapshot(
    db_manager: Any,
    *,
    name: str,
    context: Optional[Dict[str, Any]] = None,
    graph_name: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Snapshot:
    """Read the live index into a :class:`Snapshot`.

    Uses the same two queries bundle export uses, so a snapshot sees exactly the
    graph a bundle would carry.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    with db_manager.get_driver(graph_name).session() as session:
        for record in session.run(NODE_QUERY):
            labels = normalize_labels(record["labels"])
            properties = props_of(record["n"])
            identity, primary = identity_of(labels, properties)
            nodes.append(
                {
                    "id": identity,
                    "label": primary,
                    "display": display_of(primary, properties),
                    "path": _as_text(properties.get("path")) or None,
                    "digest": digest_properties(properties),
                    "properties": properties,
                }
            )

        for record in session.run(EDGE_QUERY):
            rel_type = str(record["rel_type"])
            source_labels = normalize_labels(record["source_labels"])
            target_labels = normalize_labels(record["target_labels"])
            source_props = props_of(record["a"])
            target_props = props_of(record["b"])
            source_id, source_label = identity_of(source_labels, source_props)
            target_id, target_label = identity_of(target_labels, target_props)
            properties = props_of(record["r"])
            edges.append(
                {
                    "id": f"{source_id} -[{rel_type}]-> {target_id}",
                    "type": rel_type,
                    "source": source_id,
                    "target": target_id,
                    "source_label": source_label,
                    "target_label": target_label,
                    "source_display": _display_or_id(
                        display_of(source_label, source_props), source_id
                    ),
                    "target_display": _display_or_id(
                        display_of(target_label, target_props), target_id
                    ),
                    "digest": digest_properties(properties),
                    "properties": properties,
                }
            )

    _unique_ids(nodes)
    _unique_ids(edges)
    return Snapshot(
        name=name,
        created_at=iso_utc(now),
        context=dict(context or {}),
        nodes=nodes,
        edges=edges,
    )


def _index_by_id(records: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {record["id"]: record for record in records}


def _changed_keys(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    keys = set(before) | set(after)
    return sorted(
        key for key in keys if before.get(key, _MISSING) != after.get(key, _MISSING)
    )


#: How far a signature may walk up CONTAINS/HAS_PARAMETER chains before it stops.
_SIGNATURE_DEPTH = 4

#: Edges that express ownership. Signatures and owner-qualified displays walk
#: these and only these: a CALLS edge makes the callee a *caller's target*, not
#: a child, so deleting a call must not re-key the function it pointed at.
_OWNER_EDGE_TYPES = frozenset({"CONTAINS", "HAS_PARAMETER"})


def _parent_ids(edges: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    parents: Dict[str, List[str]] = {}
    for edge in edges:
        if edge.get("type") in _OWNER_EDGE_TYPES:
            parents.setdefault(edge["target"], []).append(edge["source"])
    return parents


def _node_signatures(
    records: Sequence[Dict[str, Any]], edges: Sequence[Dict[str, Any]]
) -> Dict[str, str]:
    """Name/path identity for each node, stable across a line shift.

    The graph's own ``uid`` embeds ``line_number`` (and a parameter's
    ``function_line_number``), so typing a line above a function re-keys it:
    without this, a pure line shift would read as "one node deleted, an
    identical one added", which buries every real change. The signature keeps
    ``label``+``name``+``path`` and walks incoming edges (File CONTAINS
    Function, Function HAS_PARAMETER Parameter) so two ``amount`` parameters
    belonging to different functions stay distinguishable.
    """
    by_id = {record["id"]: record for record in records}
    parents = _parent_ids(edges)
    memo: Dict[str, str] = {}
    active: set = set()

    def build(node_id: str, depth: int) -> str:
        if node_id in memo:
            return memo[node_id]
        record = by_id.get(node_id)
        if record is None:
            return f"?{node_id}"
        if node_id in active or depth >= _SIGNATURE_DEPTH:
            return f"{record.get('label', '')}:{node_id}"
        active.add(node_id)
        properties = record.get("properties") or {}
        name = (
            _as_text(properties.get("name"))
            or _as_text(properties.get("path"))
            or _as_text(record.get("display"))
        )
        parts = [_as_text(record.get("label")), name, _as_text(record.get("path"))]
        chain = sorted(build(parent, depth + 1) for parent in parents.get(node_id, []))
        if chain:
            parts.append("@" + ",".join(chain))
        active.discard(node_id)
        memo[node_id] = "|".join(parts)
        return memo[node_id]

    return {record["id"]: build(record["id"], 0) for record in records}


def _edge_signatures(
    records: Sequence[Dict[str, Any]], node_signatures: Dict[str, str]
) -> Dict[str, str]:
    """Identity of an edge from its endpoints' node signatures."""
    return {
        record["id"]: (
            f"{node_signatures.get(record['source'], record['source'])} "
            f"-[{record.get('type', '')}]-> "
            f"{node_signatures.get(record['target'], record['target'])}"
        )
        for record in records
    }


def _pair_records(
    before_records: Sequence[Dict[str, Any]],
    after_records: Sequence[Dict[str, Any]],
    before_signatures: Dict[str, str],
    after_signatures: Dict[str, str],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Match records that share a signature but not an id — only unambiguously.

    A signature with exactly one survivor on each side is a move; anything
    with two candidates on either side is left alone rather than guessed.
    """
    before_by_signature: Dict[str, List[Dict[str, Any]]] = {}
    after_by_signature: Dict[str, List[Dict[str, Any]]] = {}
    for record in before_records:
        key = before_signatures.get(record["id"], record["id"])
        before_by_signature.setdefault(key, []).append(record)
    for record in after_records:
        key = after_signatures.get(record["id"], record["id"])
        after_by_signature.setdefault(key, []).append(record)

    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for key in sorted(set(before_by_signature) & set(after_by_signature)):
        before_group, after_group = before_by_signature[key], after_by_signature[key]
        if len(before_group) == 1 and len(after_group) == 1:
            pairs.append((before_group[0], after_group[0]))
    return pairs


def _node_change(
    before: Dict[str, Any], after: Dict[str, Any], reason: str
) -> Dict[str, Any]:
    changed_keys = _changed_keys(before.get("properties") or {}, after.get("properties") or {})
    return {
        "id": after["id"],
        "label": after.get("label", ""),
        "display": after.get("display", ""),
        "path": after.get("path"),
        "reason": reason,
        "before": before.get("properties") or {},
        "after": after.get("properties") or {},
        "changed_properties": changed_keys,
    }


def _qualified_displays(
    records: Sequence[Dict[str, Any]], edges: Sequence[Dict[str, Any]]
) -> Dict[str, str]:
    """Node displays, qualified by their owning Function/Class.

    A parameter renders as bare ``amount`` — and a diff of two functions that
    both take ``amount`` becomes unreadable. Owners of this kind are exactly
    what ``module_context``/``class_context`` do for functions, applied here
    where the owner is an edge rather than a property.

    Only ownership edges count: a CALLS edge pointing at ``validate_card``
    makes it a *callee* of ``process_payment``, not a child of it.
    """
    by_id = {record["id"]: record for record in records}
    owner_of = _parent_ids(edges)
    displays: Dict[str, str] = {}
    for record in records:
        display = _as_text(record.get("display")) or record["id"]
        qualifier = ""
        for parent_id in owner_of.get(record["id"], []):
            parent = by_id.get(parent_id)
            if parent and parent.get("label") in ("Function", "Class", "Method"):
                qualifier = _as_text(parent.get("display")) or ""
                break
        displays[record["id"]] = f"{qualifier}.{display}" if qualifier else display
    return displays


def _requalify_nodes(
    records: Sequence[Dict[str, Any]], displays: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Copies of node rows with ``display`` re-qualified by their owner."""
    return [
        {**record, "display": displays.get(record["id"], record.get("display"))}
        for record in records
    ]


def _node_changes(
    base_nodes: Dict[str, Dict[str, Any]],
    current_nodes: Dict[str, Dict[str, Any]],
    base_signatures: Dict[str, str],
    current_signatures: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    added = [current_nodes[key] for key in sorted(set(current_nodes) - set(base_nodes))]
    removed = [base_nodes[key] for key in sorted(set(base_nodes) - set(current_nodes))]
    changed: List[Dict[str, Any]] = []
    for key in sorted(set(base_nodes) & set(current_nodes)):
        before, after = base_nodes[key], current_nodes[key]
        if before["digest"] == after["digest"]:
            continue
        changed.append(_node_change(before, after, "properties"))

    paired_before: set = set()
    paired_after: set = set()
    for before, after in _pair_records(removed, added, base_signatures, current_signatures):
        paired_before.add(before["id"])
        paired_after.add(after["id"])
        # Content identical means only the internal key moved: nothing to report.
        if before["digest"] != after["digest"]:
            changed.append(_node_change(before, after, "moved"))

    removed = [record for record in removed if record["id"] not in paired_before]
    added = [record for record in added if record["id"] not in paired_after]
    changed.sort(key=lambda record: (record.get("label", ""), record.get("display", "")))
    return {"added": added, "removed": removed, "changed": changed}


def _edge_changes(
    base_edges: List[Dict[str, Any]],
    current_edges: List[Dict[str, Any]],
    base_nodes: Dict[str, Dict[str, Any]],
    current_nodes: Dict[str, Dict[str, Any]],
    base_signatures: Dict[str, str],
    current_signatures: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Diff edges in three passes: shared ids, shared endpoints, retargets.

    Pass 2 exists because an edge id embeds its endpoints' ``uid``s, so both
    endpoints shifting by a line would otherwise read as one edge deleted and
    an identical one added. Pass 3 folds a retarget — one removed and one added
    edge with the same source and type — into a single ``target changed`` row,
    but only when exactly one of each exists *and* the new target already
    existed in the base graph. Without that last condition a file that gained
    ``refund`` while losing ``legacy_checkout`` would claim its CONTAINS edge
    was retargeted, which is two unrelated facts, not one.
    """
    base_by_id = _index_by_id(base_edges)
    current_by_id = _index_by_id(current_edges)

    added = [current_by_id[key] for key in sorted(set(current_by_id) - set(base_by_id))]
    removed = [base_by_id[key] for key in sorted(set(base_by_id) - set(current_by_id))]
    changed: List[Dict[str, Any]] = []

    for key in sorted(set(base_by_id) & set(current_by_id)):
        before, after = base_by_id[key], current_by_id[key]
        if before["digest"] == after["digest"]:
            continue
        changed.append(_edge_change(before, after, "properties"))

    paired: set = set()
    for before, after in _pair_records(
        removed,
        added,
        _edge_signatures(base_edges, base_signatures),
        _edge_signatures(current_edges, current_signatures),
    ):
        paired.add(before["id"])
        paired.add(after["id"])
        # Same endpoints, same edge properties: only the embedding uids moved.
        if before["digest"] != after["digest"]:
            changed.append(_edge_change(before, after, "properties"))

    remaining_removed = [record for record in removed if record["id"] not in paired]
    remaining_added = [record for record in added if record["id"] not in paired]

    removed_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    added_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for record in remaining_removed:
        source = base_signatures.get(record["source"], record["source"])
        removed_by_key.setdefault((source, record["type"]), []).append(record)
    for record in remaining_added:
        source = current_signatures.get(record["source"], record["source"])
        added_by_key.setdefault((source, record["type"]), []).append(record)

    base_signature_values = set(base_signatures.values())
    for key, removed_group in removed_by_key.items():
        added_group = added_by_key.get(key) or []
        if len(removed_group) != 1 or len(added_group) != 1:
            continue
        old_edge, new_edge = removed_group[0], added_group[0]
        # A source that vanished itself is a deletion, not a retarget.
        if new_edge["source"] not in current_nodes:
            continue
        # ...and a target that is itself brand new is an addition, not a
        # retarget: the removed edge simply belonged to something else.
        target_signature = current_signatures.get(new_edge["target"], new_edge["target"])
        if new_edge["target"] not in base_nodes and target_signature not in base_signature_values:
            continue
        paired.add(old_edge["id"])
        paired.add(new_edge["id"])
        changed.append(_edge_change(old_edge, new_edge, "target", target=new_edge))

    if paired:
        added = [record for record in added if record["id"] not in paired]
        removed = [record for record in removed if record["id"] not in paired]

    changed.sort(
        key=lambda record: (
            record.get("type", ""),
            record.get("source", ""),
            str(record.get("after", {}).get("target", "")),
        )
    )
    return {"added": added, "removed": removed, "changed": changed}


def _edge_change(
    before: Dict[str, Any],
    after: Dict[str, Any],
    reason: str,
    target: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one ``edges.changed`` row from *before* to *after*."""
    after_side = target or after
    changed_keys = (
        ["target"]
        if reason == "target"
        else _changed_keys(before.get("properties") or {}, after.get("properties") or {})
    )
    return {
        "type": after.get("type", before.get("type", "")),
        "source": after.get("source", ""),
        "source_label": after.get("source_label", ""),
        "source_display": after.get("source_display", ""),
        "reason": reason,
        "before": {
            "id": before["id"],
            "target": before.get("target", ""),
            "target_label": before.get("target_label", ""),
            "target_display": before.get("target_display", ""),
            "properties": before.get("properties") or {},
        },
        "after": {
            "id": after_side["id"],
            "target": after_side.get("target", ""),
            "target_label": after_side.get("target_label", ""),
            "target_display": after_side.get("target_display", ""),
            "properties": after_side.get("properties") or {},
        },
        "changed_properties": changed_keys,
    }


def diff_snapshots(base: Snapshot, current: Snapshot) -> Dict[str, Any]:
    """Compare *base* (a saved snapshot) against *current* (usually the live index).

    Returns the ``cgc-diff`` document: stable keys first, human output is a
    rendering of it and nothing more.
    """
    base_nodes = _index_by_id(base.nodes)
    current_nodes = _index_by_id(current.nodes)
    base_signatures = _node_signatures(base.nodes, base.edges)
    current_signatures = _node_signatures(current.nodes, current.edges)
    base_displays = _qualified_displays(base.nodes, base.edges)
    current_displays = _qualified_displays(current.nodes, current.edges)

    nodes = _node_changes(base_nodes, current_nodes, base_signatures, current_signatures)
    edges = _edge_changes(
        base.edges,
        current.edges,
        base_nodes,
        current_nodes,
        base_signatures,
        current_signatures,
    )

    # Owner-qualified displays. Only node rows get them: an edge row already
    # names its source, so `HAS_PARAMETER refund -> amount` is unambiguous and
    # qualifying the target too would just repeat the source.
    nodes["added"] = _requalify_nodes(nodes["added"], current_displays)
    nodes["removed"] = _requalify_nodes(nodes["removed"], base_displays)
    nodes["changed"] = _requalify_nodes(nodes["changed"], current_displays)

    summary = {
        "nodes": {key: len(value) for key, value in nodes.items()},
        "edges": {key: len(value) for key, value in edges.items()},
    }
    summary["total"] = sum(summary["nodes"].values()) + sum(summary["edges"].values())

    return {
        "format": DIFF_FORMAT,
        "format_version": DIFF_FORMAT_VERSION,
        "base": {
            "name": base.name,
            "created_at": base.created_at,
            "cgc_version": base.cgc_version,
            "context": dict(base.context),
        },
        "current": {
            "name": current.name,
            "created_at": current.created_at,
            "cgc_version": current.cgc_version,
            "context": dict(current.context),
        },
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
    }


def save_result_document(snapshot: Snapshot, path: Path) -> Dict[str, Any]:
    """Receipt printed by `cgc snapshot save --json`.

    Deliberately a summary rather than the manifest itself: the manifest can be
    megabytes, and the caller already knows where it was written.
    """
    return {
        "format": SNAPSHOT_SAVE_FORMAT,
        "format_version": SNAPSHOT_SAVE_FORMAT_VERSION,
        "name": snapshot.name,
        "path": Path(path).as_posix(),
        "created_at": snapshot.created_at,
        "cgc_version": snapshot.cgc_version,
        "context": dict(snapshot.context),
        "counts": snapshot.counts,
    }


def snapshot_list_document(entries: Sequence[SnapshotEntry]) -> Dict[str, Any]:
    return {
        "format": SNAPSHOT_LIST_FORMAT,
        "format_version": SNAPSHOT_LIST_FORMAT_VERSION,
        "count": len(entries),
        "snapshots": [
            {
                "name": entry.name,
                "path": entry.path.as_posix(),
                "created_at": entry.created_at,
                "cgc_version": entry.snapshot.cgc_version if entry.snapshot else "",
                "context": dict(entry.context),
                "counts": dict(entry.counts),
                **({"error": entry.error} if entry.error else {}),
            }
            for entry in entries
        ],
    }


def _shorten(keys: Sequence[str], limit: int = 3) -> str:
    shown = list(keys[:limit])
    text = ", ".join(shown)
    remaining = len(keys) - len(shown)
    if remaining > 0:
        text = f"{text} +{remaining} more"
    return text


def _change_note(record: Dict[str, Any]) -> str:
    """Human note for one ``changed`` row."""
    reason = record.get("reason")
    if reason == "target":
        return "target changed"
    keys = _shorten(record.get("changed_properties") or [])
    if reason == "moved":
        return f"moved, changed: {keys}" if keys else "moved"
    return f"changed: {keys}" if keys else "changed"


def render_diff_text(diff: Dict[str, Any], limit: Optional[int] = None) -> List[str]:
    """Render the diff document as plain ASCII lines (no Rich, no colour).

    ASCII is deliberate: on a non-UTF-8 Windows code page an arrow or em dash
    raises ``UnicodeEncodeError`` the moment output is redirected to a pipe.
    """
    base_name = diff["base"]["name"]
    rows: List[Tuple[str, str, str, str]] = []

    for record in diff["nodes"]["added"]:
        rows.append(("+", record.get("label", ""), record.get("display") or record["id"], "new"))
    for record in diff["nodes"]["removed"]:
        rows.append(("-", record.get("label", ""), record.get("display") or record["id"], "removed"))
    for record in diff["nodes"]["changed"]:
        rows.append(
            ("~", record.get("label", ""), record.get("display") or record["id"], _change_note(record))
        )
    for record in diff["edges"]["added"]:
        display = f"{record.get('source_display') or record.get('source')} -> {record.get('target_display') or record.get('target')}"
        rows.append(("+", record.get("type", ""), display, "new"))
    for record in diff["edges"]["removed"]:
        display = f"{record.get('source_display') or record.get('source')} -> {record.get('target_display') or record.get('target')}"
        rows.append(("-", record.get("type", ""), display, "removed"))
    for record in diff["edges"]["changed"]:
        after = record["after"]
        display = (
            f"{record.get('source_display') or record.get('source')} -> "
            f"{after.get('target_display') or after.get('target')}"
        )
        rows.append(("~", record.get("type", ""), display, _change_note(record)))

    truncated = 0
    if limit is not None and limit >= 0 and len(rows) > limit:
        truncated = len(rows) - limit
        rows = rows[:limit]

    lines = [f'cgc diff - comparing current index vs snapshot "{base_name}"', ""]
    # Both columns are sized from the data: a fixed width silently swallowed the
    # space before the display column as soon as a label ("HAS_PARAMETER")
    # outgrew it.
    kind_width = max([len(row[1]) for row in rows], default=10)
    width = max([len(row[2]) for row in rows], default=0)
    for sign, kind, display, note in rows:
        lines.append(f"{sign} {kind:<{kind_width}} {display:<{width}}  ({note})")
    if truncated:
        lines.append(f"... and {truncated} more changes (use --json for the full diff)")

    summary = diff["summary"]
    parts: List[str] = []
    for kind in ("nodes", "edges"):
        for bucket in ("added", "removed", "changed"):
            count = summary[kind][bucket]
            if count:
                parts.append(f"{count} {kind} {bucket}")
    if not parts:
        parts.append("no changes")
    lines.append(f"  {' | '.join(parts)}")
    return lines


def render_snapshot_list_text(entries: Sequence[SnapshotEntry]) -> List[str]:
    """Plain, column-aligned listing; ASCII so it survives redirected output."""
    if not entries:
        return ["No snapshots saved. Run `cgc snapshot save --name <name>` first."]
    header = ("NAME", "CREATED", "NODES", "EDGES", "CONTEXT")
    rows = [
        (
            entry.name,
            entry.created_at or "-",
            str(entry.counts["nodes"]) if entry.snapshot else "-",
            str(entry.counts["edges"]) if entry.snapshot else "-",
            str(entry.context.get("mode") or "-"),
        )
        for entry in entries
    ]
    widths = [
        max(len(header[index]), max((len(row[index]) for row in rows), default=0))
        for index in range(len(header))
    ]
    lines = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(header)).rstrip(),
        "  ".join("-" * width for width in widths).rstrip(),
    ]
    for entry, row in zip(entries, rows):
        line = "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip()
        if entry.error:
            line = f"{line}  [unreadable: {entry.error}]"
        lines.append(line)
    return lines
