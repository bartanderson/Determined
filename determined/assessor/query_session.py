# tools/analysis/assessor/query_session.py
# CLAUDE-EDIT 2026-06-16: (1) pass `text=text` into compile_and_explain()
# call inside run_algebra() so the local AI compiler sees the raw NL query,
# not just the intent label. (2) self_model wiring (import + field +
# to_dict key + populate in run_query) came from Bart's ChatGPT-assisted
# commit 2004302 — Claude fixed the import path bug, see system_self_model.py.
# (3) history is now durable: every run_query() also persists its result
# to the query_sessions table (best-effort — a persistence failure never
# blocks a query result). self._history remains the fast in-memory path;
# the DB is now the source of truth across process restarts.
#
# QuerySession — the first true oracle runtime object.
#
# Owns a single query lifecycle:
#   - snapshot binding (graph + seeds at query time)
#   - intent classification
#   - router execution
#   - expansion trace capture
#   - result normalization
#   - reasoning output packaging
#
# Purpose: make query execution reproducible and inspectable.
# Every query that passes through Assessor produces a QuerySession
# that can be replayed, diffed, or logged without re-running the engine.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from determined.inspection.meta.system_self_model import SystemSelfModelBuilder
from determined.oracle.persist_query_session import persist_query_session
from determined.persistence.persistence_engine import ensure_schema


# =========================================================
# QUERY SESSION RESULT (normalized output shape)
# =========================================================

@dataclass
class QuerySessionResult:
    # identity
    raw_query: str
    intent: str

    # reproducibility
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    queried_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # seeds (DB-authoritative)
    seeds: List[str] = field(default_factory=list)

    # expansion
    expanded: List[str] = field(default_factory=list)
    expansion_trace: Dict[str, Any] = field(default_factory=dict)

    # execution
    primitives: List[str] = field(default_factory=list)
    execution_plan: Dict[str, Any] = field(default_factory=dict)

    # graph snapshot facts at query time
    snapshot_edge_count: int = 0

    # reasoning surface (human + AI readable)
    reasoning: Dict[str, Any] = field(default_factory=dict)

    # understand and explore its limits for improving through questioning and usage
    self_model: Any = None

    def seed_explanation(self) -> str:
        if not self.seeds:
            return "No seeds found for query."
        return (
            f"Query '{self.raw_query}' matched {len(self.seeds)} seed(s): "
            f"{', '.join(self.seeds[:5])}"
        )
    def expansion_explanation(self) -> str:
        added = [s for s in self.expanded if s not in self.seeds]
        return (
            f"Expansion added {len(added)} symbol(s) via {self.intent} traversal. "
            f"Total symbols in result: {len(self.expanded)}."
        )

    def intent_mapping_trace(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "detected_intent": self.intent,
            "primitives_selected": self.primitives,
            "seed_count": len(self.seeds),
            "expanded_count": len(self.expanded),
        }

    def seed_paths(self) -> Dict[str, Any]:
        """Which graph paths were followed to reach each seed."""
        return self.reasoning.get("seed_paths", {})

    def expansion_edges(self) -> Dict[str, Any]:
        """Edge-level trace of how expansion propagated from seeds."""
        return self.reasoning.get("edges", {})

    def node_reasons(self) -> Dict[str, str]:
        """Per-node explanation of why each expanded symbol was included."""
        trace = self.expansion_trace
        return trace.get("node_reasons", {})

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "queried_at": self.queried_at,
            "query": self.raw_query,
            "intent": self.intent,
            "seeds": self.seeds,
            "expanded": self.expanded,
            "seed_explanation": self.seed_explanation(),
            "expansion_explanation": self.expansion_explanation(),
            "intent_mapping_trace": self.intent_mapping_trace(),
            "snapshot_edge_count": self.snapshot_edge_count,
            "self_model": self.self_model,
        }


# =========================================================
# QUERY SESSION
# =========================================================

class QuerySession:
    """
    Owns a single query lifecycle against a fixed oracle snapshot.

    Usage:
        session = QuerySession(oracle)
        result = session.run_query("what depends on resolve_analysis_db_path")
        print(result.summary())

    For observability:
        session = QuerySession(oracle, logger=print)
        result = session.run_query("what depends on X")
    """

    def __init__(self, oracle, logger: Optional[Callable] = None):
        self.oracle = oracle
        self.logger = logger
        self._graph = None
        self._history: List[QuerySessionResult] = []

        try:
            ensure_schema(self.oracle.conn)
        except Exception as e:
            if self.logger:
                self.logger(f"[QuerySession] schema check failed (non-fatal): {e}")

    def _bind_snapshot(self):
        """Legacy method kept for callers that need a GraphBundle snapshot.
        The query path no longer uses this - run_query() calls route_query(oracle)
        directly (Phase 3 boundary completion).
        """
        if self._graph is None:
            self._graph = self.oracle.get_snapshot_graph()
        return self._graph

    def run_query(self, text: str) -> QuerySessionResult:
        from determined.assessor.query_router import route_query

        route_result = route_query(text, self.oracle, logger=self.logger)

        expansion_trace = route_result.execution_plan.get("trace", {})

        self_model = SystemSelfModelBuilder(self.oracle).build()

        result = QuerySessionResult(
            raw_query=text,
            intent=route_result.intent,
            seeds=route_result.seed_symbols,
            expanded=route_result.expanded_symbols,
            expansion_trace=expansion_trace,
            primitives=route_result.execution_plan.get("primitives", []),
            execution_plan=route_result.execution_plan,
            snapshot_edge_count=route_result.edge_count,
            reasoning={
                "seed_paths": expansion_trace.get("seed_paths", {}),
                "edges": expansion_trace.get("edges", {}),
            },
            self_model=self_model,
        )

        self._history.append(result)

        try:
            persist_query_session(self.oracle.conn, result)
        except Exception as e:
            # Persistence is best-effort logging, not part of the query
            # contract — a DB write failure must never invalidate a
            # successfully computed result.
            if self.logger:
                self.logger(f"[QuerySession] failed to persist session {result.session_id}: {e}")

        return result

    def replay(self, result: QuerySessionResult) -> QuerySessionResult:
        """
        Re-run a prior query against the same bound snapshot.
        Produces a new QuerySessionResult with a fresh session_id and
        queried_at — allowing diff comparison against the original.
        Snapshot is NOT re-fetched; determinism is guaranteed by the
        bound graph state.
        """
        return self.run_query(result.raw_query)

    def history(self) -> List[QuerySessionResult]:
        """All results produced by this session in execution order."""
        return list(self._history)

    def run_batch(self, queries: List[str]) -> Dict[str, QuerySessionResult]:
        """
        Execute multiple queries against the same bound snapshot.
        Snapshot is bound on the first query and reused — deterministic
        across the batch.
        """
        return {q: self.run_query(q) for q in queries}

    def run_algebra(self, text: str, views: dict) -> dict:
        """
        Full pipeline: natural language → oracle expansion + algebra result.

        Steps:
          1. run_query() — oracle router gives intent + expansion trace
          2. compile_query(intent) — maps intent → AST via query compiler
          3. QueryExecutor.execute() — runs AST against provided views

        Returns a dict with both the oracle result and the algebra result
        so callers can see the expansion trace AND the structured view output
        side by side.

        views: dict of {view_name: view_object}. In practice, callers should
        use Assessor.all_views() to build this from real DB-backed data —
        see Assessor.ask() and tools/analysis/ask.py, the real entrypoint
        that wires this method up end-to-end (2026-06-16).
        """
        from determined.truth.query_compiler import compile_and_explain
        from determined.truth.query_executor import QueryExecutor

        oracle_result = self.run_query(text)

        compiled = compile_and_explain(oracle_result.intent, text=text)
        plan = compiled["plan"]

        executor = QueryExecutor(views=views)
        algebra_result = executor.execute(plan.root)

        return {
            "text": text,
            "intent": oracle_result.intent,
            "oracle": oracle_result,
            "compiled_ast": compiled["ast"],
            "compiler_explanation": compiled["explanation"],
            "algebra_result": algebra_result,
        }
