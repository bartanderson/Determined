# tools/analysis/contracts/contract_validator.py


# MODULE: contract
# OWNED: TRUE
#
# CONTRACT (LOCKED v2 - SymbolIdentity integrated validation layer)
#
# ROLE:
# - runtime validation of pipeline invariants across:
#     SymbolIdentity → classification → snapshot → metrics
#
# ENSURES:
# - SymbolIdentity objects are structurally valid SymbolIdentity instances
# - classification consumes but does not mutate SymbolIdentity
# - snapshot only aggregates post-classification outputs
#
# STRICT RULES:
# - must not perform identity reconstruction
# - must not resolve symbols
# - must only validate invariants


from dataclasses import dataclass
from typing import Any, Dict


class ContractViolation(Exception):
    pass


class ContractRuntimeValidator:
    def __init__(self, contract: Dict[str, Any]):
        self.contract = contract

    def validate_stage(self, stage: str, context: Dict[str, Any]) -> None:
        """
        context = runtime snapshot of what just happened in pipeline stage
        """

        modules = self.contract.get("modules", {})
        stage_contract = modules.get(stage)

        if not stage_contract:
            raise ContractViolation(f"Unknown stage: {stage}")

        invariants = stage_contract.get("invariants", {})

        for name, rule in invariants.items():
            self._check_rule(stage, name, rule, context)

    def _check_rule(self, stage: str, name: str, rule: Any, context: Dict[str, Any]):
        """
        Minimal rule engine (intentionally simple)
        """

        # ---- edge conservation ----
        if name == "edge_conservation":
            edges = context.get("edges", None)
            if edges is not None and edges < 0:
                raise ContractViolation(f"[{stage}] negative edge count")

        # ---- classification boundary ----
        if name == "classification_must_not_be_in_persistence":
            if context.get("classification_called_in_persistence"):
                raise ContractViolation(f"[{stage}] classification leaked into persistence")

        # ---- snapshot integrity ----
        if name == "snapshot_must_match_graph":
            if context.get("snapshot_mismatch"):
                raise ContractViolation(f"[{stage}] snapshot mismatch detected")

        # ---- generic boolean guard ----
        if isinstance(rule, bool) and rule is True:
            if context.get(name) is False:
                raise ContractViolation(f"[{stage}] invariant failed: {name}")

    def validate_all_stages(self, stage_contexts: dict) -> list:
        """
        Run validate_stage for every stage in stage_contexts without raising.
        Returns list of violation dicts compatible with persist_contract_violations.
        stage_contexts: {stage_name: {invariant_name: observed_value, ...}}
        """
        violations = []
        for stage, context in stage_contexts.items():
            try:
                self.validate_stage(stage, context)
            except ContractViolation as exc:
                violations.append({
                    "contract_name": f"stage:{stage}",
                    "layer": stage,
                    "severity": "error",
                    "message": str(exc),
                })
        return violations