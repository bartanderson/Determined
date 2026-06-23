# tools/analysis/contracts/contract_lifecycle.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ContractLifecycleState:
    contract_name: str
    state: str
    stability_score: float
    trend: str
    recommendation: str


class ContractLifecycleController:
    """
    Converts contract health signals into lifecycle states.

    IMPORTANT:
    - NO enforcement
    - NO mutation
    - PURE interpretive layer
    """

    def evaluate(
        self,
        health: List[Any],
    ) -> List[ContractLifecycleState]:

        results: List[ContractLifecycleState] = []

        for h in health:

            score = h.stability_score
            trend = h.trend_direction

            # -----------------------------------------
            # STATE MACHINE
            # -----------------------------------------
            if score > 0.85 and trend == "stable":
                state = "ACTIVE"
                recommendation = "no action"

            elif 0.7 <= score <= 0.85:
                state = "STABLE"
                recommendation = "monitor"

            elif trend == "degrading":
                state = "DEGRADING"
                recommendation = "investigate usage shift"

            elif score < 0.5 and h.total_observations > 5:
                state = "UNSTABLE"
                recommendation = "review contract definition"

            elif h.total_observations <= 2:
                state = "STALE"
                recommendation = "insufficient signal"

            else:
                state = "OBSOLETE"
                recommendation = "candidate for removal"

            results.append(
                ContractLifecycleState(
                    contract_name=h.contract_name,
                    state=state,
                    stability_score=h.stability_score,
                    trend=h.trend_direction,
                    recommendation=recommendation,
                )
            )

        return results