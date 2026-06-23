# tools/analysis/contracts/contract_types.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


# -------------------------
# Domain-level contract
# -------------------------

@dataclass(frozen=True)
class DomainContract:
    """
    Represents a single domain section from tool_system_contract.json
    """
    definition: str
    rules: List[str]


# -------------------------
# Output contract
# -------------------------

@dataclass(frozen=True)
class OutputContract:
    required_fields: List[str]
    rules: List[str]


# -------------------------
# Dependency rules
# -------------------------

@dataclass(frozen=True)
class DependencyRules:
    allowed: Dict[str, List[str]]
    forbidden: List[str]


# -------------------------
# Core invariants
# -------------------------

@dataclass(frozen=True)
class CoreInvariants:
    invariants: List[str]


# -------------------------
# Stability principle
# -------------------------

@dataclass(frozen=True)
class StabilityPrinciple:
    definition: str
    constraints: List[str]


# -------------------------
# Full system contract (composed view)
# -------------------------

@dataclass(frozen=True)
class SystemContract:
    system: str
    version: str

    domains: Dict[str, DomainContract]

    output_contract: OutputContract
    dependency_rules: DependencyRules
    core_invariants: CoreInvariants
    stability_principle: StabilityPrinciple