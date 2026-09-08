#!/usr/bin/env python3
"""A very stupid syntactic analysis, that only checks for assertion errors."""

import logging
import sys
from pathlib import Path

import tree_sitter
import tree_sitter_java

import jpamb


def main():
    if (sys.argv[1] == "--debug"):
        sys.argv = [sys.argv[0], "jpamb.cases.Simple.assertTrue:()V"]

    methodid = jpamb.getmethodid(
        "syntaxer",
        "1.0",
        "SteGiro",
        ["syntactic", "python"],
        for_science=True,
    )

    JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
    parser = tree_sitter.Parser(JAVA_LANGUAGE)

    log = logging
    log.basicConfig(level=logging.DEBUG)

    suite, _ = jpamb.setup()

    srcfile = suite.sourcefile(methodid.classname).relative_to(Path.cwd())

    with open(srcfile, "rb") as f:
        tree = parser.parse(f.read())

    simple_classname = str(methodid.classname.name)


    # To figure out how to write these you can consult the
    # https://tree-sitter.github.io/tree-sitter/playground
    class_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        f"""
        (class_declaration 
            name: ((identifier) @class-name 
                   (#eq? @class-name "{simple_classname}"))) @class
    """,
    )

    for node in tree_sitter.QueryCursor(class_q).captures(tree.root_node)["class"]:
        break
    else:
        log.error(f"could not find a class of name {simple_classname} in {srcfile}")

        sys.exit(-1)

    # log.debug("Found class %s", node.range)

    method_name = methodid.extension.name


    method_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        f"""
        (method_declaration name: 
          ((identifier) @method-name (#eq? @method-name "{method_name}"))
        ) @method
    """,
    )

    for snode in tree_sitter.QueryCursor(method_q).captures(node)["method"]:
        if not (p := snode.child_by_field_name("parameters")):
            log.debug(f"Could not find parameteres of {method_name}")
            continue

        params = [c for c in p.children if c.type == "formal_parameter"]

        if len(params) != len(methodid.extension.params):
            continue

        # log.debug(methodid.extension.params)
        # log.debug(params)

        for tn, t in zip(methodid.extension.params, params):
            if (tp := t.child_by_field_name("type")) is None:
                break

            if tp.text is None:
                break

            # todo check for type.
        else:
            break
    else:
        log.warning(
            f"could not find a method of name {method_name} in {simple_classname}"
        )
        sys.exit(-1)

    # log.debug("Found method %s %s", method_name, node.range)

    body = snode.child_by_field_name("body")
    assert body and body.text
    # for t in body.text.splitlines():
    #     log.debug("line: %s", t.decode())

    safe_condition = True
    unsafe_condition = False

    # check for assertion error logic
    assert_q = tree_sitter.Query(JAVA_LANGUAGE, """(block
      (assert_statement
        (primary_expression) @assert_true
        (#eq? @assert_true "true")))

    (block
      (assert_statement
        (primary_expression) @assert_false
        (#eq? @assert_false "false")))  

    (block
      (assert_statement
        (binary_expression) @assert_statement))""")

    assert_true_found = any(
        capture_name == "assert_true"
        for capture_name, _ in tree_sitter.QueryCursor(assert_q).captures(body).items()
    )
    assert_false_found = any(
        capture_name == "assert_false"
        for capture_name, _ in tree_sitter.QueryCursor(assert_q).captures(body).items()
    )
    assert_statement_found = any(
        capture_name == "assert_statement"
        for capture_name, _ in tree_sitter.QueryCursor(assert_q).captures(body).items()
    )

    if assert_false_found:
        print("assertion error;assert_false_found")
        safe_condition = False
    elif assert_statement_found:
        print("assertion error;assert_statement_found")
        safe_condition = False
    elif assert_true_found:
        print("assertion error;assert_true_found")
    else:
        print("assertion error;assert_statement_not_found")
        safe_condition = False

    divide_by_zero_q = tree_sitter.Query(
        JAVA_LANGUAGE,
        """
        (binary_expression
        operator: "/"
        right: (primary_expression) @right_zero
        (#eq? @right_zero "0"))


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
        (#not-eq? @not_right_zero "0"))
        """
    )


    divide_by_zero_found = any(
        capture_name == "right_zero"
        for capture_name, _ in tree_sitter.QueryCursor(divide_by_zero_q).captures(body).items()
    )

    maybe_divide_by_zero_found = any(
        capture_name == "maybe_right_zero"
        for capture_name, _ in tree_sitter.QueryCursor(divide_by_zero_q).captures(body).items()
    )

    not_divide_by_zero_found = any(
        capture_name == "not_right_zero"
        for capture_name, _ in tree_sitter.QueryCursor(divide_by_zero_q).captures(body).items()
    )

    if divide_by_zero_found:
        print("divide by zero;right_zero")
        safe_condition = False
    elif maybe_divide_by_zero_found:
        print("divide by zero;maybe_right_zero")
        safe_condition = False
    elif not_divide_by_zero_found:
        print("divide by zero;not_right_zero")
    else:
        print("divide by zero;not_found")

    # Infinite loop check

    infinite_loop_q = tree_sitter.Query(JAVA_LANGUAGE, """
        (block
            (while_statement
                condition: (parenthesized_expression
                    (expression) @while_true
                ) 
            )
            
        ) (#eq? @while_true "true")


        (block
            (while_statement) @while_statement
        ) """)

    while_true_found = any(
        capture_name == "while_true"
        for capture_name, _ in tree_sitter.QueryCursor(infinite_loop_q).captures(body).items()
    )

    while_statement_found = any(
        capture_name == "while_statement"
        for capture_name, _ in tree_sitter.QueryCursor(infinite_loop_q).captures(body).items()
    )

    if while_true_found:
        print("*;while_true_found")
        unsafe_condition = True
    elif while_statement_found:
        print("*;while_statement")
        safe_condition = False
    else:
        print("*;while_statement_not_found")

    # NULL POINTER
        null_pointer_q = tree_sitter.Query(JAVA_LANGUAGE, """
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
        )  """)

    empty_array_declaration = any(
        capture_name == "empty_array_declaration"
        for capture_name, _ in tree_sitter.QueryCursor(null_pointer_q).captures(body).items()
    )

    arrays_present = any(
        capture_name == "arrays_present"
        for capture_name, _ in tree_sitter.QueryCursor(null_pointer_q).captures(body).items()
    )

    if empty_array_declaration:
        print("null pointer;empty_array_declaration")
        unsafe_condition = True
    elif arrays_present:
        print("null pointer;arrays_present")
        safe_condition = False
    else:
        print("null pointer;array_declaration_not_found")

    # OK state check
    if (safe_condition):
        print("ok;yes")
    elif(unsafe_condition):
        print("ok;no")
    else:
        print("ok;maybe")


    for q in jpamb.QUERIES:
        if q not in ["assertion error", "divide by zero", "ok", "*", "null pointer"]:
            print(f"{q};skip")

    sys.exit(0)

if __name__ == "__main__":
    main()