# tools\analysis\tests\semantic\test_semantic_identity_invariants.py

from determined.representation.symbol_environment import SymbolEnvironment
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder
from determined.graph.symbol_resolution_engine import resolve_symbol_type


def test_builtin_fallback_behavior():
    env = SymbolEnvironment(
        alias_map={},
        runtime_bindings={},
        project_symbols=set(),
    )

    builder = SemanticIdentityBuilder()

    route_type = resolve_symbol_type(
        name="print",
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )

    identity = builder.build(
        "print",
        env,
        route_type=route_type,
    )

    assert identity.fqdn is None
    assert identity.confidence == 0.05
    assert "no_resolution_signal" in identity.provenance


def test_external_symbol_no_false_project():
    env = SymbolEnvironment(
        alias_map={},
        runtime_bindings={},
        project_symbols={"SomeInternalThing"},
    )

    builder = SemanticIdentityBuilder()

    route_type = resolve_symbol_type(
        name="flask.jsonify",
        runtime_bindings=env.runtime_bindings,
        project_symbols=env.project_symbols,
    )

    identity = builder.build(
        "flask.jsonify",
        env,
        route_type=route_type,
    )

    assert "project_symbol_hint" not in identity.provenance
    assert identity.leaf == "jsonify"


def test_project_does_not_override_runtime():
    env = SymbolEnvironment(
        alias_map={},
        runtime_bindings={"y": "flask.request.args"},
        project_symbols={"args"},
    )

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

    assert identity.resolved_by == "runtime"
    assert identity.fqdn.startswith("flask.request")