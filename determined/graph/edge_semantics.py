# tools/analysis/graph/edge_semantics.py

from __future__ import annotations


def classify_edge_semantics(caller: str, callee: str) -> str:
    """
    Deterministic edge-role classification.

    NO AI.
    NO inference beyond structure.
    """

    if not caller or not callee:
        return "unknown"

    caller_l = caller.lower()
    callee_l = callee.lower()

    # test relationships
    if caller_l.startswith("test_"):
        return "test_execution"

    # runtime / execution primitives
    if callee_l in {"print", "exec", "eval"}:
        return "runtime_execution"

    # import / module access patterns
    if "." in callee:
        return "module_dependency"

    # class usage
    if callee[0].isupper():
        return "type_usage"

    # generic function call
    return "function_call"