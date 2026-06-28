# Determined -- Engineering Practices

## BE A GOOD ENGINEER

1. **Read before you write.** Before writing any function, query, or module - search for what already exists that does the same thing. If it exists, use it.
2. **Use the authoritative implementation.** If a function exists that does X correctly, call it. Don't write a new version of X that bypasses it.
3. **Don't duplicate logic.** Two places that do the same thing will diverge. One will be wrong. Find it before it hurts you.
4. **Test what you ship.** If you can't verify it works, you don't know it works.
5. **Handle failures at the boundary.** Anything that can fail - network, file, model, DB - gets a try/except at the call site.
6. **One thing owns each concern.** If two places both decide the same question, one of them is wrong.
7. **Don't leave broken windows.** Placeholder code, dead paths, and TODOs without owners become permanent. Gate them or delete them.
8. **Understand before you change.** If you don't know why code is the way it is, find out before touching it.
9. **Confidence is not a substitute for verification.** Feeling capable of doing something is not the same as knowing the right way to do it in this codebase. Stop and check first.

## PRE-CODE CHECKLIST (Determined-specific)
Before writing any code that queries, transforms, or computes data in Determined:
1. Grep for it in `determined/agent/graph_utils.py` and `determined/agent/agent_tools.py`
2. If it exists, use it
3. If it doesn't exist, state what you searched for and didn't find before writing

## DO THIS (specific to this system)

1. **Ground truth in queryable structure.** Every fact the system reports must trace to a DB row or AST node. If it can't be queried, it can't be trusted.
2. **Make assumptions falsifiable before building on them.** Run the minimum against real data and get a pass/fail. Don't build a second layer on an untested first layer.
3. **Lock constraints before adding flexibility.** Determinism first. Expressiveness second. Every time flexibility came first, something regressed.
4. **Design closed-world constraints into features.** Enumerate what's legal. Reject what isn't. Scope creep enters through undefined edges.
5. **One authority per layer, enforced structurally.** Ingestion creates. Routing decides. Classification labels. Persistence stores. Never backwards, never shared.
6. **Design for partial failure.** If one component can't answer, the rest should still fire. A gap in one dimension shouldn't crash the whole response.
7. **Publish schema in one place.** The compiler reads it, the executor validates against it, the UI renders from it. One source, multiple consumers.
8. **Invalidate derived state when source changes.** Hash the source, check the hash. Time-based expiry assumes the source didn't change.

## DON'T DO THIS (anti-patterns earned the hard way)

1. **Don't let guesses become infrastructure.** An assumption that works once and never gets validated will eventually be load-bearing and wrong.
2. **Don't trust pattern matching for identity.** Substring and keyword matching feels cheap and clever. It produces false positives at scale and is hard to audit.
3. **Don't mix identity domains in one path.** Builtins, project symbols, and external calls are different things. Route them before classifying them.
4. **Don't design fallbacks without wrapping the primary.** A fallback that only catches ImportError while the actual call sits outside try/except is not a fallback.
5. **Don't ask a component to do what it reliably fails at.** If a model or layer can't reliably do X, redesign around what it actually does rather than forcing it.
6. **Don't make persistence boundaries ambiguous.** Know exactly what lives in which DB, why, and what happens to it when the corpus is rebuilt.
7. **Don't close a gap without a test that proves it stays closed.** A fix without a regression test is a patch. It will reopen.
8. **Don't omit the why from design decisions.** Future sessions will face the same temptations. The reasoning is what stops them from making the same mistake.
