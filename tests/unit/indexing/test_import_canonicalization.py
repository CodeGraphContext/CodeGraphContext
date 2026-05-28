from codegraphcontext.tools.indexing.persistence.writer import _canonical_import_rows


def test_canonical_import_rows_choose_lowest_line_per_module():
    rows = [
        {
            "name": "indoc",
            "full_import_name": "use indoc::indoc;",
            "imported_name": "indoc",
            "alias": "",
            "line_number": 124,
        },
        {
            "name": "indoc",
            "full_import_name": "use indoc::indoc;",
            "imported_name": "indoc",
            "alias": "",
            "line_number": 1,
        },
        {
            "name": "IssueCode",
            "full_import_name": "use crate::code::IssueCode;",
            "imported_name": "IssueCode",
            "alias": "",
            "line_number": 51,
        },
    ]

    assert _canonical_import_rows(rows, ("name",)) == [
        {
            "name": "IssueCode",
            "full_import_name": "use crate::code::IssueCode;",
            "imported_name": "IssueCode",
            "alias": "",
            "line_number": 51,
        },
        {
            "name": "indoc",
            "full_import_name": "use indoc::indoc;",
            "imported_name": "indoc",
            "alias": "",
            "line_number": 1,
        },
    ]
