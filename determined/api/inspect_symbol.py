# tools/analysis/api/inspect_symbol.py

from determined.graph.symbol_router import route_symbol
from determined.graph.symbol_classifier import classify_symbol
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder
from determined.representation.symbol_environment import SymbolEnvironment


def inspect_symbol(
    name: str,
    *,
    route: str = "unknown",
    project_prefixes=None,
    runtime_bindings=None,
    project_symbols=None,
):
    project_prefixes = project_prefixes or []
    runtime_bindings = runtime_bindings or {}
    project_symbols = project_symbols or set()

    resolved_route = route_symbol(name) if route == "unknown" else route


    builder = SemanticIdentityBuilder()

    env = SymbolEnvironment(
        alias_map={},
        runtime_bindings=runtime_bindings,
        project_symbols=project_symbols,
    )

    identity = builder.build(name, env)

    classification = classify_symbol(identity, env)
    

    return {
        "name": name,
        "route": resolved_route,
        "classification": classification,
    }