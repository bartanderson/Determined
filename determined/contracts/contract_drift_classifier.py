# tools/analysis/contracts/contract_drift_classifier.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
from collections import defaultdict


@dataclass
class ContractDriftSignal:
    contract_name: str
    severity: str
    layer: str
    classification: str  # transient | recurring | structural | obsolete
    count: int


def _field(v: Any, name: str, default: Any = None) -> Any:
    """
    Read `name` off a violation regardless of whether it's a dict (the
    real shape produced by Assessor.file_contract_reports() - the only
    production caller) or an object with attributes (the
    ContractViolation dataclass shape from contracts/contract_observer.py,
    which has zero production callers today but is a legitimate shape
    this classifier should not break on if it's ever wired up). Same
    shape-safety principle as truth/query_executor.py's get_field() -
    handle whichever valid shape came back, don't demand one specific one.
    """
    if isinstance(v, dict):
        return v.get(name, default)
    return getattr(v, name, default)


class ContractDriftClassifier:
    """
    Converts raw contract violations into lifecycle signals.

    This is PURE ANALYSIS:
    - no mutation
    - no enforcement
    - no DB writes
    """

    def __init__(self):
        pass

    def classify(
        self,
        reports: List[Any],
    ) -> List[ContractDriftSignal]:

        counter = defaultdict(int)
        meta = {}

        # -----------------------------------------
        # FLATTEN ALL VIOLATIONS
        # -----------------------------------------
        for report in reports:
            for v in getattr(report, "violations", []):
                key = _field(v, "contract_name")
                counter[key] += 1
                meta[key] = {
                    "severity": _field(v, "severity", "unknown"),
                    "layer": _field(v, "layer", "unknown"),
                }

        signals: List[ContractDriftSignal] = []

        # -----------------------------------------
        # CLASSIFICATION RULES (simple, deterministic)
        # -----------------------------------------
        for contract, count in counter.items():

            if count == 1:
                classification = "transient"

            elif 2 <= count <= 3:
                classification = "recurring"

            elif count > 3:
                classification = "structural"

            else:
                classification = "obsolete"

            signals.append(
                ContractDriftSignal(
                    contract_name=contract,
                    severity=meta[contract]["severity"],
                    layer=meta[contract]["layer"],
                    classification=classification,
                    count=count,
                )
            )

        return signals
