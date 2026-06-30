# tools\analysis\assessor\assessor.py

import os
from collections import defaultdict
from dataclasses import dataclass, field
from determined.oracle.db_oracle import DBOracle
from determined.assessor.epistemic_policy import (
    EpistemicPolicy,
    LLM_SEVERITY_THRESHOLD,
    HARD_BLOCK_INTEGRITY,
    HARD_BLOCK_STRUCTURE,
)
from determined.agent import llm_client

from determined.truth.views import (
    build_structure_view,
    build_stability_view,
    build_integrity_view,
    build_system_summary_view,
    build_role_view,
    build_intent_view,
)
from determined.truth.subsystem_view import build_subsystem_view
from determined.contracts.contract_drift_classifier import ContractDriftClassifier
from determined.validation.system_validator import SystemValidator
from determined.reducer.reduce import reduce
from determined.engine.responsibility_map import ROLE_PATTERNS, print_responsibility_map
from determined.engine.responsibility_snapshot import build_responsibility_snapshot
from determined.inspection.meta.system_self_model import SystemSelfModelBuilder
from determined.inspection.explain_file import explain_file as _explain_file
from determined.agent.task_generator import generate_task_md as _generate_task_md
from determined.agent.task_rereferencer import rereference_task_md as _rereference_task_md
from determined.intent.semantic_summary import (
    get_or_generate_summary as _get_or_generate_summary,
    get_summary_if_fresh as _get_summary_if_fresh,
    list_summaries as _list_summaries,
)
from determined.intent.knowledge_artifact import (
    add_artifact as _add_artifact,
    get_artifacts as _get_artifacts,
    list_artifacts as _list_artifacts,
    delete_artifact as _delete_artifact,
    highest_provenance as _highest_provenance,
)


# =========================================================
# DB-DERIVED SHAPES (assessor analogues of the in-memory
# ContractReport / ValidationResult used by run_engine)
# =========================================================

@dataclass
class ContractReport:
    file_path: str
    violations: list
    ok: bool


@dataclass
class ValidationSummary:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class Assessor:
    def __init__(self, oracle, knowledge=None):
        self.oracle = oracle
        self._bags: "BagStore | None" = None

    @property
    def _knowledge_conn(self):
        return self.oracle.conn

    @property
    def bags(self) -> "BagStore | None":
        """Lazy-init BagStore using the corpus DB connection."""
        if self._bags is None:
            try:
                from determined.agent.bag_store import BagStore
                corpus_path = getattr(self.oracle, "db_path", "")
                self._bags = BagStore(self.oracle.conn, corpus_path)
            except Exception:
                pass
        return self._bags

    def run(self, symbol: str):
        graph = self.oracle.get_snapshot_graph()

        return {
            "symbol": symbol,

            # existing DB capability
            "neighbors": self.oracle.neighbors(symbol),
            "surface": self.oracle.surface(symbol, 1),
            "influence": self.oracle.influence(symbol, 1),

            # NEW assessor capabilities (now actually executed)
            "validation": self.validate_graph(),
            "snapshot": self.build_snapshot(),
        }

    def snapshot(self):
        return self.oracle.get_snapshot_graph()

    def degree(self):
        edges = self.oracle.get_snapshot_graph().edges

        degree_map = {}

        for e in edges:
            degree_map[e.caller] = degree_map.get(e.caller, 0) + 1
            degree_map[e.callee] = degree_map.get(e.callee, 0) + 1

        return degree_map

    def hotspots(self, top_n=10):
        deg = self.degree()
        return sorted(deg.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def module_projection(self):
        edges = self.oracle.get_snapshot_graph().edges

        pairs = []

        for e in edges:
            caller_mod = e.caller.split(".")[0]
            callee_mod = e.callee.split(".")[0]

            if caller_mod != callee_mod:
                pairs.append((caller_mod, callee_mod))

        return pairs

    def subsystems(self):
        proj = self.module_projection()

        graph = defaultdict(set)

        for caller, callee in proj:
            graph[caller].add(callee)

        return {k: sorted(v) for k, v in graph.items()}

    def subsystem_degree(self):
        proj = self.module_projection()

        fanout = {}

        for caller, callee in proj:
            fanout[caller] = fanout.get(caller, 0) + 1

        return fanout

    def impact(self, symbol: str, depth: int = 1):
        return {
            "symbol": symbol,
            "surface": self.oracle.surface(symbol, depth),
            "influence": self.oracle.influence(symbol, depth),
            "neighbors": self.oracle.neighbors(symbol),
            "semantic": self.oracle.get_semantic_edges(),
        }

    def run_integrity_check(self):
        edges = self.snapshot().edges

        errors = []

        for e in edges:
            if not e.caller or not e.callee:
                errors.append(("invalid_edge", e))

        symbol_reference_count = self.oracle.symbol_reference_count()

        if len(edges) != symbol_reference_count:
            errors.append((
                "edge_count_mismatch",
                {"graph_edges": len(edges), "symbol_references": symbol_reference_count},
            ))

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def structural_diff(self, engine_edges, db_edges):
        engine_set = set((e.caller, e.callee) for e in engine_edges)
        db_set = set((e.caller, e.callee) for e in db_edges)

        missing_in_db = engine_set - db_set
        missing_in_engine = db_set - engine_set

        return {
            "missing_in_db": list(missing_in_db),
            "missing_in_engine": list(missing_in_engine)
        }

    def validate_graph(self):
        graph = self.snapshot().edges

        errors = []
        warnings = []

        for e in graph:
            if not e.caller:
                errors.append(("missing_caller", e))
            if not e.callee:
                errors.append(("missing_callee", e))

            if e.caller == e.callee:
                warnings.append(("self_edge", e))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "edge_count": len(graph)
        }

    def build_snapshot(self):
        graph = self.oracle.get_snapshot_graph().edges

        node_degree = {}

        for e in graph:
            node_degree[e.caller] = node_degree.get(e.caller, 0) + 1
            node_degree[e.callee] = node_degree.get(e.callee, 0) + 1

        # NOTE: bucket info lives in symbol_references, not graph_edges -
        # GraphEdge has no .bucket attribute, so deriving bucket_summary
        # from the graph snapshot always reported everything as
        # "classification_gap". Pull it from the DB directly instead.
        bucket_summary = self.oracle.bucket_summary()

        ranked = sorted(node_degree.items(), key=lambda x: -x[1])
        top_nodes = ranked[:10]
        high_fanout = [(n, d) for n, d in top_nodes if d > 3]

        return {
            "file_count": self.oracle.file_count(),
            "edge_count": len(graph),
            "symbol_reference_count": self.oracle.symbol_reference_count(),
            "bucket_summary": bucket_summary,
            "graph_insights": {
                "top_nodes_by_degree": top_nodes,
            },
            "structural_signals": {
                "high_fanout_nodes": high_fanout,
            },
            "node_degree": node_degree,
        }

    # =====================================================
    # QUERY (via QuerySession - single lifecycle object)
    # =====================================================
    def session(self) -> "QuerySession":
        """Return a fresh QuerySession bound to this oracle."""
        from determined.assessor.query_session import QuerySession
        return QuerySession(self.oracle)

    def query(self, text: str):
        """Execute a single query. Returns QuerySessionResult."""
        return self.session().run_query(text)

    def all_views(self) -> dict:
        """
        All 7 Truth Layer views, keyed exactly as QueryPlanner/registry
        expect (STRUCTURE/STABILITY/INTEGRITY/SUMMARY/SUBSYSTEM/ROLE/INTENT),
        built from real DB-backed data. This is the dict to pass as
        `views=` into QuerySession.run_algebra() - see
        tools/analysis/ask.py for the reference entrypoint. ROLE added
        2026-06-16 per Truth.md Phase 3/4 (purpose-of-file gap). INTENT
        added 2026-06-19 per Truth.md Phase 1 Row 1 remainder + Row 5:
        docstring-based intent capture, the first grounded answer to
        "what is X for" that does not use call-graph heuristics.
        """
        return {
            "STRUCTURE": self.structure_view(),
            "STABILITY": self.stability_view(),
            "INTEGRITY": self.integrity_view(),
            "SUMMARY": self.summary_view(),
            "SUBSYSTEM": self.subsystem_view(),
            "ROLE": self.role_view(),
            "INTENT": self.intent_view(),
        }

    def ask(self, text: str) -> dict:
        """
        The real, wired front door: natural language in, Truth-Layer-backed
        algebra result out.

        Decision gate: EpistemicPolicy measures risk from the Truth Layer
        views. If severity exceeds LLM_SEVERITY_THRESHOLD and no hard block
        applies, the algebra result is augmented with an LLM narrative layer
        via llm_client.chat(). Otherwise the deterministic result is returned
        as-is. All thresholds live in epistemic_policy.py.
        """
        views = self.all_views()
        result = self.session().run_algebra(text, views=views)

        # Risk measurement (pure, no side effects)
        policy = EpistemicPolicy()
        query_context = {
            "seed_count":     len(result["oracle"].seeds),
            "expanded_count": len(result["oracle"].expanded),
            "intent":         result["intent"],
        }
        directive = policy.analyze(
            structure_view=views["STRUCTURE"],
            integrity_view=views["INTEGRITY"],
            stability_view=views["STABILITY"],
            summary_view=views["SUMMARY"],
            role_view=views["ROLE"],
            query_context=query_context,
        )

        result["epistemic"] = {
            "severity": directive.severity,
            "risk_vector": directive.risk_vector,
            "required_surfaces": directive.required_surfaces,
        }

        # Single decision authority (only place LLM call is gated)
        hard_block = (
            directive.risk_vector["integrity"] >= HARD_BLOCK_INTEGRITY and
            directive.risk_vector["structure"] >= HARD_BLOCK_STRUCTURE
        )
        allow_llm = (
            directive.severity > LLM_SEVERITY_THRESHOLD
            and not hard_block
            and llm_client.is_available()
        )

        if allow_llm:
            narrative = llm_client.chat([
                {
                    "role": "system",
                    "content": (
                        "You are a senior software analyst. "
                        "You receive structured facts about a codebase and a question. "
                        "Synthesize a concise, grounded explanation using only the facts provided. "
                        "Do not invent information."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {text}\n\n"
                        f"Intent: {result['intent']}\n"
                        f"Relevant symbols: {result['oracle'].expanded[:15]}\n"
                        f"Seed symbols: {result['oracle'].seeds[:5]}\n"
                        f"Epistemic risk: severity={directive.severity:.2f}, "
                        f"risk_vector={directive.risk_vector}\n"
                        f"Required surfaces: {directive.required_surfaces}"
                    ),
                },
            ])
            result["narrative"] = narrative
        else:
            result["narrative"] = None
            result["narrative_skipped_reason"] = (
                "hard_block" if hard_block
                else "severity_below_threshold" if directive.severity <= LLM_SEVERITY_THRESHOLD
                else "llm_unavailable"
            )

        return result

    # =====================================================
    # STRUCTURE VIEW (run_engine Phase 3)
    # =====================================================

    def structure_view(self):
        return build_structure_view(
            self.snapshot(),
            builtin_symbols=self.oracle.builtin_symbols(),
        )

    # =====================================================
    # DB-DERIVED CONTRACT REPORTS
    #
    # run_engine built these from in-memory file_analyses via
    # evaluate_file_contracts() (a no-op stub) + SystemValidator's
    # symbol-reference check. Both checks reduce to "does this file's
    # persisted symbol_references contain a null caller/callee" -
    # which is now a DB query, not an in-memory pass.
    # =====================================================

    def file_contract_reports(self):
        files = self.oracle.file_reference_map()
        reports = []

        for file_path, refs in files.items():
            violations = []

            for ref in refs:
                if not ref["caller"] or not ref["callee"]:
                    violations.append({
                        "contract_name": "symbol_reference_integrity",
                        "severity": "error",
                        "layer": "graph",
                        "message": f"Invalid symbol reference at line {ref['line_number']}",
                    })

            reports.append(ContractReport(
                file_path=file_path,
                violations=violations,
                ok=len(violations) == 0,
            ))

        return reports

    def stability_view(self):
        from determined.contracts.contract_health_aggregator import ContractHealthAggregator
        from determined.contracts.contract_lifecycle import ContractLifecycleController
        reports = self.file_contract_reports()
        drift_signals = ContractDriftClassifier().classify(reports)
        # Read accumulated drift history to compute health + lifecycle across runs.
        # Empty on first ingest; grows richer over time as contract_drift_history fills.
        history_rows = self.oracle.conn.execute(
            "SELECT contract_name, classification, layer, count FROM contract_drift_history"
        ).fetchall()
        history = [dict(r) for r in history_rows]
        health = ContractHealthAggregator().aggregate(history) if history else []
        lifecycle = ContractLifecycleController().evaluate(health) if health else []
        return build_stability_view(reports, drift_signals=drift_signals, lifecycle=lifecycle)

    def validation_summary(self):
        # CLAUDE-EDIT 2026-06-18 (TRACKER.md section 3 item 17): was a
        # partial inline reimplementation of SystemValidator's checks -
        # only 2 of its 4 methods, and never called _validate_contracts at
        # all, so the contract violations file_contract_reports() already
        # computes were never escalated into INTEGRITY errors (this file's
        # own inline loop read v["severity"] directly, which happened to
        # work since it indexed the dict correctly - but it was a second,
        # parallel reimplementation of logic SystemValidator already owns,
        # not a wiring of the real component). Now calls SystemValidator's
        # real methods directly:
        #   - _validate_graph_integrity / _validate_shape_signals: take
        #     `graph` (.edges) - same shape as self.snapshot(), reusable
        #     unchanged.
        #   - _validate_contracts: takes ONE report and reads
        #     report.violations, then each violation's severity/
        #     contract_name/message via the new shape-safe _field() helper
        #     (system_validator.py) - needed because the real method used
        #     bare getattr(v, "severity", None), which silently returns
        #     None forever against Assessor's dict-shaped violations
        #     (dicts have no .severity attribute, so getattr's default
        #     just always won - no exception, no escalation, same "looks
        #     like a signal, does nothing" shape as the drift_signals gap
        #     fixed 2026-06-17). Called once per file report - Assessor's
        #     natural unit is one ContractReport per file, vs. run_engine's
        #     single combined report - and accumulated.
        #   - _validate_symbol_integrity: deliberately NOT called. It
        #     requires an in-memory analysis.symbol_references object
        #     Assessor's DB-only architecture doesn't have. Not a gap: the
        #     identical check (null caller/callee) is already performed in
        #     file_contract_reports() and surfaces as a
        #     "symbol_reference_integrity" contract violation, which
        #     _validate_contracts above already escalates to an error.
        #     Calling both would be the same finding under two shapes.
        validator = SystemValidator()
        graph = self.snapshot()

        errors = []
        for report in self.file_contract_reports():
            errors += validator._validate_contracts(report)

        errors += validator._validate_graph_integrity(graph)
        warnings = validator._validate_shape_signals(graph)

        return ValidationSummary(errors=errors, warnings=warnings)

    def db_mismatches(self):
        """
        CLAUDE-EDIT 2026-06-18 (TRACKER.md section 3 item 17): real source
        for IntegrityView.db_mismatches, which was permanently hardcoded
        [] in truth/views.py with the comment "no DB comparison anymore."
        Investigated whether engine/structural_parity_diff.py's
        run_structural_diff() (the historical engine-vs-DB parity check
        that name likely meant) could be revived instead - it can't: it
        requires an in-memory file_analyses object Assessor's DB-only
        architecture never produces, and it has zero callers anywhere in
        the codebase (confirmed via grep) - wiring it would mean
        inventing fake engine-side data just to satisfy its signature,
        which is exactly what "never invent information" rules out.

        What IS real and already computed: run_integrity_check() already
        compares two independently-persisted tables that are supposed to
        stay in sync - graph_edges (what the query/graph layer reads) and
        symbol_references (what ingestion wrote) - and flags
        edge_count_mismatch when their counts disagree. That is a genuine
        DB-vs-DB mismatch, just never named "db_mismatches" or wired into
        the Truth Layer. This method extracts exactly that signal, and
        only that one - run_integrity_check()'s other signal,
        invalid_edge, is the same null-caller/callee check
        file_contract_reports() already surfaces as a
        symbol_reference_integrity contract violation, escalated into
        validation_summary().errors via _validate_contracts above;
        including it here too would just be the same finding under two
        names.
        """
        check = self.run_integrity_check()
        mismatches = []

        for kind, detail in check["errors"]:
            if kind == "edge_count_mismatch":
                mismatches.append(
                    f"edge_count_mismatch: graph_edges={detail['graph_edges']} "
                    f"vs symbol_references={detail['symbol_references']}"
                )

        return mismatches

    def integrity_view(self):
        return build_integrity_view(
            self.validation_summary(),
            self.snapshot(),
            db_mismatches=self.db_mismatches(),
        )

    # =====================================================
    # SUMMARY VIEW / SUBSYSTEM VIEW
    #
    # CLAUDE-EDIT 2026-06-16: wired up - these were builder functions
    # with no real caller anywhere (see Truth.md Phase 1 findings).
    # Both are pure transforms of data Assessor already computes:
    #   - summary_view() reuses reduced_snapshot() (edge_activity_total)
    #     and oracle.bucket_summary() (the same DB-authoritative
    #     project/builtin/classification_gap counts build_snapshot()
    #     already pulls) as the "metrics" payload, plus oracle.file_count().
    #   - subsystem_view() reuses the same graph snapshot every other
    #     view is built from.
    # No new DB queries, no new heuristics - just exposing data that
    # already existed under a name the query algebra can address.
    # =====================================================

    def summary_view(self):
        snapshot = self.build_snapshot()
        return build_system_summary_view(
            reduced=self.reduced_snapshot(),
            metrics=snapshot["bucket_summary"],
            file_count=snapshot["file_count"],
        )

    def subsystem_view(self):
        # CLAUDE-EDIT 2026-06-17: pass the real DB-backed symbol -> module
        # map (oracle/db_oracle.py's Phase 2 discovery API) so SUBSYSTEM
        # grouping resolves module identity from actual declaration
        # file_path instead of guessing from dotted symbol-name splitting.
        # See subsystem_view.py's _module() for the fallback behavior on
        # symbols with no captured declaration.
        #
        # CLAUDE-EDIT 2026-06-18 (TRACKER.md section 3 item 18): also pass
        # the same DB-authoritative builtin set structure_view() already
        # uses, so len/str/RuntimeError/print etc. are excluded from
        # subsystem dependency lists instead of showing up as fake
        # cross-subsystem architectural dependencies.
        return build_subsystem_view(
            self.snapshot(),
            module_map=self.oracle.symbol_module_map(),
            builtin_symbols=self.oracle.builtin_symbols(),
        )

    def role_view(self):
        # CLAUDE-EDIT 2026-06-16: sixth Truth Layer view, wired up per
        # Truth.md Phase 3/4 - responsibility_map() was real, DB-backed,
        # already-computed data with no path into Select()/Combine().
        # Same orphaned-primitive shape as the SUMMARY/SUBSYSTEM fix
        # earlier this session; same fix.
        return build_role_view(self.responsibility_map())

    def intent_view(self):
        return build_intent_view(self.oracle.conn)

    def explain_file(self, file_path: str) -> dict:
        return _explain_file(self.oracle.conn, file_path)

    def generate_task_md(self, symbol: str, out_path: str = None) -> str:
        return _generate_task_md(
            symbol=symbol, oracle=self.oracle, out_path=out_path,
            knowledge_conn=self._knowledge_conn,
        )

    def rereference_task_md(self, task_md_path: str, diff_out_path: str = None) -> dict:
        return _rereference_task_md(task_md_path=task_md_path, oracle=self.oracle, diff_out_path=diff_out_path)

    # =====================================================
    # INTENT LAYER - SUB-LAYER A: SEMANTIC SUMMARIES
    # (DESIGN.md section 3 / TRACKER.md item 12b)
    # AI-generated per-file/module/subsystem descriptions.
    # Lazy generation; source_hash for staleness detection.
    # =====================================================

    def semantic_summary(
        self,
        subject: str,
        kind: str = "file",
        source_text: str = "",
        *,
        force_refresh: bool = False,
    ) -> dict:
        """
        Return (and cache) an AI semantic summary for `subject`.
        For kind='file', reads the file automatically if source_text is
        not supplied - resolves relative paths against the project root.
        Returns a dict with content, source_hash, model_version,
        generated_at, cache_hit.
        """
        if kind == "file" and not source_text:
            source_text = self._read_source_file(subject)
        return _get_or_generate_summary(
            self.oracle.conn, subject, kind, source_text,
            force_refresh=force_refresh,
        )

    def _read_source_file(self, subject: str) -> str:
        """Read source file content, resolving relative paths via project root."""
        from pathlib import Path
        p = Path(subject)
        if not p.is_absolute():
            root = self.oracle.get_project_root()
            if root:
                p = Path(root) / subject
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def semantic_summary_if_fresh(
        self,
        subject: str,
        kind: str = "file",
        source_text: str = "",
    ) -> dict | None:
        """Return cached summary only if fresh; None if missing/stale."""
        return _get_summary_if_fresh(self.oracle.conn, subject, kind, source_text)

    def list_semantic_summaries(self, kind: str = None) -> list:
        """List all stored summaries, optionally filtered by kind."""
        return _list_summaries(self.oracle.conn, kind=kind)

    # =====================================================
    # INTENT LAYER - SUB-LAYER B: KNOWLEDGE ARTIFACTS
    # (DESIGN.md section 3 / TRACKER.md item 12b)
    # Durable findings, strategy decisions, confirmed facts.
    # Written deliberately, not auto-captured.
    # =====================================================

    def add_artifact(
        self,
        subject: str,
        kind: str,
        content: str,
        provenance: str = "ai-generated",
        file_hash: str = None,
    ) -> int:
        """
        Store a knowledge artifact in knowledge.db. Returns the new row id.
        subject   - file path, symbol, subsystem, or free-form topic.
        kind      - file_purpose / strategy_decision / query_finding /
                    design_note / known_issue.
        provenance - human-confirmed / ai-confirmed-by-human / ai-generated.
        file_hash  - SHA-256 of subject file at creation time (optional);
                     enables staleness detection on re-ingest.
        """
        if self._knowledge_conn is None:
            raise RuntimeError("No knowledge DB configured on this Assessor.")
        corpus = os.path.basename(getattr(self.oracle, "db_path", "") or "")
        return _add_artifact(self._knowledge_conn, subject, kind, content, provenance, file_hash, corpus=corpus)

    def get_artifacts(self, subject: str, kind: str = None) -> list:
        """
        Retrieve artifacts for `subject` from knowledge.db, scoped to the
        active corpus. Unscoped (legacy) artifacts are also returned.
        """
        if self._knowledge_conn is None:
            return []
        corpus = os.path.basename(getattr(self.oracle, "db_path", "") or "")
        return _get_artifacts(self._knowledge_conn, subject, kind=kind, corpus=corpus)

    def list_artifacts(self, kind: str = None, provenance: str = None) -> list:
        """List stored artifacts scoped to active corpus, optionally filtered by kind/provenance."""
        if self._knowledge_conn is None:
            return []
        corpus = os.path.basename(getattr(self.oracle, "db_path", "") or "")
        return _list_artifacts(self._knowledge_conn, kind=kind, provenance=provenance, corpus=corpus)

    def delete_artifact(self, artifact_id: int) -> bool:
        """Delete a single artifact by id. Returns True if removed."""
        if self._knowledge_conn is None:
            return False
        return _delete_artifact(self._knowledge_conn, artifact_id)

    def extract_design_facts(self, *, min_in_degree: int = 5) -> dict:
        """
        Extract structural facts from the corpus DB and store them as
        knowledge_artifacts. No LLM required. Safe to re-run: skips any
        subject that already has an artifact of the same kind.

        Extracts:
          - entry_points: public functions with in_degree == 0
          - dead_code:    functions with in_degree == 0 AND out_degree == 0
          - hot_symbols:  functions with in_degree >= min_in_degree
          - stub_files:   files containing stubs (is_stub=1)

        Returns a summary dict of counts written.
        """
        if self._knowledge_conn is None:
            return {"error": "No knowledge DB configured."}

        # existing subjects to avoid duplicates — keyed by subject prefix so this
        # is migration-safe regardless of which kind value old rows were stored with
        existing = {
            r[0]
            for r in self._knowledge_conn.execute(
                "SELECT subject FROM knowledge_artifacts WHERE subject LIKE 'entry::%' "
                "OR subject LIKE 'hot::%' OR subject LIKE 'dead::%' OR subject LIKE 'stubs::%'"
            ).fetchall()
        }

        counts = {"entry_points": 0, "dead_code": 0, "hot_symbols": 0, "stub_files": 0}

        # Build degree maps from project functions only (have a file_path entry)
        project_fns = {
            r[0]
            for r in self.oracle.conn.execute(
                "SELECT name FROM functions"
            ).fetchall()
        }
        in_deg: dict[str, int] = {}
        out_deg: dict[str, int] = {}
        for name in project_fns:
            in_deg[name] = 0
            out_deg[name] = 0
        for row in self.oracle.conn.execute("SELECT caller, callee FROM graph_edges").fetchall():
            caller = row[0]
            # callees are stored as receiver.method (e.g. character.is_alive) or
            # module.func; match on the final segment so method calls count toward
            # the bare project function's in_degree
            callee_last = row[1].rsplit(".", 1)[-1] if row[1] else row[1]
            if caller in out_deg:
                out_deg[caller] = out_deg.get(caller, 0) + 1
            if callee_last in in_deg:
                in_deg[callee_last] = in_deg.get(callee_last, 0) + 1

        fn_file = {
            r[0]: r[1]
            for r in self.oracle.conn.execute("SELECT name, file_path FROM functions").fetchall()
        }

        corpus = os.path.basename(getattr(self.oracle, "db_path", "") or "")

        for name in project_fns:
            if name.startswith("_"):
                continue  # skip private/dunder
            fp = fn_file.get(name, "")
            file_label = fp.replace("\\", "/").split("/")[-1] if fp else "?"
            i = in_deg.get(name, 0)
            o = out_deg.get(name, 0)

            # entry points: public, in_degree=0 but out_degree > 0
            subject_ep = f"entry::{name}"
            if i == 0 and o > 0 and subject_ep not in existing:
                _add_artifact(
                    self._knowledge_conn,
                    subject_ep,
                    "entry",
                    f"Entry point in {file_label}: {name} has no callers in corpus "
                    f"but calls {o} other functions.",
                    "ai-generated",
                    corpus=corpus,
                )
                existing.add(subject_ep)
                counts["entry_points"] += 1

            # dead code: public, no callers, no callees
            subject_dc = f"dead::{name}"
            if i == 0 and o == 0 and subject_dc not in existing:
                _add_artifact(
                    self._knowledge_conn,
                    subject_dc,
                    "dead",
                    f"Potential dead code in {file_label}: {name} has no callers "
                    f"and no callees in corpus.",
                    "ai-generated",
                    corpus=corpus,
                )
                existing.add(subject_dc)
                counts["dead_code"] += 1

            # hot symbols: high in_degree
            subject_hot = f"hot::{name}"
            if i >= min_in_degree and subject_hot not in existing:
                _add_artifact(
                    self._knowledge_conn,
                    subject_hot,
                    "hot",
                    f"Hot symbol in {file_label}: {name} has {i} callers "
                    f"(in_degree={i}, out_degree={o}).",
                    "ai-generated",
                    corpus=corpus,
                )
                existing.add(subject_hot)
                counts["hot_symbols"] += 1

        # stub-bearing files
        stub_files = self.oracle.conn.execute(
            "SELECT file_path, COUNT(*) as n FROM functions "
            "WHERE is_stub=1 GROUP BY file_path ORDER BY n DESC"
        ).fetchall()
        for row in stub_files:
            fp, n = row[0], row[1]
            file_label = fp.replace("\\", "/").split("/")[-1]
            subject_sf = f"stubs::{file_label}"
            if subject_sf not in existing:
                _add_artifact(
                    self._knowledge_conn,
                    subject_sf,
                    "stub",
                    f"{file_label} contains {n} stub function(s) with no implementation.",
                    "ai-generated",
                    corpus=corpus,
                )
                existing.add(subject_sf)
                counts["stub_files"] += 1

        self._knowledge_conn.commit()
        return counts

    # =====================================================
    # WORKFLOW STATE (mutable ranked planning items)
    # =====================================================

    def add_workflow_item(
        self,
        kind: str,
        subject: str,
        content: str,
        rank: int = None,
        provenance: str = "human",
    ) -> int:
        from determined.intent.workflow_store import add_item
        if self._knowledge_conn is None:
            raise RuntimeError("No knowledge DB configured on this Assessor.")
        return add_item(self._knowledge_conn, kind, subject, content, rank, provenance)

    def update_workflow_item(self, item_id: int, **kwargs) -> bool:
        from determined.intent.workflow_store import update_item
        if self._knowledge_conn is None:
            return False
        return update_item(self._knowledge_conn, item_id, **kwargs)

    def rerank_workflow(self, ordered_ids: list) -> int:
        from determined.intent.workflow_store import rerank_items
        if self._knowledge_conn is None:
            return 0
        return rerank_items(self._knowledge_conn, ordered_ids)

    def list_workflow_items(self, kind: str = None, status: str = "active") -> list:
        from determined.intent.workflow_store import list_items
        if self._knowledge_conn is None:
            return []
        return list_items(self._knowledge_conn, kind=kind, status=status)

    def workflow_status(self) -> str:
        from determined.intent.workflow_store import format_workflow_status
        if self._knowledge_conn is None:
            return "No knowledge DB configured."
        return format_workflow_status(self._knowledge_conn)

    def highest_provenance_artifact(self, subject: str, kind: str = None) -> dict | None:
        """Return the highest-provenance artifact for a subject, or None."""
        artifacts = self.get_artifacts(subject, kind=kind)
        return _highest_provenance(artifacts)

    # =====================================================
    # RESPONSIBILITY MAP / SNAPSHOT
    #
    # DB-derived equivalent of build_responsibility_map(), grouping
    # persisted symbol_references by file_path instead of needing
    # in-memory file_analyses.
    # =====================================================

    def responsibility_map(self):
        files_data = self.oracle.file_reference_map()

        files = []
        totals = defaultdict(int)

        for file_path, refs in files_data.items():
            text = " ".join(
                [file_path] + [r["callee"] or "" for r in refs]
            ).lower()

            roles = {
                role_name: any(p in text for p in patterns)
                for role_name, patterns in ROLE_PATTERNS.items()
            }

            for role_name, enabled in roles.items():
                if enabled:
                    totals[role_name] += 1

            files.append({
                "file_path": file_path,
                "roles": roles,
                "edge_count": len(refs),
            })

        return {
            "files": files,
            "totals": dict(totals),
        }

    def responsibility_snapshot(self):
        return build_responsibility_snapshot(
            responsibility_map=self.responsibility_map(),
            db_totals=self.build_snapshot(),
        )

    # =====================================================
    # REDUCED SNAPSHOT (run_engine Phase 4 fold step)
    # =====================================================

    def reduced_snapshot(self):
        return reduce([self.build_snapshot()])

    # =====================================================
    # SYSTEM REPORT
    #
    # Bundles everything run_engine produced AFTER db creation +
    # validation: Phase 3 views, Phase 4 snapshot/reduction, the
    # responsibility map, the invariants check, and (optionally)
    # the discovery/oracle-router debug queries from __main__.
    # =====================================================

    def system_report(self, sample_queries=None):
        report = {
            "snapshot": self.build_snapshot(),
            "reduced": self.reduced_snapshot(),
            "structure_view": self.structure_view(),
            "stability_view": self.stability_view(),
            "integrity_view": self.integrity_view(),
            "summary_view": self.summary_view(),
            "subsystem_view": self.subsystem_view(),
            "responsibility": self.responsibility_snapshot(),
            "run_integrity_check": self.run_integrity_check(),
            "self_model": self.self_model(),
        }

        if sample_queries:
            session = self.session()
            report["queries"] = {}

            for q in sample_queries:
                raw = session.run_query(q)
                summary = raw.summary()
                report["queries"][q] = summary

        return report

    def self_model(self):
        return SystemSelfModelBuilder(self.oracle).build()
# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def main():
    oracle = DBOracle("corpus.db")
    assessor = Assessor(oracle)

    result = assessor.run("re.sub")

    print("symbol:", result["symbol"])
    print("neighbors:", result["neighbors"])
    print("surface:", result["surface"])
    print("influence:", result["influence"])

    print("\nvalidation:", result["validation"])
    print("\nsnapshot:", result["snapshot"])

    # -----------------------------------------------------
    # SYSTEM REPORT (migrated from run_engine post-persist phases)
    # -----------------------------------------------------
    report = assessor.system_report(sample_queries=[
        "what depends on resolve_analysis_db_path",
        "show ingestion surface",
        "what affects engine snapshot",
    ])

    print("\n=== REDUCED SNAPSHOT ===")
    print(report["reduced"])

    print("\n=== STRUCTURE VIEW ===")
    print("edges:", len(report["structure_view"].edges))
    print("hotspots:", report["structure_view"].hotspots[:10])

    print("\n=== STABILITY VIEW ===")
    print(report["stability_view"])

    print("\n=== INTEGRITY VIEW ===")
    print(report["integrity_view"])

    print_responsibility_map(report["responsibility"])

    print("\n=== RUN INTEGRITY CHECK ===")
    print(report["run_integrity_check"])

    print("\n=== ORACLE ROUTER ===")

    for q, res in report["queries"].items():
        print("\nQUERY:", q)
        print("intent:", res["intent"])
        print("seeds:", res["seeds"][:5])
        print("expanded:", res["expanded"][:5])

if __name__ == "__main__":
    main()
