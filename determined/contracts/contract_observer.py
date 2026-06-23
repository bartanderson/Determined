# tools/analysis/contracts/contract_observer.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from determined.contracts.contract_map import build_contract_map


@dataclass
class ContractViolation:
    contract_name: str
    layer: str
    file_path: str
    message: str
    severity: str
    observed_value: Any = None
    expected_value: Any = None


@dataclass
class ContractReport:
    file_path: str
    violations: List[ContractViolation]


def evaluate_file_contracts(
    file_path: str,
    file_analysis,
    graph,
    db_snapshot: Dict[str, Any],
) -> ContractReport:
    """
    Observational contract evaluator.

    This is intentionally:
    - read-only
    - side-effect free
    - deterministic given inputs
    """

    contracts = build_contract_map()
    violations: List[ContractViolation] = []

    # -----------------------------------------
    # INGESTION CONTRACTS
    # -----------------------------------------
    ingest_contract = contracts["ingestion_emits_file_analyses"]

    if not file_analysis:
        violations.append(
            ContractViolation(
                contract_name=ingest_contract.name,
                layer=ingest_contract.layer,
                file_path=file_path,
                message="No FileAnalysis produced for file",
                severity=ingest_contract.violation_type,
            )
        )

    # -----------------------------------------
    # SYMBOL DENSITY CHECK
    # -----------------------------------------
    sym_contract = contracts["ingestion_preserves_symbol_density"]

    sym_refs = getattr(file_analysis, "symbol_references", []) if file_analysis else []

    if sym_refs is None:
        violations.append(
            ContractViolation(
                contract_name=sym_contract.name,
                layer=sym_contract.layer,
                file_path=file_path,
                message="symbol_references missing entirely",
                severity="error",
            )
        )

    # -----------------------------------------
    # PERSISTENCE CHECK (if db snapshot provided)
    # -----------------------------------------
    persist_contract = contracts["persistence_row_count_matches_memory"]

    if db_snapshot is not None:
        db_count = db_snapshot.get("symbol_reference_count", None)

        if db_count is not None and len(sym_refs) != db_count:
            violations.append(
                ContractViolation(
                    contract_name=persist_contract.name,
                    layer=persist_contract.layer,
                    file_path=file_path,
                    message="DB row count mismatch with in-memory symbol_references",
                    severity=persist_contract.violation_type,
                    observed_value=len(sym_refs),
                    expected_value=db_count,
                )
            )

    # -----------------------------------------
    # GRAPH CONTRACT
    # -----------------------------------------
    graph_contract = contracts["graph_builder_deterministic_output"]

    edge_count = len(getattr(graph, "edges", []))
    symbol_count = len(sym_refs)

    if symbol_count > 0 and edge_count == 0:
        violations.append(
            ContractViolation(
                contract_name=graph_contract.name,
                layer=graph_contract.layer,
                file_path=file_path,
                message="GraphBuilder produced no edges despite symbol references",
                severity=graph_contract.violation_type,
                observed_value=edge_count,
                expected_value=symbol_count,
            )
        )

    return ContractReport(
        file_path=file_path,
        violations=violations,
    )


def summarize_reports(reports: List[ContractReport]) -> Dict[str, Any]:
    """
    Aggregated system-level view.
    """

    all_violations = []
    for r in reports:
        all_violations.extend(r.violations)

    by_contract = {}

    for v in all_violations:
        by_contract.setdefault(v.contract_name, 0)
        by_contract[v.contract_name] += 1

    return {
        "total_files": len(reports),
        "total_violations": len(all_violations),
        "by_contract": by_contract,
    }