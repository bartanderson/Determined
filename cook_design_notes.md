# Cook's Complex Systems Failure — Design Constraints for Determined

*Source: Richard Cook, "How Complex Systems Fail" (1998). Applied 2026-08-23.*

Determined is itself a defense layer for complex codebases. Cook's framework applies here
in a recursive way: Determined is a complex system that can fail in exactly the ways it
was built to detect in others.

---

## 1. Stale corpus = confident-wrong answers — the most dangerous failure mode

`ingestion/reingest_file.py` correctly implements git-diff-based selective reingest.
This is the right defense. But there is no visible freshness signal exposed to query callers.

A query against a 3-day-old corpus emits the same confidence as a query against a
5-minute-old corpus. Cook: "Complex systems run in degraded mode." A stale corpus is
Determined running in degraded mode — functional, but quietly wrong. The user has no
way to know.

**Constraint:** Every query result must carry a corpus age timestamp. Queries against
corpora older than a configurable threshold should flag the result as potentially stale.
`assessor/epistemic_policy.py` is the right place to enforce this gate.

---

## 2. `agent_tools.py` at 12,705 lines is a single massive risk concentration

Cook: "Safety is a characteristic of systems and not of their components." One component
that accounts for the majority of the system's behavior is a hazard, because changes to
it have the broadest blast radius and its failure modes are the hardest to see.

`agent_tools.py` (12,705 lines) is 5x larger than the next-largest module
(`ingestion/language_walker.py` at 2,488 lines). The engine snapshot/diff and
responsibility_map exist to track change impact, but they track changes *after the fact*.
They don't reduce the blast radius of a change to this file.

**Constraint:** Any change to `agent_tools.py` should trigger a full regression suite
before merge, not just the affected-file tests. The `engine/responsibility_map.py` should
explicitly mark this file as a high-blast-radius module so tooling surfaces the warning.

---

## 3. The observability layer is tiny relative to the system it monitors

`observability/fault_injector.py` — 26 lines.
`observability/signals.py` — 20 lines.
`observability/instruments.py` — 89 lines.
Total observability: ~135 lines.

`agent_tools.py` alone: 12,705 lines.

Cook: "People continuously create safety." The observability layer IS the mechanism by
which safety is created at runtime. At 135 lines covering a 369-file system, it can only
monitor a small fraction of potential failure modes.

**Constraint:** Either grow the observability layer to cover the major failure paths
(ingest failure, corpus corruption, query returning empty on a non-empty corpus, staleness),
or document explicitly which failure modes are NOT monitored and why. An unmonitored
system is not a safe system — it's a system that fails invisibly.

---

## 4. Diffs show individual changes; Cook's accidents require compound failures

`engine/engine_snapshot_diff.py` and `engine/structural_parity_diff.py` track what
changed between snapshots. This is correct for detecting individual regressions.

But Cook's central claim is: "Catastrophe requires multiple failures — single point
failures are not enough." A diff that reports "function A changed" and "function B changed"
separately may not surface that A and B together break an invariant that neither breaks alone.

**Constraint:** The diff engine should include cross-file invariant checks: if file A changed
and file B imports from A, flag B as potentially affected even if B itself didn't change.
`engine/pipeline_dependency_tracer.py` is the right tool for this — verify it is wired
into the diff pipeline, not just available as a standalone query.

---

## 5. Reingest must propagate transitively, not just directly

Related to point 4. `ingestion/reingest_file.py` re-analyzes changed files. But if
file A changes and file B imports from A, does B get re-analyzed?

If not, the corpus can contain a state where B's analysis reflects the old A. Queries
that cross the A-B boundary will produce wrong answers with no visible signal.

Cook: "Complex systems contain changing mixtures of failures latent within them." A
transitive staleness after a partial reingest is exactly this — a latent failure present
in the corpus that won't surface until the right query hits it.

**Constraint:** Reingest must walk the dependency graph from each changed file and
invalidate (and re-analyze) all downstream dependents. Verify this is the behavior of
`reingest_file.py` — if not, it's the highest-priority correctness gap.

---

## 6. `epistemic_policy.py` should be the query output gatekeeper

`assessor/epistemic_policy.py` (183L) is the most Cook-aligned module in the system:
it explicitly models what Determined knows vs. doesn't know about a codebase. Cook:
"Providing calibrated views of the hazards" requires this policy to run on every
query response, not just on queries that explicitly ask for an epistemic assessment.

**Constraint:** Every response that exits through `assessor/assessor.py` or `oracle/db_oracle.py`
should pass through `epistemic_policy.py` for a confidence check. A response that the
policy judges low-confidence should say so in the output, not suppress it.

---

## Summary: what to verify or build in order

1. **Add corpus age to every query result** — stale-corpus failure is silent and confident.
2. **Wire `pipeline_dependency_tracer.py` into the diff pipeline** — compound failures
   require cross-file awareness.
3. **Verify transitive reingest in `reingest_file.py`** — partial staleness is the most
   likely latent failure.
4. **Make `epistemic_policy.py` a mandatory query gate** — calibrated uncertainty at output.
5. **Mark `agent_tools.py` as high-blast-radius in `responsibility_map.py`** — concentration
   risk needs an explicit structural warning.
6. **Grow or explicitly scope the observability layer** — 135 lines covering 369 files
   is not a monitoring posture, it's a placeholder.
