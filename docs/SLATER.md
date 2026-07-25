# Slater Integration Arc

_Written 2026-07-22. Moved from TRACKER.md 2026-07-25._

**Source:** https://github.com/Hikari-Systems/slater
Slater is a Rust graph database that serves graphs that don't fit in memory
(hundreds of millions of nodes, billions of edges) in low hundreds of MB of RAM,
via the standard Bolt protocol. Any neo4j driver works unchanged. Disk-native
vector search (Vamana + PQ; cosine/L2/dot ANN) lives next to the graph.
Written with Claude Code. Open source, Apache-2.0.

**Idea 1 (Slater as Rust corpus):** DONE — probe complete 2026-07-22 (session 237).
195 files, 0 stubs, 1985 inferred EPs (all tests/benchmarks, correct for library crate).
See RM67 language scope table.

Ideas 2-6 below are design principles and future work, each gated.

---

## Idea 2 — Build/serve split as corpus generation model (feeds RM69 design)

Slater's architecture: `slater-build` compiles a graph offline into a content-addressed
immutable "generation" directory; `slater` serves from it with a bounded cache.
Swapping generations is atomic (one `current` pointer flip).

**The steal for RM69:** adopt the generation model in Determined's aggregation layer:
- Ingest = build pass. Produces a frozen, content-identified corpus snapshot.
- Query layer serves from the frozen snapshot. Never mutates it mid-query.
- Re-ingest produces a new generation, not in-place mutation of the existing DB.
- One "current" record points to the active generation.

**Why:** aggregation tools produce corpus-wide summaries that need to be stable within
a session. A re-ingest mid-session should not silently invalidate them.

**Implementation shape:**
- `ingestion/generation.py` — `GenerationManifest(corpus_path, ingest_sha, timestamp,
  symbol_count, edge_count)`; written as `generation_manifest.json` next to the DB
- Query tools read the manifest at startup; warn if manifest absent or stale
- `corpus_aggregation.py` stamps summaries with `generation_id`

**Gate: implement when RM69 architecture is being designed.**

---

## Idea 3 — Vector + graph colocation (design principle for RM69)

Slater shows that vector KNN and graph traversal can be one query:
```cypher
MATCH (n:Function)
WHERE db.idx.vector.queryNodes(n, $embedding, 10)
RETURN n, [(n)-[:CALLS]->(m) | m] AS callees
```

Today Determined keeps embeddings in `semantic_summaries` and call edges in
`graph_edges` — joined in Python across two queries.

**The principle (apply at RM69 design time, not before):** when designing RM69's
aggregation layer, make the schema choice that keeps embeddings and their associated
graph edges co-queryable — same table join with a covering index, or a single tool
call that fetches both in one DB round-trip.

`subsystem_shape` and `prerequisite_map` will need both semantic clustering
(embedding similarity) and structural clustering (call graph proximity). Design the
query so those two signals are gathered together.

**Gate: RM69 active.**

---

## Idea 4 — Cypher as graph query interface (future migration)

Determined's graph queries are raw SQL with Python BFS loops. Cypher is native to
the questions Determined asks.

**Side-by-side:**

| Question | Current (SQL + Python) | Cypher |
|---|---|---|
| Stubs and caller counts | 2-table JOIN + GROUP BY | `MATCH (c)-[:CALLS]->(s {is_stub:1}) RETURN s.name, count(c)` |
| 5-hop call chain | BFS loop ~40 lines | `MATCH p=(s)-[:CALLS*..5]->(n) RETURN p` |
| Files by stub density | subquery + ORDER BY | `MATCH (f)-[:CONTAINS]->(s {is_stub:1}) RETURN f.path, count(s) ORDER BY count(s) DESC` |
| Sibling stubs | self-join SQL | `MATCH (c)-[:CALLS]->(s1 {is_stub:1}), (c)-[:CALLS]->(s2) WHERE s1<>s2 RETURN s1,s2` |

**Node types:**
- `:Function` — name, fqdn, file_path, is_stub, is_tool, is_entry_point, body_shape, http_route, language
- `:File` — path, language, role
- `:Module` — name, package

**Edge types:** `:CALLS`, `:IMPORTS`, `:CONTAINS`, `:FUNCTION_REFERENCE`, `:DATA_FLOW`,
`:HTTP_FETCH`, `:JS_EVENT_BINDING`

**Migration steps:**
1. `scripts/export_to_cypher.py` — reads corpus DB, emits `.cypher` dump
2. Run `slater-build --input dump.cypher --graph <name> --data-dir <dir>`
3. Start `slater` on port 7687
4. `pip install neo4j`
5. `determined/graph/bolt_oracle.py` — wraps neo4j driver, same interface as current SQLite graph queries
6. Parallel-run test suite: every graph tool against both SQLite and Bolt paths, assert identical results
7. Once parallel tests pass on dj2 + one non-Python corpus: drop SQLite graph path

**Gate: not before SQLite becomes a query bottleneck OR MCTS arc makes multi-hop
Cypher clearly worthwhile. Likely after 2-3 large C/Zig corpora and measurable
query latency.**

---

## Idea 5 — Scale path for large corpora (observation)

SQLite is fine up to ~50K edges. Slater's bounded-memory model keeps RSS flat
regardless of graph size.

**Trigger to act:** ingest a C corpus and run `blast_radius` on a widely-called
symbol. If > 5 seconds on a 100K-edge corpus, migrate to Idea 4 (Cypher/Bolt)
as the fix — not SQLite optimization.

**No action until triggered.**

---

## Idea 6 — MCTS evidence gathering over Bolt (downstream of MCTS arc)

MCTS requires iterative call graph traversal as the evidence-gathering step.
In Python+SQLite this is recursive BFS: multiple DB round-trips, Python graph
objects, manual dedup. In Cypher over Bolt:

```cypher
-- All paths from stub to depth 5:
MATCH p = (stub {name: $name})-[:CALLS*..5]->(n)
WHERE NOT n.is_external
RETURN p

-- Sibling stubs (share a caller):
MATCH (c)-[:CALLS]->(s1 {is_stub:1}), (c)-[:CALLS]->(s2 {is_stub:1})
WHERE s1.fqdn <> s2.fqdn
RETURN c.name, s1.name, s2.name
```

Each MCTS action = one Cypher query. Search tree needs no Python graph objects.

**Gate: MCTS arc itself (gated on flat kernel proving insufficient post-calibration).
When MCTS design starts, Bolt is the right query surface — not a new Python BFS.**

---

## Implementation order

| Idea | When | Gate |
|------|------|------|
| 1 — Slater as Rust corpus | DONE | — |
| 2 — Generation model | RM69 design | RM69 active |
| 3 — Vector+graph colocation | RM69 design | RM69 active |
| 4 — Cypher/Bolt migration | After large C corpora or MCTS | Scale trigger or MCTS arc |
| 5 — Scale path | Monitor | >5s query on 100K-edge corpus |
| 6 — MCTS over Bolt | MCTS arc | Flat kernel insufficient |
