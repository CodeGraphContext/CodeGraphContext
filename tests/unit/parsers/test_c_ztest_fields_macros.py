"""C: Zephyr ZTEST functions, struct field accesses and macro uses.

ZTEST(suite, name) { ... } hides the function declarator, so tree-sitter reads
an expression statement followed by a bare compound statement; the test bodies
were not functions and their calls had no caller. Field accesses and macro
invocations were not recorded at all, so "what writes conn->x.mss_found" or
"who uses conn_mss()" could only be answered by grep.
"""

from unittest.mock import MagicMock

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.languages.c import CTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _parser():
    manager = get_tree_sitter_manager()
    w = MagicMock()
    w.language_name = "c"
    w.language = manager.get_language_safe("c")
    w.parser = manager.create_parser("c")
    return CTreeSitterParser(w)


SOURCE = """#include "tcp_private.h"
#define conn_mss(_conn) ((_conn)->recv_options.mss_found ? (_conn)->recv_options.mss : 536)
#define SET_N(_o) ((_o)->n = 1)

static void parse(struct tcp_options *opts)
{
	opts->mss_found = false;
	opts->mss += 4;
	(opts->count)++;
	use(opts->window);
}

static void in(struct tcp *conn)
{
	parse(&conn->recv_options);
	send(conn_mss(conn));
}

ZTEST(lib_suite, test_one)
{
	ctx.count++;
	check(&ctx);
}

#ifdef CONFIG_X
ZTEST_F(fsuite, test_two)
{
	fixture->n = 1;
}
#endif

ZTEST_SUITE(lib_suite, NULL, NULL, NULL, NULL, NULL);

ZTEST_BENCHMARK(bench_suite, bench_one, 10, NULL, NULL)
{
	run();
}

START_TEST(test_single)
{
}

void __soc_ram_code ramcode_reset(void)
{
	flush();
}

SCSI_CMD_STRUCT(TEST_UNIT_READY) {
	uint8_t opcode;
} __packed;

PAIR_STRUCT(a, b) {
	int x;
};

ZTEST(lib_suite, test_stray_semicolon)
{
	int y = 1;
	verify(&y);
};
"""


def _parse(tmp_path):
    f = tmp_path / "t.c"
    f.write_text(SOURCE)
    return _parser().parse(f, index_source=True)


def test_macro_defined_bodies_become_functions(tmp_path):
    data = _parse(tmp_path)
    tests = {f["name"]: f for f in data["functions"] if f.get("defined_by_macro")}
    # Found by shape, not by name; ZTEST_SUITE has no body.
    assert set(tests) == {"test_one", "test_two", "bench_one", "test_single", "test_stray_semicolon"}
    assert tests["test_single"]["defined_by_macro"] == "START_TEST"  # one argument: parsed as a definition
    # An attribute macro before the name misparses the same way; (void) marks it.
    plain = {f["name"]: f for f in data["functions"] if not f.get("defined_by_macro")}
    assert plain["ramcode_reset"]["line_number"] == SOURCE.splitlines().index("void __soc_ram_code ramcode_reset(void)") + 1
    assert "void" not in plain
    # Struct heads end "};" or "} __packed;" and are not functions.
    assert not {"TEST_UNIT_READY", "b"} & {f["name"] for f in data["functions"]}
    assert tests["test_one"]["line_number"] == 19
    assert tests["test_one"]["end_line"] == 23
    assert tests["test_two"]["macro_args"] == ["fsuite", "test_two"]
    assert tests["bench_one"]["defined_by_macro"] == "ZTEST_BENCHMARK"  # name is the 2nd argument
    assert tests["test_two"]["decorators"] == ["ZTEST_F"]
    assert "check(&ctx);" in tests["test_one"]["source"]


def test_calls_inside_ztest_are_attributed_to_the_test(tmp_path):
    calls = {c["name"]: c for c in _parse(tmp_path)["function_calls"]}
    assert calls["check"]["context"] == ("test_one", "function_definition", 19)


def test_field_access_kinds(tmp_path):
    rows = {(r.get("function") or r.get("macro"), r["field"], r["access"]): r["lines"]
            for r in _parse(tmp_path)["field_accesses"]}
    assert rows[("parse", "mss_found", "write")] == [7]
    assert rows[("parse", "mss", "write")] == [8]  # compound assignment
    assert rows[("parse", "count", "write")] == [9]  # ++ through parentheses
    assert rows[("parse", "window", "read")] == [10]
    assert rows[("in", "recv_options", "address")] == [15]
    assert rows[("test_one", "count", "write")] == [21]
    assert rows[("test_two", "n", "write")] == [28]


def test_macro_body_field_accesses(tmp_path):
    rows = {(r["macro"], r["field"], r["access"]) for r in _parse(tmp_path)["field_accesses"] if r.get("macro")}
    assert ("conn_mss", "mss_found", "read") in rows
    assert ("conn_mss", "recv_options", "read") in rows
    assert ("SET_N", "n", "write") in rows


def test_numbers_are_not_fields():
    from codegraphcontext.tools.languages.c import MACRO_FIELD
    assert [m.group(1) for m in MACRO_FIELD.finditer("(1.5f * x.y) + s->z")] == ["y", "z"]


def test_writer_links_macro_uses_and_fields():
    session = MagicMock()
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    db = MagicMock()
    db.get_backend_type.return_value = "falkordb"
    files = [
        {
            "path": "/r/a.c", "lang": "c", "imports": [{"name": "inc/b.h"}],
            "macros": [],
            "function_calls": [
                {"name": "conn_mss", "line_number": 9, "context": ("in", "function_definition", 5)},
                {"name": "AMBIG", "line_number": 10, "context": ("in", "function_definition", 5)},
                {"name": "conn_mss", "line_number": 1, "context": (None, None, None)},  # file scope
            ],
            "field_accesses": [
                {"function": "in", "function_line": 5, "field": "mss_found", "access": "write", "lines": [7]},
            ],
        },
        {"path": "/r/inc/b.h", "lang": "c", "macros": [{"name": "conn_mss", "line_number": 3}],
         "field_accesses": [{"macro": "conn_mss", "macro_line": 3, "field": "mss_found", "access": "read", "lines": [3]}]},
        {"path": "/r/c.h", "lang": "c", "macros": [{"name": "conn_mss", "line_number": 8}]},
        *[{"path": f"/r/x{i}.h", "lang": "c", "macros": [{"name": "AMBIG", "line_number": 1}]} for i in range(4)],
    ]
    GraphWriter(driver, db).write_c_use_links(files)

    batches = {}
    for call in session.run.call_args_list:
        query = call.args[0]
        for rel in ("USES_MACRO", "WRITES_FIELD", "READS_FIELD"):
            if f":{rel}]" in query:
                batches.setdefault(rel, []).extend(call.kwargs["batch"])
    # Resolved through the include, not to the other conn_mss; AMBIG (4 defs) skipped.
    assert batches["USES_MACRO"] == [{
        "fn": "in", "path": "/r/a.c", "fn_line": 5, "macro": "conn_mss",
        "macro_path": "/r/inc/b.h", "macro_line": 3, "lines": [9],
    }]
    assert batches["WRITES_FIELD"][0]["field"] == "mss_found"
    assert batches["READS_FIELD"][0]["macro"] == "conn_mss"


def test_headers_parsed_as_cpp_get_field_accesses(tmp_path):
    # cgc maps .h to the C++ parser; conn_mss lives in tcp_private.h.
    from codegraphcontext.tools.languages.cpp import CppTreeSitterParser
    manager = get_tree_sitter_manager()
    w = MagicMock()
    w.language_name = "cpp"
    w.language = manager.get_language_safe("cpp")
    w.parser = manager.create_parser("cpp")
    f = tmp_path / "t.h"
    f.write_text(SOURCE.split("ZTEST(")[0])
    rows = {(r.get("function") or r.get("macro"), r["field"], r["access"])
            for r in CppTreeSitterParser(w).parse(f)["field_accesses"]}
    assert ("conn_mss", "mss_found", "read") in rows
    assert ("parse", "mss_found", "write") in rows
    assert ("in", "recv_options", "address") in rows
