# tools/analysis/oracle/db_oracle.py

import logging
import os
import sqlite3
import sys
from typing import Any, Dict, List, Tuple
from collections import defaultdict, deque
from determined.graph.graph_builder import GraphEdge, GraphBundle
from determined.oracle.edge_semantics import interpret_edge
from determined.oracle.symbol_noise import is_accessor_chain_noise

_logger = logging.getLogger(__name__)

# =========================================================
# DB ORACLE CORE
# =========================================================

def _file_path_to_module(file_path: str, project_root: str = "") -> str:
    """
    Derive a deterministic module identity from a real file_path - the
    DB-backed replacement for guessing module identity from dotted
    symbol-name splitting (see truth/subsystem_view.py's old _module()).
    A "module" is the file's containing directory, dotted
    (e.g. "tools/analysis/oracle/db_oracle.py" -> "determined.oracle").
    Files at the project root map to their own stem (no containing dir).

    `project_root`, when supplied, is stripped off `file_path` first -
    this is what keeps the dotted result project-relative
    ("determined.oracle") instead of carrying the full absolute
    filesystem path ("sessions.<id>.mnt.myproject.determined.oracle" on
    this session's sandbox, or a drive-letter-polluted equivalent on
    Bart's Windows checkout). Closes TRACKER.md open item 16. Default
    "" preserves the exact prior (unpollution-aware) behavior for any
    caller that doesn't have a project_root to give - see
    DBOracle.get_project_root() for how real callers obtain one.
    """
    if not file_path:
        return ""

    normalized = file_path.replace("\\", "/")

    if project_root:
        root_norm = project_root.replace("\\", "/").rstrip("/")
        if root_norm:
            if normalized == root_norm:
                normalized = ""
            elif normalized.startswith(root_norm + "/"):
                normalized = normalized[len(root_norm) + 1:]

    parts = [p for p in normalized.split("/") if p]

    if not parts:
        return ""

    dir_parts = parts[:-1]
    if not dir_parts:
        return parts[-1].rsplit(".", 1)[0]

    return ".".join(dir_parts)


class DBOracle:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.db_path = db_path
        self._project_root = None  # lazily resolved, see get_project_root()

    # -----------------------------
    # PROJECT ROOT (for trimming absolute file_path values - item 16)
    # -----------------------------

    def get_project_root(self) -> str:
        """
        Real project root for trimming absolute file_path values down to
        a project-relative module identity (see module-level
        _file_path_to_module()). Prefers the value persisted at
        ingestion time (persistence_engine.set_project_root(), written
        from EngineRunner.run()'s repo_root); for DBs ingested before
        that was wired - or any DB missing the row for another reason -
        falls back to the longest common directory prefix across every
        distinct `files.file_path` row. That fallback is an inference,
        not an authoritative value: exact when ingestion scanned one
        contiguous root (the normal case), unreliable if the DB mixes
        file_paths from more than one root. Cached after first call - a
        DB's project root doesn't change within one DBOracle's lifetime.
        """
        if self._project_root is not None:
            return self._project_root

        root = ""
        cur = self.conn.cursor()
        try:
            row = cur.execute(
                "SELECT value FROM project_meta WHERE key = 'project_root'"
            ).fetchone()
            if row and row["value"]:
                root = row["value"]
        except sqlite3.OperationalError:
            # legacy DB, ingested before project_meta existed
            root = ""

        if not root:
            root = self._infer_project_root()

        self._project_root = root
        return root

    def _infer_project_root(self) -> str:
        """
        Fallback used only when no project_root was ever persisted:
        longest common directory prefix across every distinct
        `files.file_path`. Needs at least 2 distinct files to mean
        anything - with only one, os.path.commonpath would return the
        file itself (including its filename) rather than a directory,
        which would silently corrupt every module identity instead of
        just leaving them untrimmed, so that case intentionally returns
        "" (no trimming, identical to the pre-item-16 behavior).
        """
        cur = self.conn.cursor()
        try:
            rows = cur.execute(
                "SELECT DISTINCT file_path FROM files WHERE file_path IS NOT NULL"
            ).fetchall()
        except sqlite3.OperationalError:
            return ""

        paths = [r["file_path"].replace("\\", "/") for r in rows if r["file_path"]]
        if len(paths) < 2:
            return ""

        try:
            common = os.path.commonpath(paths)
        except ValueError:
            # e.g. mixed drive letters on Windows - no safe common root
            return ""

        return common.replace("\\", "/")

    # -----------------------------
    # SEMANTIC EDGES
    # -----------------------------

    def get_semantic_edges(self):
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT caller, callee, line_number
            FROM graph_edges
            WHERE caller IS NOT NULL
              AND callee IS NOT NULL
        """).fetchall()

        return [
            interpret_edge(
                GraphEdge(
                    caller=r["caller"],
                    callee=r["callee"],
                    line_number=r["line_number"],
                )
            )
            for r in rows
        ]

    # -----------------------------
    # FILE COUNT (FIXED LOCATION)
    # -----------------------------

    def file_count(self) -> int:
        cur = self.conn.cursor()
        return cur.execute("""
            SELECT COUNT(DISTINCT file_path)
            FROM symbol_references
            WHERE file_path IS NOT NULL
        """).fetchone()[0]

    # -----------------------------
    # GRAPH EDGE QUERIES
    # -----------------------------

    def neighbors(self, symbol: str) -> dict:
        cur = self.conn.cursor()

        cur.execute("""
            SELECT callee
            FROM graph_edges
            WHERE caller = ?
        """, (symbol,))
        calls = sorted({r["callee"] for r in cur.fetchall()})

        cur.execute("""
            SELECT caller
            FROM graph_edges
            WHERE callee = ?
        """, (symbol,))
        called_by = sorted({r["caller"] for r in cur.fetchall()})

        return {
            "symbol": symbol,
            "calls": calls,
            "called_by": called_by,
        }

    # -----------------------------
    # FORWARD WALK (surface)
    # -----------------------------

    def surface(self, symbol: str, depth: int = 1) -> List[str]:
        visited = set()
        frontier = {symbol}
        result = set()

        for _ in range(depth):
            next_frontier = set()

            for node in frontier:
                cur = self.conn.cursor()
                cur.execute("""
                    SELECT callee FROM graph_edges WHERE caller = ?
                """, (node,))

                for row in cur.fetchall():
                    tgt = row["callee"]
                    if tgt not in visited:
                        result.add(tgt)
                        next_frontier.add(tgt)

            visited.update(frontier)
            frontier = next_frontier

        return sorted(result)

    # -----------------------------
    # REVERSE WALK (influence)
    # -----------------------------

    def influence(self, symbol: str, depth: int = 1) -> List[str]:
        visited = set()
        frontier = {symbol}
        result = set()

        for _ in range(depth):
            next_frontier = set()

            for node in frontier:
                cur = self.conn.cursor()
                cur.execute("""
                    SELECT caller FROM graph_edges WHERE callee = ?
                """, (node,))

                for row in cur.fetchall():
                    src = row["caller"]
                    if src not in visited:
                        result.add(src)
                        next_frontier.add(src)

            visited.update(frontier)
            frontier = next_frontier

        return sorted(result)

    def get_snapshot_graph(self) -> GraphBundle:
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT caller, callee, line_number
            FROM graph_edges
            WHERE caller IS NOT NULL
              AND callee IS NOT NULL
        """).fetchall()

        edges = [
            GraphEdge(
                caller=r["caller"],
                callee=r["callee"],
                line_number=r["line_number"],
            )
            for r in rows
        ]

        bucket_counts = {
            "total": len(edges)
        }

        return GraphBundle(
            edges=edges,
            bucket_counts=bucket_counts
        )

    def get_edge_maps(self):
        """
        Returns (forward, reverse) adjacency dicts built from graph_edges.
        forward[caller] = set of callees; reverse[callee] = set of callers.
        Pure data access - no GraphBundle dependency; used by the query path
        to avoid importing from the graph engine layer.
        """
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT caller, callee FROM graph_edges "
            "WHERE caller IS NOT NULL AND callee IS NOT NULL"
        ).fetchall()
        forward = {}
        reverse = {}
        for r in rows:
            forward.setdefault(r["caller"], set()).add(r["callee"])
            reverse.setdefault(r["callee"], set()).add(r["caller"])
        return forward, reverse

    def builtin_symbols(self) -> set:
        """
        Returns the set of all symbols that appear exclusively as builtins
        in symbol_references. A symbol is considered builtin if every
        reference to it (as caller or callee) is bucket='builtin'.
        Used by build_structure_view to exclude builtins from hotspot ranking.
        """
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT symbol, MIN(bucket) as min_bucket, MAX(bucket) as max_bucket
            FROM (
                SELECT caller as symbol, bucket FROM symbol_references
                    WHERE caller IS NOT NULL
                UNION ALL
                SELECT callee as symbol, bucket FROM symbol_references
                    WHERE callee IS NOT NULL
            )
            GROUP BY symbol
        """).fetchall()

        builtins = set()

        for r in rows:
            if r["min_bucket"] == "builtin" and r["max_bucket"] == "builtin":
                builtins.add(r["symbol"])

        return builtins

    def snapshot(self):
        return self.get_snapshot_graph()

    # -----------------------------
    # BUCKET SUMMARY (symbol_references is the only table
    # that actually carries bucket info — graph_edges does not)
    # -----------------------------

    def bucket_summary(self) -> dict:
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT bucket, COUNT(*) as cnt
            FROM symbol_references
            WHERE caller IS NOT NULL
              AND callee IS NOT NULL
            GROUP BY bucket
        """).fetchall()

        summary = {
            "project": 0,
            "builtin": 0,
            "classification_gap": 0,
        }

        for r in rows:
            bucket = r["bucket"]
            if bucket not in summary:
                bucket = "classification_gap"
            summary[bucket] += r["cnt"]

        return summary

    # -----------------------------
    # SYMBOL REFERENCE COUNT (DB total, mirrors ingestion fact)
    # -----------------------------

    def symbol_reference_count(self) -> int:
        cur = self.conn.cursor()
        return cur.execute("""
            SELECT COUNT(*) FROM symbol_references
        """).fetchone()[0]

    # -----------------------------
    # PER-FILE SYMBOL REFERENCES (DB analogue of file_analyses)
    # -----------------------------

    def file_reference_map(self) -> Dict[str, List[Dict[str, Any]]]:
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT file_path, caller, callee, line_number, bucket
            FROM symbol_references
            WHERE file_path IS NOT NULL
            ORDER BY file_path
        """).fetchall()

        files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for r in rows:
            files[r["file_path"]].append({
                "caller": r["caller"],
                "callee": r["callee"],
                "line_number": r["line_number"],
                "bucket": r["bucket"],
            })

        return dict(files)

    # =====================================================
    # SEED DISCOVERY (DB-OWNED, NO EXTERNAL MODULE)
    # =====================================================
    def discover_seed_symbols(self, text: str, limit: int = 50) -> list:
        """
        Primary seed discovery — combines token-based and semantic (embedding)
        results when sentence-transformers is available, falls back to
        token-only otherwise.

        Token results lead (high precision on exact terminology).
        Semantic results follow (conceptual reach for queries with no
        token overlap). Duplicates are removed preserving order.
        """
        try:
            import numpy as np
            from determined.oracle.embedding_model import embed_text
            return self._discover_combined(text, limit)
        except ImportError:
            return self._discover_token(text, limit)

    def _discover_token(self, text: str, limit: int = 50) -> list:
        """
        Token-based seed discovery. Seeds are drawn from symbol_references
        (not graph_edges) so bucket filtering is available.

        Scoring:
          +4  exact symbol name match (case-insensitive)
          +3  query text is a substring of the symbol
          +2  symbol tail (last segment) contains the full query
          +1  per overlapping signal token (longer tokens weighted +1 extra)

        Minimum score of 2 required — single loose token matches excluded.
        Builtins are never seeds regardless of score.
        """
        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT DISTINCT caller as symbol, bucket FROM symbol_references
                WHERE caller IS NOT NULL
            UNION
            SELECT DISTINCT callee as symbol, bucket FROM symbol_references
                WHERE callee IS NOT NULL
        """).fetchall()

        text_lower = text.lower()
        text_tokens = set(
            text_lower
            .replace("_", " ")
            .replace(".", " ")
            .split()
        )

        WEAK_TOKENS = {"on", "in", "at", "to", "of", "is", "a", "an",
                       "the", "for", "with", "from", "by", "or", "and"}

        signal_tokens = {t for t in text_tokens if t not in WEAK_TOKENS}

        scored = []
        seen_sym = set()

        for r in rows:
            sym = r["symbol"]
            bucket = r["bucket"]

            if bucket == "builtin":
                continue

            if sym in seen_sym:
                continue
            seen_sym.add(sym)

            # Accessor-chain noise (e.g. "cursor.self.oracle.conn",
            # "split.i.surface") — canonical definition lives in
            # symbol_noise.py so expansion-time filtering (oracle_router)
            # stays in sync with discovery-time filtering.
            if is_accessor_chain_noise(sym):
                continue

            sym_lower = sym.lower()
            sym_tokens = set(
                sym_lower
                .replace(".", " ")
                .replace("_", " ")
                .split()
            )

            score = 0

            if text_lower == sym_lower:
                score += 4

            if text_lower in sym_lower:
                score += 3

            sym_tail = sym_lower.split(".")[-1]
            if text_lower in sym_tail:
                score += 2

            for tok in signal_tokens & sym_tokens:
                score += 1 + (1 if len(tok) > 5 else 0)

            if score >= 2:
                scored.append((score, sym))

        scored.sort(reverse=True, key=lambda x: x[0])

        seen = set()
        out = []

        for _, s in scored:
            if s not in seen:
                seen.add(s)
                out.append(s)

            if len(out) >= limit:
                break

        return out

    def _discover_combined(self, text: str, limit: int = 50) -> list:
        """
        Combined token + semantic seed discovery.

        Token results come first (high precision).
        Semantic results follow (conceptual reach).
        Duplicates removed preserving order.
        Total capped at limit.
        """
        token_results = self._discover_token(text, limit)
        semantic_results = self.discover_seed_symbols_semantic(text, limit)

        seen = set()
        combined = []

        for sym in token_results + semantic_results:
            if sym not in seen:
                seen.add(sym)
                combined.append(sym)
            if len(combined) >= limit:
                break

        return combined

    # =====================================================
    # EMBEDDING-BASED SEED DISCOVERY
    #
    # Semantic alternative to discover_seed_symbols().
    # Uses all-MiniLM-L6-v2 (384-dim) to embed query text
    # and all project symbols, then ranks by cosine similarity.
    #
    # Advantages over token-based:
    #   - Finds "character state persistence" → persist_character_state
    #     even with no token overlap
    #   - Immune to token stop-word issues
    #   - Degrades gracefully: falls back to token-based if model unavailable
    #
    # The embedding index is built once and cached in self._embedding_index.
    # Call build_embedding_index() to pre-warm; discover_seed_symbols_semantic()
    # builds it lazily on first call.
    # =====================================================

    def build_embedding_index(self) -> int:
        """
        Build the in-memory embedding index over all non-builtin symbols.
        Returns the number of symbols indexed.
        Called lazily by discover_seed_symbols_semantic() on first use,
        or explicitly to pre-warm before a batch of queries.
        """
        import numpy as np
        from determined.oracle.embedding_model import embed_symbol

        cur = self.conn.cursor()

        rows = cur.execute("""
            SELECT DISTINCT caller as symbol, bucket FROM symbol_references
                WHERE caller IS NOT NULL
            UNION
            SELECT DISTINCT callee as symbol, bucket FROM symbol_references
                WHERE callee IS NOT NULL
        """).fetchall()

        symbols = []
        vectors = []

        for r in rows:
            if r["bucket"] == "builtin":
                continue
            sym = r["symbol"]
            if sym in {s for s, _ in symbols}:
                continue
            # Skip accessor-chain symbols (same rule as _discover_token)
            segs = sym.lower().split(".")
            if any(seg in ("self", "cursor", "cls", "ctx") for seg in segs):
                continue
            if len(segs) >= 3 and any(len(seg) <= 2 for seg in segs[1:-1]):
                continue
            vec = embed_symbol(sym)
            symbols.append((sym, r["bucket"]))
            vectors.append(vec)

        if vectors:
            self._embedding_index = {
                "symbols": symbols,
                "matrix": np.stack(vectors),   # (N, 384)
            }
        else:
            self._embedding_index = {"symbols": [], "matrix": None}

        return len(symbols)

    def discover_seed_symbols_semantic(
        self,
        text: str,
        limit: int = 20,
        min_score: float = 0.25,
    ) -> list:
        """
        Embedding-based seed discovery. Ranks all non-builtin symbols
        by cosine similarity to the query text.

        min_score: minimum similarity threshold (0.0-1.0).
                   0.25 works well for all-MiniLM-L6-v2 — below this
                   similarity is essentially noise.

        Falls back to _discover_token() (token-based) if the
        sentence-transformers package is not installed, or if the
        embedding model fails to load/run for any other reason (e.g.
        a network or cache failure after a successful import - see
        TRACKER.md item 22). Falls back to _discover_token() directly
        rather than discover_seed_symbols(), since discover_seed_symbols()
        -> _discover_combined() -> this method would re-enter the same
        failing path and recurse.
        """
        try:
            import numpy as np
            from determined.oracle.embedding_model import embed_text
        except ImportError:
            return self._discover_token(text, limit)

        try:
            # lazy build
            if not hasattr(self, "_embedding_index") or self._embedding_index is None:
                self.build_embedding_index()

            index = self._embedding_index

            if not index["symbols"] or index["matrix"] is None:
                return self._discover_token(text, limit)

            query_vec = embed_text(text)                        # (384,)
            scores = index["matrix"] @ query_vec               # (N,) cosine similarity

            ranked = sorted(
                zip(scores, [s for s, _ in index["symbols"]]),
                reverse=True,
            )

            return [
                sym for score, sym in ranked
                if score >= min_score
            ][:limit]
        except Exception as e:
            _logger.warning(
                "Embedding-based seed discovery failed (%s: %s); falling back to token-based discovery.",
                type(e).__name__, e,
            )
            return self._discover_token(text, limit)

    # =====================================================
    # DISCOVERY API (PHASE 2 - DBReader-only bootstrap layer)
    #
    # CLAUDE-EDIT 2026-06-17: REFACTOR OPS BOARD.md PHASE 2 / Track A -
    # "expose a DB-backed symbol discovery API
    # (list_symbols/find_symbols/find_files/find_modules, DBReader-only)
    # as the single unified seed-bootstrap entrypoint." These are
    # general-purpose discovery/browsing primitives, distinct from
    # discover_seed_symbols() above (which does NL-query relevance
    # scoring specifically for route_query's seed step - left unchanged,
    # still the right tool for that job). Both read exclusively from the
    # DB (symbols/files tables) - no engine state, no in-memory fallback.
    # Confirmed by grep: route_query's only production caller
    # (QuerySession.run_query()) already passes self.oracle.
    # discover_seed_symbols, so there was never a live caller-injected
    # seed path - this section closes Phase 1's "seed discipline
    # enforcement" checkbox by giving that existing DB-only contract a
    # real, general-purpose discovery layer to sit next to, instead of
    # one ad-hoc NL-scoring method standing alone.
    # =====================================================

    def list_symbols(self, symbol_type: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        list_symbols([symbol_type]) - enumerate symbols from the `symbols`
        table (real ingestion-time data: file_path, symbol_type, name,
        line_number, signature, canonical_id). symbol_type is one of
        'function'/'class' (true declarations) or 'caller'/'callee'
        (call-graph participant records - see persistence_engine.py's
        _persist_file_analysis). DBReader-only: a single SELECT, no
        engine/in-memory fallback.
        """
        cur = self.conn.cursor()
        query = (
            "SELECT name, file_path, symbol_type, line_number, signature, "
            "canonical_id FROM symbols"
        )
        params: list = []
        if symbol_type:
            query += " WHERE symbol_type = ?"
            params.append(symbol_type)
        query += " ORDER BY file_path, line_number"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = cur.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def find_symbols(
        self,
        pattern: str,
        symbol_type: str = None,
        exact: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        find_symbols(pattern) - literal name lookup against the `symbols`
        table. exact=True does an exact name match; exact=False (default)
        does a substring match. Distinct from discover_seed_symbols(),
        which ranks symbols by NL-query relevance for route_query's seed
        step - find_symbols is the general "does a symbol named/matching
        X exist, and where is it" primitive used for direct lookups.
        DBReader-only.
        """
        cur = self.conn.cursor()
        conditions = []
        params: list = []

        if exact:
            conditions.append("name = ?")
            params.append(pattern)
        else:
            conditions.append("name LIKE ?")
            params.append(f"%{pattern}%")

        if symbol_type:
            conditions.append("symbol_type = ?")
            params.append(symbol_type)

        where = " AND ".join(conditions)
        # Rank by project reference count so the most architecturally
        # central symbols surface first. Three callee forms are checked:
        # exact name, module.name suffix (qualified imports), and
        # name.self.obj prefix (method call chains). Falls back to
        # file/line for ties.
        query = (
            "SELECT s.name, s.file_path, s.symbol_type, s.line_number, "
            "s.signature, s.canonical_id, "
            "(SELECT COUNT(*) FROM symbol_references sr "
            " WHERE sr.bucket = 'project' "
            "   AND (sr.callee = s.name "
            "        OR sr.callee LIKE '%.' || s.name "
            "        OR sr.callee LIKE s.name || '.%')) AS caller_count "
            f"FROM symbols s WHERE {where} "
            "ORDER BY caller_count DESC, s.file_path, s.line_number LIMIT ?"
        )
        params.append(limit)

        rows = cur.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def find_files(
        self,
        pattern: str = None,
        role: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        """
        find_files([pattern], [role]) - query the `files` table (real
        ingestion-time metadata: file_path, line_count, role, is_hot).
        pattern does a substring match on file_path; role does an exact
        match on the classified role (see engine/responsibility_map.py).
        DBReader-only.
        """
        cur = self.conn.cursor()
        conditions = []
        params: list = []

        if pattern:
            conditions.append("file_path LIKE ?")
            params.append(f"%{pattern}%")
        if role:
            conditions.append("role = ?")
            params.append(role)

        query = "SELECT file_path, line_count, role, is_hot FROM files"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY file_path"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = cur.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def find_modules(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        find_modules() - derive module grouping from the real `files`
        table by containing directory (see module-level
        _file_path_to_module()). There is no separate "modules" table -
        `imports.module` records modules a file imports FROM, not the
        file's own module identity - so this is the DB-backed source of
        truth for "what modules does this project actually have",
        grouped from real file_path data rather than guessed from
        symbol-name string splitting (the bug symbol_module_map() below
        replaces in truth/subsystem_view.py). DBReader-only.
        """
        cur = self.conn.cursor()
        rows = cur.execute("SELECT file_path FROM files ORDER BY file_path").fetchall()

        project_root = self.get_project_root()
        modules: Dict[str, List[str]] = defaultdict(list)
        for r in rows:
            modules[_file_path_to_module(r["file_path"], project_root)].append(r["file_path"])

        result = [
            {"module": m, "files": sorted(fs), "file_count": len(fs)}
            for m, fs in sorted(modules.items())
        ]

        if limit:
            result = result[:limit]

        return result

    def symbol_module_map(self) -> Dict[str, str]:
        """
        DB-backed symbol -> module map, built from real declarations
        (symbol_type IN ('function', 'class') in the `symbols` table -
        i.e. the file that actually DEFINES the symbol, not just a file
        that references it as a caller/callee). Used by
        truth/subsystem_view.py to replace its dotted-name-splitting
        heuristic with real data (REFACTOR OPS BOARD.md / Truth.md Phase 3
        Row 4: SUBSYSTEM grouping fragmenting into near-singleton groups
        because this codebase's symbols are mostly bare names, not
        dotted-module-qualified).

        Ambiguous names (the same bare name defined in more than one
        file) resolve deterministically to the alphabetically-first
        file_path - real-world collisions are rare and this keeps the
        map a pure function of DB content, no extra heuristics. Symbols
        with no captured declaration (builtins, external-library calls,
        accessor-chain noise) are simply absent from the map; callers
        fall back to their own heuristic for those.
        """
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            SELECT name, file_path FROM symbols
            WHERE symbol_type IN ('function', 'class')
            ORDER BY name, file_path
            """
        ).fetchall()

        project_root = self.get_project_root()
        mapping: Dict[str, str] = {}
        for r in rows:
            name = r["name"]
            if name not in mapping:
                mapping[name] = _file_path_to_module(r["file_path"], project_root)

        return mapping

# not class functions here...


# =========================================================
# INTERNAL INDEX BUILDER (STRUCTURAL ONLY)
# =========================================================

def _edges(graph):
    return getattr(graph, "edges", [])


def _build_index(graph):
    forward = defaultdict(set)
    reverse = defaultdict(set)

    for e in _edges(graph):
        forward[e.caller].add(e.callee)
        reverse[e.callee].add(e.caller)

    return forward, reverse


# =========================================================
# CONTEXT (was neighbors)
# =========================================================

def context(graph: Any, symbol: str) -> Dict[str, Any]:
    forward, reverse = _build_index(graph)

    return {
        "symbol": symbol,
        "calls": sorted(forward.get(symbol, [])),
        "called_by": sorted(reverse.get(symbol, [])),
    }


# =========================================================
# SURFACE (forward dependency)
# =========================================================

def surface(graph: Any, symbol: str, depth: int = 1) -> List[str]:
    forward, _ = _build_index(graph)

    visited = set()
    queue = deque([(symbol, 0)])
    result = set()

    while queue:
        node, d = queue.popleft()

        if node in visited:
            continue
        visited.add(node)

        if d > 0:
            result.add(node)

        if d < depth:
            for nxt in forward.get(node, []):
                queue.append((nxt, d + 1))

    return sorted(result)


# =========================================================
# INFLUENCE (reverse dependency)
# =========================================================

def influence(graph: Any, symbol: str, depth: int = 1) -> List[str]:
    _, reverse = _build_index(graph)

    visited = set()
    queue = deque([(symbol, 0)])
    result = set()

    while queue:
        node, d = queue.popleft()

        if node in visited:
            continue
        visited.add(node)

        if d > 0:
            result.add(node)

        if d < depth:
            for nxt in reverse.get(node, []):
                queue.append((nxt, d + 1))

    return sorted(result)


def engine_query(graph, symbol: str, depth: int = 1):
    """
    Single deterministic reasoning surface over the graph.

    This is the ONLY supported external query abstraction.
    """

    return {
        "symbol": symbol,
        "context": context(graph, symbol),
        "surface": surface(graph, symbol, depth=depth),
        "influence": influence(graph, symbol, depth=depth),
    }

# =========================================================
# CLI INTERFACE
# =========================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python db_oracle.py <db_path>")
        sys.exit(1)

    oracle = DBOracle(sys.argv[1])

    print("\nDB ORACLE READY")
    print("Commands:")
    print("  neighbors <symbol>")
    print("  surface <symbol> [depth]")
    print("  influence <symbol> [depth]")
    print("  exit\n")

    while True:
        cmd = input("oracle> ").strip().split()

        if not cmd:
            continue

        if cmd[0] == "exit":
            break

        if cmd[0] == "neighbors":
            res = oracle.neighbors(cmd[1])
            print(res)

        elif cmd[0] == "surface":
            depth = int(cmd[2]) if len(cmd) > 2 else 1
            res = oracle.surface(cmd[1], depth)
            print(res)

        elif cmd[0] == "influence":
            depth = int(cmd[2]) if len(cmd) > 2 else 1
            res = oracle.influence(cmd[1], depth)
            print(res)

        else:
            print("unknown command")


if __name__ == "__main__":
    main()