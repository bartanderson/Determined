# ingestion/ast_traversal.py

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class ASTBucket:
    functions: List[ast.AST]
    classes: List[ast.AST]
    imports: List[ast.AST]
    mutations: List[ast.AST]
    others: List[ast.AST]


def traverse_ast_once(tree: ast.AST) -> ASTBucket:
    """
    Single-pass AST traversal.

    This is the ONLY AST walk allowed in C-layer.
    """

    bucket = ASTBucket(
        functions=[],
        classes=[],
        imports=[],
        mutations=[],
        others=[],
    )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bucket.functions.append(node)

        elif isinstance(node, ast.ClassDef):
            bucket.classes.append(node)

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bucket.imports.append(node)

        else:
            bucket.others.append(node)

    return bucket