# Commonplace - Design Document

_Authoritative design intent for the Commonplace sample application.
Ingest with `ingest_design_docs` to make constraints available to
`check_design_violations`._

---

## Application overview

Commonplace is a personal knowledge store. A user captures URLs or notes,
the application extracts metadata and content, applies tags, and infers
connections between entries. A search surface lets the user retrieve
entries by text or semantic similarity.

The application is intentionally simple. Its purpose as a Determined
demonstration corpus requires that each layer have a clear role and that
violations of those roles be detectable.

---

## Architecture

Four layers. Each layer has a single responsibility. Only adjacent layers
may communicate, and only in the downward direction.

```
routes/      HTTP boundary -- parse request, call service, render response
services/    Business logic -- coordinate storage, apply rules, call external services
storage/     Persistence -- only layer that touches the database
utils/       Pure functions -- no state, no I/O, no imports from other layers
```

### routes/

HTTP boundary only. A route handler must:
- Parse the incoming request (form fields, query params, path segments)
- Validate input format (HTTP-level concerns: required fields, type coercion)
- Call one or more service functions
- Render a response template or redirect

Routes must not contain business logic. They must not call storage directly.
They must not import from `storage/`.

### services/

All business logic lives here. A service module:
- Coordinates calls to `storage/` and to external services (LLM, HTTP fetches)
- Applies domain rules (tag normalization, connection symmetry, content limits)
- Returns data to the calling route

Services must not contain HTTP logic (no Flask imports, no request objects).
Services may import from `storage/` and `utils/`. Services must not import
from `routes/`.

### storage/

Only layer that touches the database directly. Storage functions:
- Execute SQL against the database connection
- Return raw rows or simple scalars
- Contain no business logic and no external service calls

The database connection is obtained via `storage.db.get_db()`. No other
layer may call `get_db()` or execute SQL. Storage must not import from
`services/` or `routes/`.

### utils/

Pure functions with no side effects. Utils:
- Accept plain values, return plain values
- Import no application modules (no services, storage, routes)
- May import stdlib only

---

## Authority rules

These are the invariants Determined's violation detection should flag.

**Only `storage/` touches the database directly.**
No function outside `storage/` may call `get_db()`, execute SQL, or import
`storage.db`. Violations: any `get_db()` call in `routes/`, `services/`,
or `utils/`.

**Routes delegate to services, never to storage directly.**
A route handler must not import from `storage/` or call any storage function.
All persistence must flow through a service. Violations: any `from storage`
import in `routes/`.

**Tags are always lowercase.**
Tag names stored in the database must be lowercase. Normalization happens
in the service layer before storage. Violations: any `insert_tag()` call
where the name is not `.lower()`-normalized first.

**Connections are bidirectional -- both directions must be stored.**
A connection from entry A to entry B implies a connection from B to A.
Both rows must be inserted. Violations: any `insert_connection()` call
without a corresponding symmetric call in the same transaction.

**Content is required for every entry.**
An entry with empty or None content must not be inserted. Enforcement
belongs in the route (400 response) and defensively in the service.
Violations: any `insert_entry()` call where `content` is falsy.

**URL validation must occur before network fetch.**
The capture route must call `validate_url()` before calling `extractor.extract()`.
Violations: any call to `extractor.extract()` where `validate_url()` was not
called first in the same handler.

---

## Open design questions

These tensions are annotated in code comments and promoted here as explicit
unresolved decisions. Determined's `check_design_violations` and stub reasoning
tools should surface these when analyzing the relevant modules.

### extractor.py: one module or three?

`extractor.py` currently does three things: HTTP fetch, HTML parsing, and
readable-text extraction. These are separable responsibilities. The design
question is whether to split into `fetcher.py + parser.py + extractor.py`
or leave them unified under one module that evolves.

Arguments for splitting: each responsibility has a different failure mode,
testability improves, and `extract_full_content()` (the stub) is a natural
seam for the split.

Arguments for staying unified: the module is small, the three steps are
always called together, and splitting adds indirection without adding clarity.

Resolution deferred. The seam is at `extract_full_content()`.

### tagger.py: eager on capture vs lazy on view

`suggest_tags()` is called from the capture route when `TAGGING_ENABLED` is
set. This means tag suggestions happen synchronously during the HTTP request,
which slows capture. The alternative is to defer tag inference until the entry
is first viewed.

Arguments for eager: tags are immediately available, no stale-entry problem.
Arguments for lazy: capture is fast, LLM latency is hidden, tags are often
not needed immediately.

Resolution deferred. Current implementation is eager (called in capture route).

### searcher.py: bypasses service layer

`searcher.search()` calls `queries.search_entries()` directly (a storage
function). This means the search service touches storage without going through
a service boundary -- it IS the service but acts like storage.

The design question is whether `search_entries()` belongs in `storage/queries.py`
at all, or whether search logic should live entirely in the service layer with
storage providing only raw row access.

Resolution deferred. Current code is a known violation of the service-boundary
rule.

### capture route: URL validation in two places

`routes/capture.py` calls `validate_url()` directly AND `extractor.extract()`
also performs its own URL-level validation implicitly (via `urlopen` failures).
Two enforcement points for the same constraint.

The design question is whether route-level validation should be the only
enforcement point (trusting services to receive valid input) or whether services
should also validate defensively.

Resolution deferred. Current code has duplicate enforcement.

---

## Stub roadmap

These stubs are deliberate. Each one is waiting for a specific external
dependency or design decision. Implementing a stub is a guided journey step.

### `extractor.extract_full_content(url)`

Waiting for: a readable-text extraction library (readability-lxml or trafilatura).
What it enables: meaningful content for semantic search and connection inference.
Signature: `extract_full_content(url: str) -> str`
Returns cleaned body text, empty string on failure.

### `searcher.semantic_search(query)`

Waiting for: embedding infrastructure (sentence-transformers or llama-server
`/v1/embeddings` endpoint).
What it enables: find entries by meaning, not just keyword match.
Signature: `semantic_search(query: str) -> list[dict]`
Returns same row-dict format as `search()`.
Currently falls back to `search()`.

### `linker.find_connections(entry_id, content, all_entries)`

Waiting for: `_similarity_score()` (below) and decision on eager vs lazy
connection inference.
What it enables: automatic link graph between related entries.
Signature: `find_connections(entry_id: int, content: str, all_entries: list) -> list[tuple]`
Returns list of `(other_entry_id, relation_type, confidence)`.

### `linker._similarity_score(text_a, text_b)`

Waiting for: embedding infrastructure (same as semantic_search).
What it enables: `find_connections()` and any other cosine-similarity use.
Signature: `_similarity_score(text_a: str, text_b: str) -> float`
Returns 0.0..1.0.

### `tagger.suggest_tags(content, endpoint=None)`

Waiting for: LLM endpoint decision (eager vs lazy resolved, llama-server
port 8081 wired in config).
What it enables: automatic tag inference from entry content.
Signature: `suggest_tags(content: str, endpoint: str | None = None) -> list[str]`
Returns list of lowercase tag strings, empty on failure.
`_call_llm()` and `_parse_tags()` are already implemented and waiting.
LLM endpoint: `http://localhost:8081` (llama-server, 8B model).

---

## Schema

Four tables. Schema lives in `storage/db.py`.

```
entries     id, type, content, title, source_url, excerpt, created_at
tags        id, name, source (manual | llm)
entry_tags  entry_id, tag_id  (many-to-many, UNIQUE constraint)
connections from_entry_id, to_entry_id, relation, note
```

`entry_tags` has a UNIQUE constraint on (entry_id, tag_id) to prevent
duplicate tag associations. `tags` has a UNIQUE constraint on name.

---

## LLM integration

Two service modules are wired to use an LLM endpoint:
- `tagger.suggest_tags()` -- currently stub; endpoint is llama-server port 8081
- `searcher.semantic_search()` -- currently stub; embeddings from
  sentence-transformers or llama-server `/v1/embeddings`

Both are disabled by default. Enable via `config.py`:
- `TAGGING_ENABLED = True` activates `suggest_tags()` in the capture route
- Semantic search is activated by implementing `semantic_search()` and wiring
  it into the search route

The LLM endpoint is not a hard dependency. All LLM paths must degrade
gracefully: `suggest_tags()` returns `[]`, `semantic_search()` falls back
to text search.
