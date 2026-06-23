# tools/analysis/ingestion/extract_symbols.py

import ast


def extract_symbols(tree, module_prefix: str = ""):
    symbols = set()

    # -------------------------------------------------
    # PATCH: attach parent links so we can detect methods
    # -------------------------------------------------
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    # -------------------------------------------------
    # SYMBOL COLLECTION
    # -------------------------------------------------
    for node in ast.walk(tree):

        # -------------------------
        # FUNCTIONS + METHODS
        # -------------------------
        if isinstance(node, ast.FunctionDef):
            parent = getattr(node, "parent", None)

            if isinstance(parent, ast.ClassDef):
                symbols.add(
                    f"{module_prefix}.{parent.name}.{node.name}"
                    if module_prefix
                    else f"{parent.name}.{node.name}"
                )
            else:
                symbols.add(
                    f"{module_prefix}.{node.name}"
                    if module_prefix
                    else node.name
                )

        # -------------------------
        # CLASSES
        # -------------------------
        elif isinstance(node, ast.ClassDef):
            symbols.add(
                f"{module_prefix}.{node.name}"
                if module_prefix
                else node.name
            )

    return symbols