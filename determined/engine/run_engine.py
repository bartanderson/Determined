# tools/analysis/engine/run_engine.py

from dataclasses import dataclass
from typing import Any, Dict
import sqlite3
from pathlib import Path
from determined.ingestion.scan_project_files import scan_project_files
from determined.classification.classify_references import classify_references
from determined.graph.graph_builder import GraphBuilder
from determined.persistence.persistence_engine import persist_all
from determined.engine.db_resolver import resolve_analysis_db_path
from determined.engine.engine_logger import EngineLogger

ENABLE_FAULTS = False  # hard off for now
enable_logging = False  # <- single flag

@dataclass
class EngineResult:
    ingestion: Any
    graph: Any
    facts: Dict[str, Any]
    # snapshot: Dict[str, Any]
    # reduced: Any | None = None

class EngineRunner:
    def __init__(self, logger=None):
        self.logger = logger

    def run(self, corpus, project_prefixes, repo_root, connection=None, chaos_mode: bool = False, enable_logging: bool = False):

        # ==================================================
        # PHASE 0: INGESTION
        # ==================================================
        ingest_stats: dict = {}
        file_analyses = list(
            scan_project_files(
                corpus.root_path,
                project_prefixes,
                repo_root,
                stats=ingest_stats,
            )
        )

        # ----------------------------
        # CHAOS MODE (controlled fault injection)
        # ----------------------------
        if chaos_mode and self.logger:
            self.logger.write("\n=== CHAOS MODE ACTIVE ===")

            # 1. drop half the files
            file_analyses = file_analyses[: max(1, len(file_analyses) // 2)]

            # 2. corrupt bucket metadata slightly
            for a in file_analyses:
                for r in getattr(a, "symbol_references", []):
                    r.bucket = "unknown"

        if not file_analyses:
            raise RuntimeError("Engine ingestion produced no analyses")

        processed_count = len(file_analyses)

        file_analyses = [
            classify_references(a, project_prefixes,logger=self.logger)
            for a in file_analyses
        ]

        symbol_reference_count = sum(
            len(a.symbol_references) for a in file_analyses
        )

        ingestion = {
            "file_analyses": file_analyses,
            "processed_count": processed_count,
            "symbol_reference_count": symbol_reference_count,
        }

        # # ==================================================
        # # PHASE 0.5: GLOBAL INIT (MUST EXIST BEFORE ANYTHING ELSE)
        # # ==================================================
        # validator = SystemValidator(strict=False)

        all_reports = []
        drift_signals = []
        validation_errors = []

        # ==================================================
        # PHASE 1: GRAPH BUILD (NO ANALYSIS HERE)
        # ==================================================
        builder = GraphBuilder()

        for analysis in file_analyses:
            for ref in analysis.symbol_references:
                builder.add_reference(
                    caller=ref.caller,
                    callee=ref.callee,
                    line_number=ref.line_number,
                    bucket=getattr(ref, "bucket", "unknown"),
                    caller_file=analysis.file_path,
                )

        graph = builder.build()

        if ENABLE_FAULTS:
            from determined.observability.fault_injector import (
                inject_edge_drop,
                inject_classification_drift,
            )

            graph = inject_edge_drop(graph, rate=0.1)
            file_analyses = inject_classification_drift(file_analyses, rate=0.1)

        edge_count = len(getattr(graph, "edges", []))

        # Obeservability begin
        from determined.observability.signal_contract import prune_signals
        from determined.observability.instruments import (
            ingestion_instrument,
            graph_instrument,
            classification_instrument,
        )

        signals = []

        signals += ingestion_instrument(file_analyses)
        signals += graph_instrument(graph)
        signals += classification_instrument(file_analyses)

        signals = prune_signals(signals)

        if self.logger:
            self.logger.write("\n=== OBSERVABILITY SIGNALS ===")

            for s in signals:
                self.logger.write(
                    f"{s.stage} | {s.signal_class} | {s.name} = {s.value}"
                )

        if self.logger:
            self.logger.write("\n=== SYMBOL REFERENCE SANITY CHECK ===")

            sample = file_analyses[:3]

            for a in sample:
                self.logger.write(a.file_path)
                self.logger.write(f"  symbol_references: {len(a.symbol_references)}")

            self.logger.write(f"TOTAL symbol refs: {sum(len(a.symbol_references) for a in file_analyses)}")
            self.logger.write(f"EDGE COUNT: {edge_count}")

        persist_all(
            connection=connection,
            file_analyses=file_analyses,
            graph=graph,
            project_prefixes=project_prefixes,
            project_root=repo_root,
        )

        return ingest_stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest a codebase into a Determined corpus DB.")
    parser.add_argument("path", nargs="?", help="Path to the directory to ingest (omit to use a folder picker dialog)")
    args = parser.parse_args()

    print("Begin analysis.")
    project_prefixes = []

    if args.path:
        selected_target = str(Path(args.path).resolve())
    else:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        selected_target = filedialog.askdirectory(initialdir=Path(__file__).parent)

    if not selected_target:
        print("No path selected. Exiting.")
        raise SystemExit(1)

    repo_root = selected_target
    corpus = type("Corpus", (), {"root_path": selected_target})()
    db_path = resolve_analysis_db_path(corpus.root_path)

    log_path = Path(db_path).with_suffix(".log")
    logger = EngineLogger(enabled=enable_logging, path=log_path)

    logger.write("ENGINE START")
    logger.write("Target:", corpus.root_path)
    logger.write("DB:", db_path)
    runner = EngineRunner(logger=logger)

    runner.run(
        corpus=corpus,
        project_prefixes=project_prefixes,
        repo_root=repo_root,
        connection=sqlite3.connect(db_path),
    )
    logger.flush()
    print("\nAnalysis complete.")
    print("Database saved at:", db_path)