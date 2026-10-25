"""Extract executable import() calls shared by JavaScript and TypeScript."""

_TYPE_ONLY_CONTEXTS = frozenset(
    {
        "type_query",
        "type_alias_declaration",
        "type_annotation",
        "type_arguments",
        "type_parameters",
        "interface_declaration",
    }
)


def extract_dynamic_import_call(parser, node):
    """Build one call record, or None for a TypeScript type-only import."""
    child, ancestor = node, node.parent
    while ancestor is not None:
        if ancestor.type in _TYPE_ONLY_CONTEXTS:
            return None
        # Cast/check operands execute; the type on their right does not.
        if ancestor.type in ("as_expression", "satisfies_expression"):
            if child != ancestor.named_child(0):
                return None
        child, ancestor = ancestor, ancestor.parent

    arguments = node.child_by_field_name("arguments")
    # Comments are named children too, including webpack chunk hints.
    specifier = None
    if arguments is not None:
        specifier = next(
            (
                argument
                for argument in arguments.named_children
                if argument.type != "comment"
            ),
            None,
        )
    return {
        "name": "import",
        "full_name": parser._get_node_text(node),
        "line_number": node.start_point[0] + 1,
        "args": [parser._get_node_text(specifier)] if specifier is not None else [],
        "inferred_obj_type": None,
        "context": parser._get_parent_context(node),
        "class_context": parser._get_parent_context(
            node, types=("class_declaration", "abstract_class_declaration")
        ),
        "lang": parser.language_name,
        "is_dependency": False,
        "call_kind": "dynamic_import",
    }
