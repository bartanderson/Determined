# tools/analysis/graph/symbol_classifier.py

from __future__ import annotations

# MODULE: classifier
# OWNED: TRUE
#
# CONTRACT (LOCKED v1)
# - Owns symbol → bucket classification
# - Must produce deterministic bucket labels
# - Does NOT own snapshot aggregation or metrics

import builtins
import sys
from typing import Literal, Tuple, Dict, Any
from determined.identity.symbol_identity import normalize_symbol, resolve_symbol_identity
from determined.contracts.classification_contract import load_classification_contract
from determined.representation.semantic_identity import SemanticIdentity
from determined.representation.symbol_environment import SymbolEnvironment
from determined.contracts.semantic_pipeline_contract import SemanticPipelineContract as Contract

BUILTINS = set(dir(builtins))
STDLIB_PREFIXES = set(sys.stdlib_module_names)

SymbolClass = Literal[
    "project",
    "builtin",
    "stdlib",
    "runtime",
    "external_lib",
    "external_unknown",
    "classification_gap",
    "unresolved_qualified_reference",
]

# ----------------------------
# HELPERS
# ----------------------------


# def normalize_symbol(name: str) -> str:
#     if not name:
#         return name
#     return name.replace("<module>.", "").strip()

def external_root(name: str) -> str:
    if "." not in name:
        return "unknown"
    return name.split(".")[0]


def project_key(name: str) -> str:
    return name.split(".")[-1]


def module_key2(name: str) -> str:
    parts = name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


# ----------------------------
# CORE CLASSIFIER
# ----------------------------

def classify_symbol(identity: SemanticIdentity, env: SymbolEnvironment):
    
    leaf = identity.leaf
    fqdn = identity.fqdn or identity.surface

    # ----------------------------
    # 1. PROJECT (HARD RULE)
    # ----------------------------
    project_leaf_match = any(
        leaf == s.split(".")[-1]
        for s in env.project_symbols
    )

    is_proj = (
        env.is_project_symbol(fqdn)
        or project_leaf_match
    )

    if is_proj:
        return "project"

    # ----------------------------
    # 2. BUILTIN (HARD RULE)
    # ----------------------------
    if leaf in BUILTINS:
        return "builtin"

    # ----------------------------
    # 3. STDLIB (ONLY VIA ENV OR MINIMAL SIGNAL)
    # ----------------------------
    if fqdn.split(".")[0] in STDLIB_PREFIXES:
        return "stdlib"

    # ----------------------------
    # 4. RUNTIME (WEAK SIGNAL)
    # ----------------------------
    if identity.resolved_by in ("runtime", "alias"):
        return "runtime"

    # ----------------------------
    # 5. FALLBACK
    # ----------------------------
    return "unknown"