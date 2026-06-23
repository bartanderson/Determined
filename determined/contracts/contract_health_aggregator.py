# tools/analysis/contracts/contract_health_aggregator.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
from collections import defaultdict


@dataclass
class ContractHealth:
    contract_name: str
    total_observations: int
    classification_counts: Dict[str, int]
    stability_score: float  # 0.0 unstable → 1.0 stable
    trend_direction: str    # improving | degrading | stable


class ContractHealthAggregator:
    """
    Converts drift history into system-level contract health signals.

    PURE READ MODEL:
    - no DB writes
    - no enforcement
    """

    def aggregate(
        self,
        drift_rows: List[Dict[str, Any]],
    ) -> List[ContractHealth]:

        grouped = defaultdict(list)

        # -----------------------------------------
        # GROUP BY CONTRACT
        # -----------------------------------------
        for row in drift_rows:
            grouped[row["contract_name"]].append(row)

        results: List[ContractHealth] = []

        # -----------------------------------------
        # ANALYZE EACH CONTRACT
        # -----------------------------------------
        for name, rows in grouped.items():

            total = len(rows)

            classification_counts = defaultdict(int)

            for r in rows:
                classification_counts[r["classification"]] += 1

            # -----------------------------------------
            # SIMPLE STABILITY MODEL
            # -----------------------------------------
            structural = classification_counts.get("structural", 0)
            recurring = classification_counts.get("recurring", 0)
            transient = classification_counts.get("transient", 0)

            # normalize instability pressure
            instability = (structural * 3 + recurring * 2 + transient * 1) / max(total, 1)

            stability_score = max(0.0, 1.0 - instability / 5.0)

            # -----------------------------------------
            # TREND DIRECTION (simple heuristic)
            # -----------------------------------------
            if structural > recurring:
                trend = "degrading"
            elif transient > structural and recurring == 0:
                trend = "improving"
            else:
                trend = "stable"

            results.append(
                ContractHealth(
                    contract_name=name,
                    total_observations=total,
                    classification_counts=dict(classification_counts),
                    stability_score=round(stability_score, 3),
                    trend_direction=trend,
                )
            )

        return results