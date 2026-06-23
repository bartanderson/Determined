# tools/analysis/graph/context_classification.py

from determined.graph.project_graph_context import ProjectGraphContext
from determined.graph.symbol_classifier import classify_symbol
from determined.graph.symbol_router import route_symbol
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder
from determined.representation.symbol_environment import SymbolEnvironment
from determined.graph.symbol_resolution_engine import resolve_symbol_type


def classify_symbol_with_context(
    name: str,
    ctx: ProjectGraphContext,
):
    assert not isinstance(
        ctx,
        dict,
    ), "ctx must be ProjectGraphContext, not dict"

    runtime_bindings = ctx.runtime_bindings or {}
    project_symbols = ctx.project_symbols or set()

    # ----------------------------
    # semantic environment
    # ----------------------------
    env = SymbolEnvironment(
        alias_map={},
        runtime_bindings=runtime_bindings,
        project_symbols=project_symbols,
    )

    # ----------------------------
    # routing
    # ----------------------------
    route = route_symbol(
        name=name,
        runtime_bindings=runtime_bindings,
        project_symbols=project_symbols,
    )

    # ----------------------------
    # identity construction
    # ----------------------------
    builder = SemanticIdentityBuilder()


    route_type = resolve_symbol_type(
        name=name,
        runtime_bindings=ctx.runtime_bindings,
        project_symbols=ctx.project_symbols,
    )

    identity = builder.build(
        name=name,
        env=env,
        route_type=route_type,
    )

    # ----------------------------
    # final classification
    # ----------------------------
    return classify_symbol(
        identity,
        env,
    )