#!/usr/bin/env python3
"""A syntactic analysis using Tree-sitter."""

import logging
import sys
from pathlib import Path

import tree_sitter
import tree_sitter_java

import jpamb


def main():

    # ============================================================
    # DEBUG MODE
    # ============================================================

    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        sys.argv = [
            sys.argv[0],
            "jpamb.cases.Simple.assertTrue:()V"
        ]

    # ============================================================
    # GET METHOD TO ANALYZE
    # ============================================================

    methodid = jpamb.getmethodid(
        "syntaxer",
        "1.0",
        "bests analyzers",
        ["syntactic", "python"],
        for_science=True,
    )

    # ============================================================
    # SET UP TREE-SITTER
    # ============================================================

    JAVA_LANGUAGE = tree_sitter.Language(
        tree_sitter_java.language()
    )

    parser = tree_sitter.Parser(JAVA_LANGUAGE)

    # ============================================================
    # LOGGING
    # ============================================================

    log = logging
    log.basicConfig(level=logging.DEBUG)

    # ============================================================
    # LOAD JPAMB SUITE
    # ============================================================

    suite, _ = jpamb.setup()

    # ============================================================
    # FIND JAVA SOURCE FILE
    # ============================================================

    srcfile = suite.sourcefile(
        methodid.classname
    ).relative_to(Path.cwd())

    # ============================================================
    # PARSE JAVA FILE
    # ============================================================

    with open(srcfile, "rb") as f:
        tree = parser.parse(f.read())

    simple_classname = str(methodid.classname.name)

    # ============================================================
    # FIND CLASS
    # ============================================================

    class_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        f"""
        (class_declaration
            name: (
                (identifier) @class-name
                (#eq? @class-name "{simple_classname}")
            )
        ) @class
        """,
    )

    for node in tree_sitter.QueryCursor(
        class_q
    ).captures(tree.root_node)["class"]:
        break

    else:
        log.error(
            f"Could not find a class of name "
            f"{simple_classname} in {srcfile}"
        )
        sys.exit(-1)

    # ============================================================
    # FIND METHOD
    # ============================================================

    method_name = methodid.extension.name

    method_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        f"""
        (method_declaration
            name: (
                (identifier) @method-name
                (#eq? @method-name "{method_name}")
            )
        ) @method
        """,
    )

    for snode in tree_sitter.QueryCursor(
        method_q
    ).captures(node)["method"]:

        p = snode.child_by_field_name("parameters")

        if not p:
            log.debug(
                f"Could not find parameters of {method_name}"
            )
            continue

        params = [
            c
            for c in p.children
            if c.type == "formal_parameter"
        ]

        # Make sure the number of parameters matches
        if len(params) != len(methodid.extension.params):
            continue

        # Check that parameters contain types
        for tn, t in zip(
            methodid.extension.params,
            params
        ):

            tp = t.child_by_field_name("type")

            if tp is None:
                break

            if tp.text is None:
                break

            # TODO:
            # Actually compare parameter types here.

        else:
            break

    else:
        log.warning(
            f"Could not find a method of name "
            f"{method_name} in {simple_classname}"
        )
        sys.exit(-1)

    # ============================================================
    # GET METHOD BODY
    # ============================================================

    body = snode.child_by_field_name("body")

    assert body
    assert body.text

    # ============================================================
    # VARIABLES USED LATER FOR "OK"
    # ============================================================

    safe_condition = True
    unsafe_condition = False

    # ============================================================
    # ASSERTION ERROR
    # ============================================================

    assert_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (block
            (assert_statement
                (primary_expression) @assert_true
                (#eq? @assert_true "true")
            )
        )

        (block
            (assert_statement
                (primary_expression) @assert_false
                (#eq? @assert_false "false")
            )
        )

        (block
            (assert_statement
                (binary_expression) @assert_statement
            )
        )
        """
    )

    assert_captures = tree_sitter.QueryCursor(
        assert_q
    ).captures(body)

    assert_true_found = any(
        capture_name == "assert_true"
        for capture_name, _ in assert_captures.items()
    )

    assert_false_found = any(
        capture_name == "assert_false"
        for capture_name, _ in assert_captures.items()
    )

    assert_statement_found = any(
        capture_name == "assert_statement"
        for capture_name, _ in assert_captures.items()
    )

    if assert_false_found:

        print(
            "assertion error;assert_false_found"
        )

        safe_condition = False

    elif assert_statement_found:

        print(
            "assertion error;assert_statement_found"
        )

        safe_condition = False

    elif assert_true_found:

        print(
            "assertion error;assert_true_found"
        )

    else:

        print(
            "assertion error;assert_statement_not_found"
        )

        safe_condition = False

    # ============================================================
    # DIVIDE BY ZERO
    # ============================================================

    divide_by_zero_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (binary_expression
            operator: "/"
            right: (primary_expression) @right_zero
            (#eq? @right_zero "0")
        )

        (binary_expression
            operator: "/"
            right: [
                (parenthesized_expression)
                (identifier)
            ] @maybe_right_zero
        )

        (binary_expression
            operator: "/"
            right: (primary_expression) @not_right_zero
            (#not-eq? @not_right_zero "0")
        )
        """
    )

    division_captures = tree_sitter.QueryCursor(
        divide_by_zero_q
    ).captures(body)

    divide_by_zero_found = any(
        capture_name == "right_zero"
        for capture_name, _ in division_captures.items()
    )

    maybe_divide_by_zero_found = any(
        capture_name == "maybe_right_zero"
        for capture_name, _ in division_captures.items()
    )

    not_divide_by_zero_found = any(
        capture_name == "not_right_zero"
        for capture_name, _ in division_captures.items()
    )

    if divide_by_zero_found:

        print(
            "divide by zero;right_zero"
        )

        safe_condition = False

    elif maybe_divide_by_zero_found:

        print(
            "divide by zero;maybe_right_zero"
        )

        safe_condition = False

    elif not_divide_by_zero_found:

        print(
            "divide by zero;not_right_zero"
        )

    else:

        print(
            "divide by zero;not_found"
        )

    # ============================================================
    # NON-TERMINATION / INFINITE LOOP
    # ============================================================

    infinite_loop_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (block
            (while_statement
                condition: (
                    parenthesized_expression
                    (expression) @while_true
                )
            )
        )
        (#eq? @while_true "true")

        (block
            (while_statement) @while_statement
        )
        """
    )

    loop_captures = tree_sitter.QueryCursor(
        infinite_loop_q
    ).captures(body)

    while_true_found = any(
        capture_name == "while_true"
        for capture_name, _ in loop_captures.items()
    )

    while_statement_found = any(
        capture_name == "while_statement"
        for capture_name, _ in loop_captures.items()
    )

    if while_true_found:

        print(
            "*;while_true_found"
        )

        unsafe_condition = True
        safe_condition = False

    elif while_statement_found:

        print(
            "*;while_statement"
        )

        safe_condition = False

    else:

        print(
            "*;while_statement_not_found"
        )

    # ============================================================
    # NULL POINTER
    # ============================================================

    null_pointer_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (variable_declarator
            dimensions: (_)
            value: (_) @val
            (#eq? @val null)
        )
        @empty_array_declaration

        (block
            (statement
                (variable_declarator
                    dimensions: (_)
                ) @arrays_present
            )
        )
        """
    )

    null_captures = tree_sitter.QueryCursor(
        null_pointer_q
    ).captures(body)

    empty_array_declaration = any(
        capture_name == "empty_array_declaration"
        for capture_name, _ in null_captures.items()
    )

    arrays_present = any(
        capture_name == "arrays_present"
        for capture_name, _ in null_captures.items()
    )

    if empty_array_declaration:

        print(
            "null pointer;empty_array_declaration"
        )

        unsafe_condition = True
        safe_condition = False

    elif arrays_present:

        print(
            "null pointer;arrays_present"
        )

        safe_condition = False

    else:

        print(
            "null pointer;array_declaration_not_found"
        )

    # ============================================================
    # OUT OF BOUNDS
    # ============================================================

    out_of_bounds_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (array_access) @array_access

        (array_access
            index: (decimal_integer_literal) @constant_index
        )

        (array_access
            index: (identifier) @variable_index
        )
        """
    )

    out_of_bounds_captures = tree_sitter.QueryCursor(
        out_of_bounds_q
    ).captures(body)

    constant_index_found = any(
        capture_name == "constant_index"
        for capture_name, _ in out_of_bounds_captures.items()
    )

    variable_index_found = any(
        capture_name == "variable_index"
        for capture_name, _ in out_of_bounds_captures.items()
    )

    array_access_found = any(
        capture_name == "array_access"
        for capture_name, _ in out_of_bounds_captures.items()
    )

    if constant_index_found:
        print("out of bounds;constant_index")

    elif variable_index_found:
        print("out of bounds;variable_index")

    elif array_access_found:
        print("out of bounds;other_array_access")

    else:
        print("out of bounds;no_array_access")

    # ============================================================
    # OK
    # ============================================================

    # Strong syntactic evidence that something can go wrong
    definite_problem = (
        assert_false_found
        or divide_by_zero_found
        or while_true_found
        or empty_array_declaration
    )

    # We saw something potentially dangerous, but syntax alone cannot tell us whether it will actually fail
    possible_problem = (
        assert_statement_found
        or maybe_divide_by_zero_found
        or while_statement_found
        or array_access_found
    )

    if definite_problem:
        print("ok;definite_problem")

    elif possible_problem:
        print("ok;possible_problem")

    else:
        print("ok;no_obvious_problem")

    # ============================================================
    # QUERIES WE DO NOT ANALYZE YET
    # ============================================================

    for q in jpamb.QUERIES:

        if q not in [
            "assertion error",
            "divide by zero",
            "ok",
            "*",
            "null pointer",
            "out of bounds",
        ]:

            print(f"{q};skip")

    sys.exit(0)


if __name__ == "__main__":
    main()