# tools/analysis/validation/contract_validation_pass.py

from __future__ import annotations

from typing import Any, List
from determined.contracts.contract_observer import ContractReport


class ContractValidationPass:
    """
    FINAL validation gate between:
    - observation (evaluate_file_contracts)
    - enforcement (SystemValidator)
    """

    def __init__(self, strict: bool = False):
        self.strict = strict

    def run(
        self,
        report: ContractReport,
        analysis: Any,
        graph: Any,
    ) -> List[str]:

        errors: List[str] = []

        # ---------------------------
        # 1. REPORT VALIDITY
        # ---------------------------
        if report is None:
            return ["Missing ContractReport"]

        if not hasattr(report, "violations"):
            return ["Invalid ContractReport structure"]

        # ---------------------------
        # 2. ERROR ESCALATION
        # ---------------------------
        for v in report.violations:
            if getattr(v, "severity", None) == "error":
                errors.append(
                    f"{v.contract_name}: {v.message}"
                )

        # ---------------------------
        # 3. STRICT MODE ENFORCEMENT
        # ---------------------------
        if self.strict:
            errors.extend(self._strict_checks(report))

        return errors

    def _strict_checks(self, report: ContractReport) -> List[str]:
        return [
            "STRICT MODE: contract system requires full enforcement pass"
        ]