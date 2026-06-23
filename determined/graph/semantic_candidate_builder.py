# tools/analysis/graph/semantic_candidate_builder.py

from determined.representation.semantic_identity import SemanticIdentity
from determined.representation.symbol_environment import SymbolEnvironment
from determined.graph.runtime_resolution import resolve_runtime_symbol


class SemanticIdentityBuilder:
    """
    SymbolIdentity construction layer.

    PURPOSE:
    - unify signals from routing stage (CP3)
    - produce coherent semantic identity
    - MUST NOT perform routing or classification
    """

    def build(
        self,
        name: str,
        env: SymbolEnvironment,
        route_type: str | None = None,
    ) -> SemanticIdentity:

        # -------------------------------------------------
        # HARD GATE: CP3 routing must exist
        # -------------------------------------------------
        if route_type is None:
            import traceback

            raise RuntimeError(
                f"[ROUTE CONTRACT BREAK] Missing route_type for symbol='{name}'\n"
                f"CALL STACK:\n{''.join(traceback.format_stack(limit=10))}"
            )

        # -------------------------------------------------
        # basic identity scaffold
        # -------------------------------------------------
        leaf = name.split(".")[-1]

        identity = SemanticIdentity(
            surface=name,
            leaf=leaf,
            resolved_by=route_type,
        )
        identity.confidence = 0.0
        identity.provenance = []

        if not hasattr(identity, "runtime_hints"):
            identity.runtime_hints = {}

        if not hasattr(identity, "project_hits"):
            identity.project_hits = []

        # -------------------------------------------------
        # GLOBAL FQDN INVARIANT INITIALIZATION
        # -------------------------------------------------
        # enforce deterministic semantic contract baseline
        # -------------------------------------------------
        if route_type in (
            "builtin",
            "stdlib",
            "unknown",
            "external",
        ):
            identity.fqdn = None

        elif route_type in (
            "runtime",
            "project",
        ):
            identity.fqdn = None

        else:
            raise RuntimeError(
                f"[INVARIANT VIOLATION] unknown route_type early: "
                f"{route_type} for {name}"
            )

        # -------------------------------------------------
        # HARD CONTRACT: routing must match identity
        # -------------------------------------------------
        if identity.resolved_by != route_type:
            raise RuntimeError(
                f"[INTEGRITY VIOLATION] resolved_by mismatch "
                f"name={name} route_type={route_type} "
                f"resolved_by={identity.resolved_by}"
            )

        # -------------------------------------------------
        # 1. Runtime enrichment (no classification, only signals)
        # -------------------------------------------------
        if route_type == "runtime":
            runtime_target = resolve_runtime_symbol(
                name,
                env.runtime_bindings,
            )

            if runtime_target:
                identity.fqdn = runtime_target
                identity.runtime_hints[leaf] = runtime_target
                identity.provenance.append(
                    f"runtime:{leaf}->{runtime_target}"
                )

                # FIX: ensure runtime confidence is not left at default 0.0
                identity.confidence = 0.9

            else:
                # still valid runtime route, but unresolved binding
                identity.confidence = 0.2

        # -------------------------------------------------
        # 2. Project enrichment (signal-only, no inference)
        # -------------------------------------------------
        elif route_type == "project":
            if name in env.project_symbols:
                identity.fqdn = name
                identity.project_hits.append(name)
                identity.provenance.append(f"project:{name}")
                identity.confidence = max(identity.confidence, 0.95)
            else:
                identity.confidence = 0.4

        elif route_type == "builtin":
            identity.fqdn = None
            identity.confidence = 0.05
            identity.provenance.append("no_resolution_signal")
            identity.provenance.append(f"builtin:{name}")

        elif route_type == "stdlib":
            identity.fqdn = None
            identity.confidence = 0.15
            identity.provenance.append(f"stdlib:{name}")

        # -------------------------------------------------
        # 3. External / unknown (pure labeling)
        # -------------------------------------------------
        elif route_type == "external":
            identity.fqdn = None
            identity.confidence = 0.25
            identity.provenance.append(f"external:{name}")

        elif route_type == "unknown":
            identity.fqdn = None
            identity.confidence = 0.1
            identity.provenance.append(f"unresolved:unknown")

        else:
            raise RuntimeError(
                f"[ROUTE CONTRACT BREAK] invalid route_type='{route_type}' "
                f"for symbol='{name}'"
            )

        # -------------------------------------------------
        # HARD CONTRACT: fail fast on identity corruption
        # -------------------------------------------------
        self._assert_identity_integrity(identity, route_type, name)

        return identity

    # -----------------------------------------------------
    # Instrumentation guard (explicit failure visibility)
    # -----------------------------------------------------
    def _assert_identity_integrity(self, identity, route_type, name):

        if identity.resolved_by != route_type:
            raise RuntimeError(
                f"[INTEGRITY VIOLATION] resolved_by mismatch "
                f"name={name} route_type={route_type}"
            )

        if route_type == "runtime" and identity.confidence == 0.0:
            raise RuntimeError(
                f"[INTEGRITY VIOLATION] runtime confidence not set "
                f"name={name}"
            )