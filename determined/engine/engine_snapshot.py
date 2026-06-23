# tools/analysis/engine/engine_snapshot.py

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class EngineSnapshot:
    ingestion: Any
    graph: Any
    facts: Any
    metrics: Dict[str, Any]
    system_shape: Any
    structure_view: Any
    stability_view: Any
    integrity_view: Any
    subsystem_view: Any
    metadata: Dict[str, Any]


class EngineSnapshotBuilder:

    def build(
        self,
        ingestion,
        graph,
        facts,
        system_shape,
        structure_view,
        stability_view,
        integrity_view,
        subsystem_view,
    ) -> EngineSnapshot:

        edge_count = graph["edge_count"]

        metrics = {
            "file_count": facts["file_count"],
            "symbol_reference_count": facts["symbol_reference_count"],
            "edge_count": edge_count,
        }

        return EngineSnapshot(
            ingestion=ingestion,
            graph=graph,
            facts=facts,
            metrics=metrics,
            system_shape=system_shape,
            structure_view=structure_view,
            stability_view=stability_view,
            integrity_view=integrity_view,
            subsystem_view=subsystem_view,
            metadata={},
        )