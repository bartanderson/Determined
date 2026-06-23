# tools\analysis\tests\semantic\test_semantic_identity_runtime.py
import ast

from determined.representation.symbol_environment import SymbolEnvironment
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder
from determined.ingestion.parse_ast import (
    _extract_imports,
    _extract_runtime_bindings,
)
from determined.graph.symbol_resolution_engine import resolve_symbol_type

def build_env(source: str) -> SymbolEnvironment:
    tree = ast.parse(source)

    _, alias_map = _extract_imports(tree)
    runtime_bindings = _extract_runtime_bindings(tree, alias_map=alias_map)

    return SymbolEnvironment(
        alias_map=alias_map,
        runtime_bindings=runtime_bindings,
        project_symbols=set(),
    )


def test_runtime_binding_resolves_fqdn():
    source = """
from flask import request
y = request.args
"""

    env = build_env(source)
    builder = SemanticIdentityBuilder()

    route_type = resolve_symbol_type(
        name="y",
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )

    identity = builder.build(
        "y",
        env,
        route_type=route_type,
    )

    assert identity.fqdn is not None
    assert identity.resolved_by == "runtime"
    assert identity.confidence >= 0.85
    assert any(
        p.startswith("runtime:")
        for p in identity.provenance
    )


def test_runtime_binding_consistency():
    source = """
from flask import request
x = request.args
y = request.args
"""

    env = build_env(source)
    builder = SemanticIdentityBuilder()

    x_route = resolve_symbol_type(
        name="x",
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )

    y_route = resolve_symbol_type(
        name="y",
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )

    x_id = builder.build(
        "x",
        env,
        route_type=x_route,
    )

    y_id = builder.build(
        "y",
        env,
        route_type=y_route,
    )

    assert x_id.fqdn == y_id.fqdn
    assert x_id.resolved_by == "runtime"
    assert y_id.resolved_by == "runtime"