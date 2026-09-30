"""Snapshot/diff logic behind `cgc snapshot save` and `cgc diff` (#1312).

These tests build snapshots directly instead of indexing a repository: they
cover identity, pairing, documents and rendering — everything that must hold
regardless of which graph backend produced the rows.
"""
import json

import pytest

from codegraphcontext.core import graph_snapshot as gs


# --------------------------------------------------------------------------- helpers


def _node(label, props):
    identity, primary = gs.identity_of([label], props)
    return {
        "id": identity,
        "label": primary,
        "display": gs.display_of(primary, props),
        "path": props.get("path"),
        "digest": gs.digest_properties(props),
        "properties": dict(props),
    }


def _edge(rel_type, source, target, props=None):
    properties = dict(props or {})
    return {
        "id": f"{source['id']} -[{rel_type}]-> {target['id']}",
        "type": rel_type,
        "source": source["id"],
        "target": target["id"],
        "source_label": source["label"],
        "target_label": target["label"],
        "source_display": source["display"],
        "target_display": target["display"],
        "digest": gs.digest_properties(properties),
        "properties": properties,
    }


def _snapshot(name, nodes, edges, created_at="2026-01-01T00:00:00Z"):
    return gs.Snapshot(
        name=name,
        created_at=created_at,
        context={"mode": "global"},
        nodes=list(nodes),
        edges=list(edges),
    )


def _function(name, line, *, path="repo/app.py", uid=None, extra=None):
    props = {"name": name, "path": path, "line_number": line}
    if uid is not None:
        props["uid"] = uid
    if extra:
        props.update(extra)
    return _node("Function", props)


def _param(name, function_line, *, path="repo/app.py"):
    return _node(
        "Parameter",
        {"name": name, "path": path, "function_line_number": function_line, "uid": f"{name}{path}{function_line}0"},
    )


def _file(path="repo/app.py"):
    return _node("File", {"path": path, "name": path.rsplit("/", 1)[-1]})


# --------------------------------------------------------------------------- names


@pytest.mark.parametrize(
    "name",
    ["", "-leading-dash", "has space", "slash/name", "../escape", "a" * 65, "semi;colon"],
)
def test_unsafe_snapshot_names_are_usage_errors(name):
    with pytest.raises(gs.SnapshotUsageError):
        gs.validate_name(name)


@pytest.mark.parametrize("name", ["base", "before-refactor", "v1.2", "ci_42", "a"])
def test_safe_snapshot_names_are_accepted(name):
    assert gs.validate_name(name) == name


def test_default_snapshot_name_is_a_valid_name():
    name = gs.default_snapshot_name()

    assert gs.validate_name(name) == name
    assert name.startswith("snapshot-")


# --------------------------------------------------------------------------- storage


def test_snapshot_survives_a_disk_roundtrip(tmp_path):
    snapshot = _snapshot("base", [_function("run", 4)], [])
    path = gs.save_snapshot(snapshot, tmp_path / "base.json")

    loaded = gs.load_snapshot(path)

    assert loaded.name == "base"
    assert loaded.format_version == gs.SNAPSHOT_FORMAT_VERSION
    assert loaded.nodes == snapshot.nodes
    assert loaded.counts == {"nodes": 1, "edges": 0}


def test_saving_over_an_existing_name_needs_force(tmp_path):
    snapshot = _snapshot("base", [], [])
    gs.save_snapshot(snapshot, tmp_path / "base.json")

    with pytest.raises(gs.SnapshotExistsError):
        gs.save_snapshot(snapshot, tmp_path / "base.json")

    gs.save_snapshot(snapshot, tmp_path / "base.json", force=True)  # no raise


def test_list_snapshots_is_newest_first_and_tolerates_corrupt_files(tmp_path):
    gs.save_snapshot(_snapshot("older", [], []), tmp_path / "older.json")
    gs.save_snapshot(_snapshot("newer", [], []), tmp_path / "newer.json", force=True)
    # A file that is not a snapshot at all must not sink the whole listing.
    (tmp_path / "garbage.json").write_text("{not json", encoding="utf-8")

    # created_at drives the order, so pin it deterministically.
    older = json.loads((tmp_path / "older.json").read_text(encoding="utf-8"))
    older["created_at"] = "2020-01-01T00:00:00Z"
    (tmp_path / "older.json").write_text(json.dumps(older), encoding="utf-8")

    entries = gs.list_snapshots(tmp_path)

    assert [entry.name for entry in entries][:2] == ["newer", "older"]
    garbage = [entry for entry in entries if entry.name == "garbage"]
    assert garbage and garbage[0].snapshot is None and garbage[0].error


# --------------------------------------------------------------------------- identity


def test_identity_prefers_the_persisted_uid():
    identity, label = gs.identity_of(["Function"], {"uid": "runrepo/app.py40", "name": "run"})
    assert (identity, label) == ("Function:uid:runrepo/app.py40", "Function")


def test_identity_falls_back_to_the_synthesised_uid():
    identity, _ = gs.identity_of(
        ["Function"], {"name": "run", "path": "repo/app.py", "line_number": 4}
    )
    assert identity.startswith("Function:uid:")
    assert "run" in identity and "repo/app.py" in identity


def test_identity_of_a_file_is_its_path():
    identity, label = gs.identity_of(["File"], {"path": "repo/app.py", "name": "app.py"})
    assert (identity, label) == ("File:path:repo/app.py", "File")


def test_display_qualifies_by_context_but_not_with_itself():
    assert gs.display_of("Function", {"name": "run", "context": "app"}) == "app.run"
    assert gs.display_of("Function", {"name": "run", "context": "run"}) == "run"
    assert gs.display_of("Function", {"name": "run", "context": "<module>"}) == "run"
    assert gs.display_of("File", {"path": "repo/app.py", "name": "app.py"}) == "repo/app.py"


def test_indexed_at_never_reaches_a_snapshot():
    props = gs._clean_props({"name": "run", "indexed_at": "2026-01-01T00:00:00Z", "line_number": 4})
    assert "indexed_at" not in props
    assert props["line_number"] == 4


# --------------------------------------------------------------------------- build


class _FakeSession:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **kwargs):
        if query == gs.NODE_QUERY:
            return self._nodes
        if query == gs.EDGE_QUERY:
            return self._edges
        raise AssertionError(f"unexpected query: {query}")


class _FakeDriver:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def session(self):
        return _FakeSession(self._nodes, self._edges)


class _FakeDBManager:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def get_driver(self, graph_name=None):
        return _FakeDriver(self._nodes, self._edges)


def test_build_snapshot_reads_nodes_and_edges():
    file_node = {"path": "repo/app.py", "name": "app.py"}
    function = {"uid": "runrepo/app.py40", "name": "run", "path": "repo/app.py", "line_number": 4}
    db = _FakeDBManager(
        nodes=[
            {"labels": ["File"], "n": file_node},
            {"labels": ["Function"], "n": function},
        ],
        edges=[
            {
                "rel_type": "CONTAINS",
                "source_labels": ["File"],
                "target_labels": ["Function"],
                "a": file_node,
                "b": function,
                "r": {},
            }
        ],
    )

    snapshot = gs.build_snapshot(db, name="base", context={"mode": "global"})

    assert snapshot.counts == {"nodes": 2, "edges": 1}
    assert [node["id"] for node in snapshot.nodes] == [
        "File:path:repo/app.py",
        "Function:uid:runrepo/app.py40",
    ]
    assert snapshot.context == {"mode": "global"}


# --------------------------------------------------------------------------- diff


def test_identical_snapshots_diff_to_nothing():
    nodes = [_function("run", 4, uid="runrepo/app.py40")]
    diff = gs.diff_snapshots(_snapshot("base", nodes, []), _snapshot("current", nodes, []))

    assert diff["summary"]["total"] == 0
    assert diff["summary"]["nodes"] == {"added": 0, "removed": 0, "changed": 0}


def test_added_and_removed_nodes_are_reported():
    base = _snapshot("base", [_function("run", 4, uid="runrepo/app.py40")], [])
    current = _snapshot(
        "current",
        [
            _function("run", 4, uid="runrepo/app.py40"),
            _function("fresh", 9, uid="freshrepo/app.py90"),
        ],
        [],
    )

    diff = gs.diff_snapshots(base, current)

    assert [node["properties"]["name"] for node in diff["nodes"]["added"]] == ["fresh"]
    assert diff["nodes"]["removed"] == []
    assert diff["summary"]["nodes"]["added"] == 1


def test_a_line_shift_reads_as_a_move_not_churn():
    """The uid embeds line_number, so typing a line above a function re-keys it."""
    base = _snapshot("base", [_function("run", 4, uid="runrepo/app.py40")], [])
    current = _snapshot("current", [_function("run", 5, uid="runrepo/app.py50")], [])

    diff = gs.diff_snapshots(base, current)

    assert diff["nodes"]["added"] == [] and diff["nodes"]["removed"] == []
    assert [entry["reason"] for entry in diff["nodes"]["changed"]] == ["moved"]
    assert "line_number" in diff["nodes"]["changed"][0]["changed_properties"]


def test_a_rename_is_still_an_add_and_a_remove():
    base = _snapshot("base", [_function("run", 4, uid="runrepo/app.py40")], [])
    current = _snapshot("current", [_function("execute", 4, uid="executerepo/app.py40")], [])

    diff = gs.diff_snapshots(base, current)

    assert len(diff["nodes"]["added"]) == 1
    assert len(diff["nodes"]["removed"]) == 1
    assert diff["nodes"]["changed"] == []


def test_two_candidates_sharing_a_signature_are_not_guessed():
    """Two `run` definitions in one file: pairing them would be a coin toss."""
    base = _snapshot(
        "base",
        [_function("run", 4, uid="runrepo/app.py40"), _function("run", 9, uid="runrepo/app.py90")],
        [],
    )
    current = _snapshot(
        "current",
        [_function("run", 5, uid="runrepo/app.py50"), _function("run", 10, uid="runrepo/app.py100")],
        [],
    )

    diff = gs.diff_snapshots(base, current)

    assert len(diff["nodes"]["added"]) == 2
    assert len(diff["nodes"]["removed"]) == 2
    assert diff["nodes"]["changed"] == []


def test_owners_qualify_ambiguous_node_names():
    file_node = _file()
    base_param = _param("amount", 4)
    current_param = _param("amount", 5)
    base_fn = _function("pay", 4, uid="payrepo/app.py40")
    current_fn = _function("pay", 5, uid="payrepo/app.py50")

    base = _snapshot(
        "base",
        [file_node, base_fn, base_param],
        [
            _edge("CONTAINS", file_node, base_fn),
            _edge("HAS_PARAMETER", base_fn, base_param),
        ],
    )
    current = _snapshot(
        "current",
        [_file(), current_fn, current_param],
        [
            _edge("CONTAINS", _file(), current_fn),
            _edge("HAS_PARAMETER", current_fn, current_param),
        ],
    )

    diff = gs.diff_snapshots(base, current)

    changed = {entry["display"] for entry in diff["nodes"]["changed"]}
    assert "pay.amount" in changed


def test_a_call_edge_does_not_qualify_its_callee():
    caller = _function("pay", 4, uid="payrepo/app.py40")
    callee = _function("validate", 9, uid="validaterepo/app.py90")

    diff = gs.diff_snapshots(
        _snapshot("base", [caller, callee], []),
        _snapshot("current", [caller, callee], [_edge("CALLS", caller, callee)]),
    )

    assert [entry["display"] for entry in diff["nodes"]["added"]] == []
    assert diff["edges"]["added"] and diff["edges"]["added"][0]["target_display"] == "validate"


def test_moving_both_endpoints_leaves_the_edge_alone():
    """An edge id embeds both uids, so a line shift must not look like churn."""
    file_node = _file()
    base_fn = _function("run", 4, uid="runrepo/app.py40")
    current_fn = _function("run", 5, uid="runrepo/app.py50")

    base = _snapshot("base", [file_node, base_fn], [_edge("CONTAINS", file_node, base_fn)])
    current = _snapshot(
        "current", [_file(), current_fn], [_edge("CONTAINS", _file(), current_fn)]
    )

    diff = gs.diff_snapshots(base, current)

    assert diff["edges"] == {"added": [], "removed": [], "changed": []}


def test_a_call_that_switched_target_is_folded_into_one_row():
    caller = _function("pay", 4, uid="payrepo/app.py40")
    old = _function("validate", 9, uid="validaterepo/app.py90")
    new = _function("score", 14, uid="scorerepo/app.py140")

    base = _snapshot("base", [caller, old, new], [_edge("CALLS", caller, old)])
    current = _snapshot(
        "current",
        [caller, old, new],
        [_edge("CALLS", caller, new, {"line_number": 4})],
    )

    diff = gs.diff_snapshots(base, current)

    assert diff["edges"]["added"] == [] and diff["edges"]["removed"] == []
    assert [entry["reason"] for entry in diff["edges"]["changed"]] == ["target"]
    assert diff["edges"]["changed"][0]["before"]["target"] == old["id"]


def test_gaining_and_losing_children_is_not_a_retarget():
    """A file that gained `refund` while losing `refund_old` gained and lost
    a child; folding that into "target changed" would invent a relationship."""
    file_node = _file()
    old_child = _function("refund_old", 4, uid="refund_oldrepo/app.py40")
    new_child = _function("refund", 4, uid="refundrepo/app.py40")

    base = _snapshot("base", [file_node, old_child], [_edge("CONTAINS", file_node, old_child)])
    current = _snapshot(
        "current", [_file(), new_child], [_edge("CONTAINS", _file(), new_child)]
    )

    diff = gs.diff_snapshots(base, current)

    assert diff["edges"]["changed"] == []
    assert len(diff["edges"]["added"]) == len(diff["edges"]["removed"]) == 1


def test_a_removed_source_is_a_removal_not_a_retarget():
    caller = _function("pay", 4, uid="payrepo/app.py40")
    callee = _function("validate", 9, uid="validaterepo/app.py90")

    base = _snapshot("base", [caller, callee], [_edge("CALLS", caller, callee)])
    current = _snapshot("current", [callee], [])

    diff = gs.diff_snapshots(base, current)

    assert diff["edges"]["changed"] == []
    assert len(diff["edges"]["removed"]) == 1


# --------------------------------------------------------------------------- documents


def test_diff_document_summary_matches_its_buckets():
    base = _snapshot("base", [_function("gone", 4, uid="gonerepo/app.py40")], [])
    current = _snapshot("current", [_function("fresh", 4, uid="freshrepo/app.py40")], [])

    diff = gs.diff_snapshots(base, current)

    assert diff["format"] == gs.DIFF_FORMAT
    assert diff["format_version"] == gs.DIFF_FORMAT_VERSION
    totals = sum(diff["summary"][kind][bucket] for kind in ("nodes", "edges") for bucket in ("added", "removed", "changed"))
    assert totals == diff["summary"]["total"]
    assert diff["base"]["name"] == "base"


def test_dump_json_stays_ascii_and_round_trips():
    payload = {"name": "café", "note": "-> + ~"}

    text = gs.dump_json(payload)

    assert text.isascii()
    assert json.loads(text) == payload


def test_save_receipt_summarises_instead_of_echoing_the_manifest(tmp_path):
    snapshot = _snapshot("base", [_function("run", 4)], [])

    document = gs.save_result_document(snapshot, tmp_path / "base.json")

    assert document["format"] == gs.SNAPSHOT_SAVE_FORMAT
    assert document["name"] == "base"
    assert document["counts"] == {"nodes": 1, "edges": 0}
    assert "nodes" not in document  # the manifest itself is not the receipt


def test_snapshot_list_document_lists_names_and_counts(tmp_path):
    gs.save_snapshot(_snapshot("base", [_function("run", 4)], []), tmp_path / "base.json")

    document = gs.snapshot_list_document(gs.list_snapshots(tmp_path))

    assert document["format"] == gs.SNAPSHOT_LIST_FORMAT
    assert [entry["name"] for entry in document["snapshots"]] == ["base"]
    assert document["snapshots"][0]["counts"]["nodes"] == 1


# --------------------------------------------------------------------------- rendering


def _rich_diff():
    """A diff with enough shapes to exercise every rendered row."""
    file_node = _file()
    base_fn = _function("pay", 4, uid="payrepo/app.py40")
    current_fn = _function("pay", 5, uid="payrepo/app.py50")
    added_fn = _function("refund", 9, uid="refundrepo/app.py90")
    base_param = _param("amount", 4)
    current_param = _param("amount", 5)

    base = _snapshot(
        "base",
        [file_node, base_fn, base_param],
        [
            _edge("CONTAINS", file_node, base_fn),
            _edge("HAS_PARAMETER", base_fn, base_param),
        ],
    )
    current = _snapshot(
        "current",
        [_file(), current_fn, current_param, added_fn],
        [
            _edge("CONTAINS", _file(), current_fn),
            _edge("HAS_PARAMETER", current_fn, current_param),
            _edge("CONTAINS", _file(), added_fn),
            _edge("HAS_PARAMETER", added_fn, _param("amount", 9)),
        ],
    )
    return gs.diff_snapshots(base, current)


def test_rendered_output_is_pure_ascii():
    lines = gs.render_diff_text(_rich_diff())

    text = "\n".join(lines)
    assert text.isascii(), "non-ASCII leaks break redirected output on cp1252"
    assert "->" in text


def test_rendered_labels_are_never_glued_to_their_display():
    text = "\n".join(gs.render_diff_text(_rich_diff()))

    for marker in ("HAS_PARAMETER", "CONTAINS", "Function", "Parameter"):
        assert f"{marker} " in text, f"{marker} collided with the display column"


def test_rendered_summary_counts_every_bucket():
    text = "\n".join(gs.render_diff_text(_rich_diff()))

    assert "nodes added" in text
    assert "edges added" in text
    assert "nodes changed" in text


def _change_rows(lines):
    """Just the +/-/~ rows, skipping the header and its blank line."""
    return [line for line in lines if line[:1] in {"+", "-", "~"}]


def test_render_limit_truncates_and_says_so():
    lines = gs.render_diff_text(_rich_diff(), limit=2)

    assert len(_change_rows(lines)) == 2
    assert any("more changes" in line for line in lines)


def test_render_reports_an_empty_diff_as_no_changes():
    nodes = [_function("run", 4, uid="runrepo/app.py40")]
    diff = gs.diff_snapshots(_snapshot("base", nodes, []), _snapshot("current", nodes, []))

    lines = gs.render_diff_text(diff)

    assert any("no changes" in line for line in lines)
    assert _change_rows(lines) == []


def test_rendered_rows_carry_a_human_note():
    text = "\n".join(gs.render_diff_text(_rich_diff()))

    assert "(new)" in text
    assert "(moved" in text
