# tools/analysis/tests/regression/test_runtime_resolution_lock.py

import ast

from determined.representation.symbol_environment import SymbolEnvironment
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder
from determined.ingestion.parse_ast import (
    _extract_imports,
    _extract_runtime_bindings,
)
from determined.graph.symbol_resolution_engine import resolve_symbol_type

def build_identity(builder, name, env):
    route_type = resolve_symbol_type(
        name=name,
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )
    return builder.build(name, env, route_type=route_type)

def test_runtime_resolution_real_lock():

    fixture = "tests/fixtures/sample_project/runtime_case.py"

    with open(fixture, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    # ----------------------------
    # build real environment
    # ----------------------------
    imports, alias_map = _extract_imports(tree)

    runtime_bindings = _extract_runtime_bindings(
        tree,
        alias_map=alias_map,
    )

    env = SymbolEnvironment(
        alias_map=alias_map,
        runtime_bindings=runtime_bindings,
        project_symbols=set(),
    )

    builder = SemanticIdentityBuilder()

    # ----------------------------
    # identities
    # ----------------------------
    x_identity = build_identity(builder, "x", env)
    y_identity = build_identity(builder, "y", env)

    # ----------------------------
    # LOCKED ASSERTIONS
    # ----------------------------

    # runtime resolution must exist somewhere in graph
    assert y_identity.fqdn is not None, "runtime resolution failed for y_identity"

    # resolved runtime target must propagate consistently
    if x_identity.fqdn is not None:
	    assert x_identity.fqdn == y_identity.fqdn, (
	        f"fqdn mismatch: x={x_identity.fqdn}, y={y_identity.fqdn}"
	    )

    # runtime binding must win over unresolved state
    assert y_identity.resolved_by == "runtime"

    # confidence must reflect resolution success
    assert y_identity.confidence >= 0.85