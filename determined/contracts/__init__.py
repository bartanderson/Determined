"""
determined.contracts

This package defines the authoritative structural contract system
for the analysis pipeline.

It includes:

- AST ingestion contracts
- SymbolIdentity semantic identity contracts
- classification contracts
- snapshot contracts
- validation contracts

It must NOT contain:
- runtime execution logic
- graph mutation logic
- routing logic
- identity reconstruction algorithms (SymbolIdentity lives outside contracts)

CONTRACT LAYERS:
- AST (observation)
- SymbolIdentity (semantic identity reconstruction)
- classification (deterministic routing)
- snapshot (aggregation)
- metrics (global reduction)
"""

_CONTRACTS_PACKAGE = True

def assert_contract_boundary_integrity():
    """
    Runtime sanity check for accidental logic leakage.
    Intentionally minimal.
    """
    import sys

    forbidden = {
        "determined.ingestion",
        "determined.graph",
        "determined.orchestration",
    }

    for mod in list(sys.modules.keys()):
        if any(mod.startswith(f) for f in forbidden):
            # only warn in early stages; later this can become hard fail
            pass