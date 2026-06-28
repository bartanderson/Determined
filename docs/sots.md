The Shape of the System
Structure over vigilance: Engineering for bounded cognition

New here? Start at the front door. Five ways in, depending on why you came.

Software gets read far more than it gets written. It gets changed more than it gets read, and then it runs in a world that fails partially, at the worst possible moment, usually while you're asleep. So build correctness into the shape of the system, not into the vigilance of the people keeping it going. Any rule you can only enforce by remembering it is a rule that will eventually get forgotten, and any defence you have to run by hand gets skipped the first time there's a deadline. The objective has two terms and you're meant to push on both of them at the same time: minimise what a tired engineer has to hold in their head to make a correct change, while keeping the blast radius bounded for anything an attacker or an unlucky caller controls. Most of the tenets here buy you that first term. The ones that add code and state to contain failure are paying for the second. When two tenets pull against each other, and sooner or later they will, you don't resolve it with a slogan. It's a judgement about who controls the input and how wide the blast radius is. If the input is caller- or attacker-controlled and the blast radius is wide, pay the cost now. If it's self-controlled and contained, you can defer it, but write down why. These tenets work on one part and one boundary at a time, because that's about all a bounded mind can keep hold of at once. The failures that only turn up once the whole thing is assembled, the ones that belong to no single part, get their own page, The Shape of the Whole. Every tenet below names the failure it stops, the tension it sets up, and one question to ask yourself mid-edit. None of them is free.

I
Locality of reasoning over global cleverness
A reader should be able to verify a piece of code correct by looking only at that piece and its declared inputs.

When understanding one function means you also have to know the call order of three others, and a flag set in a constructor, and some global that gets mutated somewhere else, then you haven't really written a function. You've written a puzzle and scattered the pieces across the repo. Action-at-a-distance is the biggest tax there is on changing code, because before the reader can touch anything they have to rebuild all that invisible context in their head first. Locality is the thing that lets people make correct changes while staying ignorant of 99% of the system.

Frontend: a component that derives everything from its props and local state vs one whose behaviour depends on a useEffect three files away mutating shared context.
Backend: a handler that reads request-scoped, explicitly-passed config vs one reaching into a process-global singleton mutated by middleware.
Data/ML: a stage that declares its input schema and emits a new dataset vs one that mutates a shared dataframe in place, so stage 7's correctness depends on stage 2's side effects.
Tension: DRY and single source of truth (XIV) push back here. Inlining everything so each unit stands on its own ends up duplicating logic that then drifts apart. Resolve it by scope: keep control flow and invariants local, but let named, owned shared facts live somewhere else as long as the dependency is explicit (II). Duplicating a three-line guard is cheaper than some spooky-action abstraction, and the wrong abstraction costs you more than the copy does, but duplicating the authoritative definition of a fact is exactly (XIV)'s bug. Copy the things that are only coincidentally similar and will drift apart anyway. Unify only what's genuinely the same fact and has to change together.

Ask yourself: To convince myself this code is correct, how far from this screen do I have to look?

Lineage: local reasoning / the frame rule [O'Hearn, Reynolds & Yang 2001]; information hiding [Parnas 1972]; deep modules / complexity-as-cognitive-load [Ousterhout 2018]; coupling and cohesion [Constantine et al. 1974]; action-at-a-distance [Dominus 1999], spooky-action [Einstein 1947]; the wrong abstraction [Metz 2016], Rule of Three [Fowler 1999]; DRY / single source of truth [Hunt & Thomas 1999]; software read more than written [Abelson & Sussman 1985]

II
Make the data flow explicit, and give every ambient dependency one override point
Show where state comes from and where effects go; an ambient dependency with no declared override is a bug you can't see yet.

Globals, mutable module state, and now() and random() in particular, pulled out of the ether, make behaviour depend on things that aren't in the call. So the same inputs give you different outputs and the tests need a séance to reproduce anything. The rule is not "pass everything as an argument". Threading a clock and an RNG down through forty layers is its own kind of parameter soup. The rule is that every ambient dependency has exactly one declared seam a test can actually reach: an injected default, an overridable context, a virtual clock. A controlled seam is fine. An uncontrolled Date.now() buried four frames down with no override is the bug. This is the precondition for both locality (I) and any honest test at all.

Testing/backend: a function reachable via an injected clock and httpClient is reproducible; a hardcoded Date.now() and a module-level client deep inside is a flake you'll chase for days.
Frontend: prefer props and explicit stores to deeply-nested implicit context; one-way data flow exists so you can answer "why did this re-render?"
Scripting/glue: pass config and paths as arguments, not via a mutated os.environ a reader has to hunt for. Invisible environment state is a debugging trap.
Ask yourself: Could a test pin this behaviour through a single declared override, and if not, which ambient input has no seam?

Lineage: dependency injection [Fowler 2004], dependency inversion [Martin 1996]; seam [Feathers 2004]; test double / virtual clock [Meszaros 2007]; one-way data flow [Facebook 2014]; props vs implicit context [Dodds 2018]; referential transparency [Quine 1960; Strachey 1967]; flaky tests [Micco 2016]; ambient authority [Miller, Yee & Shapiro 2003]

III
Parse, don't validate: make the illegal state unrepresentable
Turn unstructured input into a typed, constrained value once at the door, so the bad shape can't be built or passed on.

Validation answers "is this okay?" and then throws the answer away, so every later function has to ask it again, and some of them forget. The rule holds at thirty-nine of forty call sites. Parsing answers "what is this, exactly?" and hands back a narrower thing (an Email, a NonEmptyList, a PaidOrder) whose validity is carried in the representation itself and can't be un-checked. This tenet is purely about shape: structure refuses the malformed for everyone, forever, including the call sites that don't even exist yet. (Whether a well-formed value is also hostile is (IV)'s job, not the type's: too big, unauthorised, or lying about its identity.)

Backend/types: separate UnvalidatedInput and ValidatedInput so an unvalidated value physically cannot reach the database call; the boundary cross is the function that changes the type.
Frontend: model UI as a discriminated union (loading | error | loaded(data)) so "spinner showing and stale data rendered" is literally untypeable, instead of three booleans encoding five nonsense states.
Databases: a NOT NULL, a CHECK, a foreign key, a partial unique index. The schema refuses the bad row for every writer, including the migration script and the intern at a psql prompt.
Tension: In Python, JS, Bash, or a notebook the compiler won't carry this for you, and even in strong type systems you can build a whole cathedral of phantom types that nobody can read. The principle survives, just demoted to a single chokepoint that everything funnels through. For tabular or array data there are no per-cell types you can make unrepresentable; the structural form is a schema asserted once at ingestion (pandera, pydantic, Great Expectations) that yields a validated frame downstream code is allowed to assume, with the bad rows quarantined off. For whole-dataset and dynamic-language work, validate-once-at-the-edge isn't a fallback. It is the realistic ceiling, and it still beats forty scattered checks, which beat a comment.

Ask yourself: Past this line, is it structurally impossible to be holding the raw, unchecked form, or am I just adding one more check someone can skip?

Lineage: parse, don't validate [King 2019]; make illegal states unrepresentable [Minsky 2010], popularised [Wlaschin 2013], UI sum types [Feldman 2016]; type-driven development [Brady 2017]; correct by construction [Dijkstra 1976]; phantom types [Leijen & Meijer 1999]; declarative constraints [Codd 1970]; pandera/pydantic/Great Expectations [Bantilan 2018], [Colvin 2017], [Gong & Campbell 2017]

IV
Everything across a trust boundary is hostile until proven otherwise
A well-formed value can still be an attack; bound its size before you allocate, and authorise the actor separately from authenticating them.

Tenet III makes the value well-formed. Tenet IV starts from the idea that a well-formed value can still be hostile, and it guards the things a type can't encode. There are three of them. Crashing on malformed input is a free DoS. Allocating in proportion to a size the attacker picks is the 2 GB JSON body that parses fine and then kills your heap. And trusting an identity or authority that the request merely asserts about itself is the classic privilege escalation. Authentication tells you who; it says nothing about what they may do. So verify the signature, and then check that this subject is actually authorised for this specific action. The boundary is the socket, the form field, the queue message, last week's data dump, a sibling service, and the dependency you import and the CI that runs with your secrets. A library runs with your privileges (tenet XVI), a build job runs with your keys, and the code you didn't write but shipped is still code you shipped. Pin it and verify it.

Web/backend: cap body size and array lengths before deserialising; re-derive identity from the verified token, never from a userId in the payload; client-side validation is UX, not security.
Supply chain: lockfiles with checksums, signature verification, a minimised dependency surface (tenet XXI), and least privilege (tenet XVI) on the build. A typosquat or a poisoned transitive dep is a boundary crossing, not a convenience.
Embedded/ML: clamp every reading off the bus or ADC to a physical range before it reaches actuator maths; quarantine the row whose null-rate or dtype violates the schema rather than NaN-poisoning a model you only discover three weeks later.
Tension: Locality and parse-once (tenets I, III) cut the other way here. Re-validating at every internal hop is tenet III's anti-pattern and a latency tax, and zero-trust between your own in-process functions buys you clutter for no real reduction in threat. So bound the trust boundary deliberately: validate and parse once at each real crossing - process edge, deserialisation point, privilege change - and carry the parsed type (tenet III) inward, so internal callers trust the type and not the wire.

Ask yourself: What is the worst single value, or the worst package, the other side could send here, and have I bounded the size, re-verified the authority, and pinned what I trust before acting on it?

Lineage: trust boundary [Swiderski & Snyder 2004]; all input is evil [Howard & LeBlanc 2002]; authn vs authz [Lampson 1971 / Saltzer & Schroeder 1975]; STRIDE (escalation/DoS) [Kohnfelder & Garg 1999]; least privilege & complete mediation [Saltzer & Schroeder 1975]; bound size before allocating [OWASP API4 2023], billion laughs [Billion Laughs 2002], zip bomb [Zip bomb 1996]; supply chain pin & verify [SLSA / Sigstore 2021], typosquatting [Tschacher 2016]; zero trust [Kindervag 2010]; client-side validation is UX [OWASP Input Validation 2021]

V
Keep the responsive path free of uncontrolled-latency work
A path that owes someone a deadline must never wait inline on work whose completion depends on a party you don't control.

A UI thread, an event loop, a request handler, a game frame, a scheduler tick - each one is a heartbeat with a deadline it owes to a user's eye, or a watchdog, or a 16 ms frame budget. The instant it synchronously calls a slow network, or a disk, or a lock held by who-knows, its responsiveness is hostage to a stranger's worst day. The general move is to get that work off the responsive path and make it observable, and the right mechanism depends on the domain: async/await plus a pending state in a UI; a job queue and a 202 in a service; an off-thread load in a game loop that the frame reads if it's ready; a background process or a separate stage in a script, so the one thread a human is watching never goes dark. In a concurrent server the specific form is a bounded queue with a separate worker that returns an explicit "full" as backpressure, but the queue is just one instance of the rule, it isn't the rule.

Frontend: hand a heavy parse to a Web Worker and render a pending state; a synchronous fetch or a data-dependent 200 ms sort on the main thread freezes scroll and input.
Backend: enqueue the third-party call or the transcode, return 202, surface "queue full" as a 503. Don't tie your tail latency to their bad day until the thread pool starves.
Scripting/data: a long step belongs in a background job or a separate stage, not inline on the only thread, where the user sits staring at a dead terminal.
Tension: A queue absorbs bursts, not sustained overload. Under sustained load a deep buffer just delays the rejection and fills up with already-dead work, every item past its deadline by the time you reach it. Pair it with deadline-aware shedding: fast-reject work whose deadline (tenet VI) will expire before you serve it, prefer freshest-first, and add the seam only where a real uncontrolled-latency dependency exists. Watch out for the data-dependent case. In-process work whose cost scales with input you don't bound - a client-side sort over user data, say - is an uncontrolled-latency path even though it's "yours", so measure it at realistic scale before you decide.

Ask yourself: On this responsive path, am I waiting on anything whose worst-case latency I don't control, and if it never returns, does my system look dead?

Lineage: don't block the event loop [Node.js (Don't Block the Event Loop)]; 16 ms frame budget [Irish & Lewis 2015], 100 ms threshold [Miller 1968]; Web Worker [WHATWG / Hickson 2009]; async/await [Syme 2007; C# 5.0 2012]; 202/503 [RFC 9110 2022]; backpressure [Reactive Streams 2015], bounded buffer [Dijkstra 1965 (EWD123)]; tail latency [Dean & Barroso 2013]; load shedding & deadline-aware shedding [Ulrich 2016], [Maurer 2015]; deep buffer just delays rejection [Little 1961]; watchdog/heartbeat [Murphy & Barr 2001]; game-loop decoupling [Fiedler 2004; Witters 2009]

VI
Every wait across an uncontrolled boundary has a deadline
A cross-boundary call with no timeout is a bet that the other side is always fast and always answers; you will lose it.

Scope this to waits that cross a boundary you don't control: a network, an IPC, a lock you don't own. A hung dependency without a deadline doesn't fail, it spreads. It eats the caller's threads, then the caller's caller's threads, until one slow database melts the whole fleet. A deadline turns an unbounded hang into a bounded, observable error. But a deadline only protects you from a hung dependency, not from a slow-but-progressing one. A six-hour training run, a 50 GB sort, a multi-hour query - that's correct long work, and an arbitrary timeout would just kill it. The right tool there is progress, heartbeat, and cancellation, not a wall-clock cutoff. There are two hard parts the headline hides. A timeout that doesn't cancel and propagate just orphans the slow work (tenet VII) and may fire a duplicate, so a deadline is only safe when the operation is cancellable or idempotent (tenet X) on retry. And the retry policy that follows from all this lives in tenet XIX, not here.

Distributed systems: propagate a deadline through the call chain, so a 5 s edge budget isn't spent waiting on a service that itself waits 30 s.
Databases: set statement_timeout and connection-acquisition timeouts; one runaway query must not hold a pool slot forever.
Data/ML (the exception): a legitimately long batch job gets cancellation and a progress signal, not a deadline that murders correct work at hour five.
Ask yourself: Does this wait cross a boundary I don't control, and if so, what's the cutoff, is the work cancellable or idempotent if it fires, and where is the number written down?

Lineage: Timeouts / Fail Fast stability patterns [Nygard 2007]; cascading failure & deadline propagation/budget [Ulrich 2016]; deadline vs timeout [Sheehy 2015]; statement_timeout [PostgreSQL 2002], connection-acquisition timeout [Wooldridge 2013]; cooperative cancellation [Microsoft 2010]; idempotent retry-safety [RFC 7231 2014], idempotent term [Peirce 1870]

VII
Bound what callers can create; release what you acquire
Every resource has a ceiling, and everything you acquire has exactly one owner that releases it on every exit path, including error and panic.

Anything a caller can ask for in a loop (connections, threads, queue depth, retries, cache keys, recursion, payload size) is a DoS or an OOM waiting to happen, whether it's an attacker who triggers it or just your own retry storm. And anything you go and acquire (a goroutine, a timer, a subprocess, a subscription, a file handle, a lock) is an orphan-in-waiting unless something releases it. In garbage-collected and scripting languages the runtime reclaims memory and nothing else: a subscription, timer, subprocess, file handle, or lock is still yours to release by hand. Use the language's scoping construct where there is one (with, defer, try/finally, RAII) and release manually only where there isn't. "Unbounded" is just a synonym for "fails later, mysteriously, in production".

Backend: a fixed pool with a wait-or-reject policy degrades into 503s; unbounded connection or thread creation per request turns a spike into a death spiral.
Data/ML: cap batch size and parallelism, or one skewed key OOMs the cluster; cap retries with backoff or a flaky upstream becomes a self-inflicted DDoS.
Mobile/frontend: an unbounded image cache is an OOM kill; a timer or listener registered on mount and not torn down on unmount leaks the screen the user already left.
Tension: This invites the YAGNI objection. Not every list needs a configurable max today, and premature limits become wrong limits that page you at 3am. The way out is to ask who controls the growth. If it's caller-driven, external-input-driven, or unbounded-by-time, it always gets a ceiling. The twelve months of the year do not. A missing limit isn't a missing feature, it's an unbounded liability. The owner rule, unlike the ceiling, can't be negotiated away.

Ask yourself: What's the maximum this can grow to, who controls that (me or my caller), and on every exit path, what releases what I acquired?

Lineage: RAII [Stroustrup 1994], single-owner Drop [Klabnik & Nichols 2018], language scoping [Klabnik & Nichols 2018]; bound the unbounded / Unbounded Result Sets & Bulkhead [Nygard 2007]; bounded pool wait-or-reject [Wooldridge 2013], 503 [RFC 9110 2022]; cap retries with backoff+jitter [Brooker 2015]; GC reclaims memory not external resources [Bloch 2001]; YAGNI applies to features not limits [Beck 1999]

VIII
Tear down what you set up; subscribe for latency, reconcile for correctness
Every subscription, listener, or handle you register has a teardown that runs when either side goes away, and prefer the event over the timer, except where the event is silence.

A cache, a registry, an observer, a parent supervising its children will routinely outlive the thing it references. In a garbage-collected language the rule is about lifecycle and not memory: clean up the listener on unmount, or it goes on firing callbacks into a thing that no longer exists. The manual-memory version (Rust, C++, Swift/ARC) is where you actually choose the reference strength, and there the trade gets sharp. A strong claim from the long-lived side wedges teardown and leaks. A weak claim risks the watched thing being collected or evicted out from under a user who's still active (the listener that quietly stops, the cache entry that vanishes mid-use). Hold weak where the watcher survives the watched disappearing, and hold strong-with-explicit-teardown where it doesn't. And learn that something is finished from the event (a close, a done, an unmount, a DMA-complete interrupt) rather than from a clock.

Frontend: a listener set up on mount and removed on unmount; the missing cleanup keeps a dead component alive and updating.
Mobile / manual-memory: a callback strongly retaining a screen pins it after the user left; the long-lived side holds weakly, the short-lived side owns. In embedded, detect "DMA done" from its completion interrupt, not a status-bit poll.
Distributed/backend: subscribe to the close event for latency, but keep an idempotent (X) reconciliation sweep for correctness. Across a boundary you can miss the edge.
Tension: Events are sharp but lossy. A pure event-driven design is right only when the event is guaranteed to be delivered somewhere you can't miss it. When completion is absence (a crash, a hang, a disconnect emits no event at all), a timer or heartbeat is the only signal you'll get, and a missed edge across a boundary (IV) wedges you forever. So subscribe for latency, but keep a level-triggered, convergent reconciler (X) for correctness. Poll where the truth is silence and subscribe everywhere else.

Ask yourself: Does every thing I registered have a teardown, and am I learning "it's done" from an event, with a reconciler behind it for the edge I might miss?

Lineage: edge vs level-triggered control loops [Hockin 2017], hardware origin [Intel 8259 1976]; self-stabilisation / convergent reconciler [Dijkstra 1974]; effect cleanup on unmount [React 2019], observer Attach/Detach [GoF 1994]; lifecycle not memory / RAII [Stroustrup 1994], strong/weak refs & retain cycles [Apple 2011]; completion-is-absence / failure detection [Chandra & Toueg 1996]; idempotent sweep [Peirce 1870]

IX
Check-then-act on shared state is a race unless it's atomic or serialised
If two actors can interleave between your check and your act, the check is a guess.

if not exists: create, if balance ≥ amount: debit, "reserve the last seat": every one of these is two operations pretending to be one. This only bites where two actors can actually interleave, so concurrent requests, multiple workers, overlapping cron runs, parallel partitions. In code that's genuinely single-threaded and single-run there's no window, and the heavy machinery is just waste. But "it's single-threaded" is the assumption that turns out wrong most often at scale, and the window is invisible in review and devastating in production. The correct fixes come in three families, and the reader should be able to see which one you picked: atomicity (one indivisible step, including optimistic compare-and-swap on a version, then retry), serialisation (one owner, or a consistent lock order), or commutativity (make the act idempotent so the race does no harm).

Databases: INSERT ... ON CONFLICT or a unique constraint, not SELECT then INSERT; UPDATE ... WHERE balance >= amount checking rows-affected, not read-modify-write.
Distributed systems: a compare-and-swap or a fenced lease, not "read the flag, then take the lease", and expect to be wrong about holding it.
Frontend/scripting: disable on submit or dedupe by request id, or two rapid clicks double-charge; two overlapping cron runs claim work by atomic rename, not by checking a "processing" flag.
Ask yourself: Can two actors actually run this between my read and my act, and if so, have I made that window atomic, serialised, or harmless?

Lineage: check-then-act / read-modify-write compound actions [Goetz 2006]; TOCTOU [McPhee 1974; Bishop & Dilger 1996]; atomicity [Härder & Reuter 1983], linearisability [Herlihy & Wing 1990]; compare-and-swap [IBM System/370 1970], optimistic concurrency [Kung & Robinson 1981]; serialisability [Eswaran et al. 1976], lock ordering [Coffman et al. 1971]; commutativity [Shapiro et al. 2011], idempotent [Peirce 1870]; fenced lease [Kleppmann 2016], lease [Gray & Cheriton 1989]; INSERT ... ON CONFLICT [PostgreSQL 9.5 2016]

X
Make operations idempotent so "do it again" is always safe
In a world of retries, redelivery, and at-least-once everything, the only safe operation is one that's harmless to repeat.

Where (IX) is about concurrent interleaving of one logical attempt, X is about sequential re-delivery of the same attempt: the lost ack, the redelivered message, the double-click, the job re-run after a crash. They share a fix, a stable key, but the failures they prevent are different. If "apply once" and "apply twice" don't give the same result, then every retry becomes a corruption, which is why idempotency is the thing that makes (XIX)'s retries, crash recovery, and at-least-once messaging safe instead of dangerous. Key your writes by a stable id, make creates upserts, and make the pipeline re-runnable from any point.

Backend: an idempotency key on payment and order creation returns the original result on retry instead of charging twice.
Data/infra: a Terraform run or a batch job you can re-execute to the same end state recovers from a half-finished run by just running it again, with no forensic cleanup.
Distributed/messaging: consumers dedupe by message id, so at-least-once delivery behaves like exactly-once where it counts.
Tension: Idempotency keys, dedupe tables, and reconciliation are real machinery with storage and expiry. Don't build it for a read that's genuinely safe to repeat. Spend it where a repeat mutates money, state, or the outside world.

Ask yourself: If this runs twice because something retried, is the result identical to running it once?

Lineage: idempotent term [Peirce 1870], idempotent methods / retry-safety [RFC 7231 2014]; idempotency key [Leach 2017]; at-least-once delivery [Birrell & Nelson 1984], exactly-once is faked [Treat 2015], dedupe-by-id [Confluent 2017]; Two Generals (the lost ack) [Gray 1978]; upsert [SQL:2003 MERGE]; convergence to end state [Burgess 1995]; 'two hard problems' aphorism [Verraes 2015]

XI
Separate the irreversible decision from its effect
Make "should we / which ones" a pure, exhaustively-testable function that returns a plan; make the doing a thin wrapper that only executes the plan.

The catastrophic verbs - delete, kill, charge, send, overwrite, launch - are dangerous mostly because the reasoning is fused right into them. A delete() that works out what to delete while it's deleting can't be tested without something actually getting deleted, so the code that most needs proof is the code you end up testing least. Split them. A pure whichRowsToPurge(state) -> ids can be hammered with ten thousand cases and no side effects at all, and the wrapper that takes those ids and runs DELETE is small enough to read in one breath. This seam is also the thing that makes dry-run, four-eyes approval and undo possible. They all hook in here.

Backend/billing: decideCharge(cart) -> ChargeIntent is property-tested to death; the gateway call merely realises a fully-formed, idempotent (X) intent and never touches a live gateway in a test.
Data engineering: the job computes the diff as a reviewable manifest, logs it, dry-runs it; a separate trivial step applies the approved plan. Never fuse the query and the rm.
Infra/scripting: terraform plan then apply; the find -delete one-liner that fuses choosing and deleting is how you erase the wrong directory at 2am.
Tension: The plan goes stale, a TOCTOU window (IX). The split brings back the very race (IX) warns about, because the plan was computed against a snapshot that the effect may no longer match by the time you apply it. Close it: pin the plan to a state version and re-check at apply (compare-and-swap on the version), or make the effect conditional on the precondition still holding. A stale plan applied blindly is the race you split the code to avoid in the first place. And where the verb is cheap and undoable, skip the seam altogether. The intermediate plan is just ceremony for trivial, reversible actions.

Ask yourself: Can I test this irreversible decision without doing it, is the doing-part obviously correct, and is the plan still valid at the moment it executes?

Lineage: functional core, imperative shell [Bernhardt 2012]; command-query separation [Meyer 1988]; plan/apply [HashiCorp 2014]; dry-run; four-eyes [Four-eyes principle]; property-based testing [Claessen & Hughes 2000]; humble object [Feathers 2002], sans-IO [Benfield 2016]; TOCTOU window [McPhee 1974; Bishop & Dilger 1996], CAS-on-version [IBM System/370 1970]; Decider [Chassaing 2021]

XII
Finish your obligations before you exit
Stop accepting new work, drain or hand off in-flight work within a bounded deadline, flush and ack only what is durably done, then exit.

Shutdown isn't the absence of work. It's the last work you owe, and the one most likely to get skipped. A process that exits with buffered writes unflushed, or messages consumed but not acked, or requests dropped halfway through a handshake, doesn't fail loudly. It quietly loses whatever someone downstream was counting on, and you find out later from a data discrepancy that nobody can explain. The OS reclaims memory, never meaning. The floor here applies to everything, even a one-shot script: leave either a complete output or none at all. Write to a temp path and atomically rename on success, so a half-written CSV never gets mistaken for a finished one, and trap signals to clean up. And since you might get killed abruptly anyway, the durability contract has to live somewhere else too - a WAL, at-least-once redelivery, idempotent writes (X) - so that an abrupt exit is survivable by design rather than by luck.

Backend: on SIGTERM, stop the listener, drain in-flight requests within a grace window, close the pool, then exit. A rolling deploy drops zero requests instead of 500-ing every connection mid-flight.
Scripting/data: the killed script leaves a complete file or nothing: temp-write-then-rename, and a signal trap that removes partials; commit the stream offset only after the record is durably written, because ack-before-persist silently eats data on restart.
Mobile/embedded: flush unsaved state and queued analytics on background or low battery; the OS may kill you without a second warning, and the user's last edit is your obligation.
Tension: Unbounded graceful drain is its own kind of hang. A shutdown that waits forever for a stuck request is no better than one that just drops it. Bound the drain with a deadline (VI), then force-exit.

Ask yourself: If this were told to stop right now, what has it accepted that would silently vanish, and does my shutdown path complete those obligations within a deadline?

Lineage: graceful drain [Envoy 2017], SIGTERM grace window [Dinesh 2018], signal trap [POSIX signal(7) 1988]; atomic temp-then-rename [POSIX rename() 2024], maildir idiom [Bernstein 1995]; write-ahead log [Gray 1978]; durability (ACID) [Härder & Reuter 1983]; at-least-once taxonomy [Spector 1982]; idempotent writes [Peirce 1870]; crash-only [Candea & Fox 2003]; commit offset after durable write [Confluent 2017]

XIII
Failure modes must be visible and impossible to swallow
Make every way this can fail legible to the next reader without running it, and handle failure where the context to decide lives; the sin is the silent swallow, not the keyword.

When a failure is an invisible exception tunnelling up through ten frames, the reader sitting in any one of those frames can't see what might blow up beneath them, so handling turns into guesswork and the happy path becomes a lie. The invariant is that failure stays visible and can't be ignored. The mechanism, though, is whatever your language makes idiomatic. A Result or (value, err) where you have them, so the tooling nags you to handle the case. Typed exceptions caught at a deliberate boundary, where exceptions are the idiom (Python's EAFP, Ruby), count as a first-class way of doing this and not a fallback, as long as there's no bare except: or empty catch. Error codes with no allocation in embedded. A swallowed error is a wrong state that has learned to hide.

Backend / Go-style: (value, err) forces the caller to confront failure at the call site, where the context to handle it lives.
Frontend: a fetch returning { ok } | { error }, or a typed exception caught at one boundary, lets the component render the error state by design instead of an unhandled rejection vanishing into the console.
Scripting/glue (fail fast): set -euo pipefail so a failed step halts the chain; the default (a failed command ignored while the script charges on, corrupting the next step) is the trap.
Tension: Fail-fast and degrade (XIX) want opposite things. Threading errors everywhere can drown the happy path, so let them propagate with minimal ceremony (?, monadic bind, one catch boundary) to where the context to decide lives. And the two error stances really do conflict. A glue script or a data pipeline should halt loudly on the first bad step, because carrying on corrupts everything downstream. A long-running service should degrade (XIX) instead, because halting is an outage. Choose by blast radius: abort where a wrong result silently propagates, degrade where staying up with less is the lesser harm.

Ask yourself: Can the next reader see this call can fail just by reading it, and is there any path where the failure silently disappears?

Lineage: Python's EAFP [Python Glossary (EAFP/LBYL)]; errors-as-values [Pike 2015], (value, err) at the call site [Gerrand 2011]; Result/Either, monadic bind [Moggi 1991; Wadler 1992], ? operator [Rust RFC 243 2014]; swallowed-error anti-pattern [Howard & LeBlanc 2002]; fail fast [Shore 2004]

XIV
One source of truth; derive the rest
Every fact has exactly one authoritative owner; everything else is a computed or subscribed view.

The same fact stored in two places is two facts, and sooner or later one update misses the other and they disagree. Not if, when. The cache that drifts from the rows it's meant to count, two denormalised columns, two services each holding a writable copy of "the user's plan" - every one of those is a future bug where the system holds two beliefs at once and you can't tell which one is real. Pick the owner, derive everything downstream from it, and make the derivation cheap enough that you're never tempted to cache a second copy.

Databases: the normalised table is truth; a materialised view is a derivation the database keeps honest, not a hand-maintained duplicate two writers update independently.
Frontend: server state is the source; the client cache (React Query, a store) is a derived view with explicit invalidation, not a parallel kingdom of truth you sync by hand and pray.
Distributed/config: one service owns each entity; others hold read replicas or projections clearly marked as derived, never a second master.
Tension: Declared divergence is fine; undeclared is the bug. Caches and read replicas are deliberate, valuable duplications, and so is UI that diverges on purpose. An optimistic update or an in-progress form draft is meant to be temporarily "wrong" relative to the server. So the rule isn't "never copy". It's that every copy has a named owner, an invalidation path back to the source, and a staleness budget, and for deliberate divergence you also add a defined reconciliation point where the server confirms or you roll back. A copy only earns the name engineering once it's declared, invalidated and reconciled. Short of that it's just a bug.

Ask yourself: If these two copies disagreed at 3am, which one is right, why does the other exist, and where does it reconcile?

Lineage: single source of truth / DRY [Hunt & Thomas 1999]; client cache as derived view of server state [Linsley 2020], optimistic update confirm-or-rollback [TanStack & Apollo 2016]; materialised view & schema synthesis [Kleppmann 2017]; ubiquitous-language ownership [Evans 2003]; cache invalidation is hard [Karlton 1996]

XV
Name the boundary, version the contract: strict in, tolerant of the unknown
Every place control, data, or trust changes hands is an interface; declare it on purpose, and evolve it without breaking consumers you can't force to upgrade.

A boundary you didn't design is one your bugs designed for you. When a module reaches into another's internals, when a service trusts an undocumented header, when the ORM table shape leaks into the public JSON, you've got an implicit contract nobody can see, test, or change safely. And contracts live in time. Clients persist, events sit in queues for days, and mobile apps you can't force-upgrade keep sending last year's payload at you. So evolve additively, give every deprecation a window, and settle the strict-vs-tolerant question precisely: reject what violates an invariant you depend on; ignore what you simply don't understand (the unknown-additive field from a newer or older peer). The boundary parser is now your most security-critical, most-tested code, because a bug there is a bug everywhere downstream that trusted it.

Backend/API: the public response is a contract pinned by a test that fails the instant a refactor drops a field; add fields, never repurpose them, version the breaking change behind a deprecation window.
Distributed/data: a wire or event schema evolves with tolerant readers and forward/backward compatibility (Avro, Protobuf rules), because a consumer on old code is not a bug, it's Tuesday.
Mobile: the server serves clients three versions back; "everyone updates" is a wish, not a deployment strategy.
Ask yourself: If I shipped this and an old consumer hit it unchanged, would it break, and does this contract reject what it must while ignoring what it merely doesn't recognise?

Lineage: Postel's robustness principle [Postel 1980 (RFC 761)], reconsidered [Allman 2011]; tolerant reader [Fowler 2011]; Hyrum's Law [Wright 2012]; consumer-driven contracts [Robinson 2006]; SemVer [Preston-Werner 2013]; schema evolution / forward-backward compat [Kleppmann 2012]; deprecation/sunset window [Wilde 2019]; interface as designed boundary [Parnas 1972]; boundary parser as most-tested code [Sassaman et al. 2011]

XVI
Least privilege, by construction
Give every component the narrowest authority that lets it do its job, so a bug or breach is contained by what it was never granted.

Authority you hand out is authority that can be misused. Maybe by an attacker who compromises the component, maybe by a bug that does the wrong thing with full power, maybe by some future caller who never knew the power was sitting there. This is the runtime sibling of "make over-reach unrepresentable" (tenet III): containment is cheaper than trust. It also reads as honest intent. A function that takes only the two fields it touches, rather than the god-object, tells the reader exactly what it can affect.

Backend: the reporting job connects with a read-only role, so a SQL injection in it cannot drop a table it has no grant to drop; scope tokens short and narrow.
Cloud/infra/supply chain: a function scoped to one bucket can't exfiltrate the others when a dependency is compromised; the CI job (tenet IV) gets only the secrets it needs. Broad * IAM is the difference between an incident and a catastrophe.
Frontend: an iframe with a tight sandbox and a Content-Security-Policy whitelisting origins gives third-party code exactly the powers you grant and not one more.
Ask yourself: If this component were fully compromised or simply buggy, what's the most it could touch, and does it actually need all of that?

Lineage: least privilege & fail-safe defaults [Saltzer & Schroeder 1975]; least authority (POLA) [Miller 2006], capability [Dennis & Van Horn 1966]; OAuth scopes [Saltzer & Schroeder 1975], IAM least privilege [AWS 2023]; iframe sandbox [WHATWG / Hickson 2009], Content-Security-Policy [WAF / CSP Stamm et al. 2010]; god-object counterexample [Riel 1996]; SQL injection bounded by read-only grant [Forristal 1998]

XVII
Measure, then make the common case fast, but bound the unbounded without a profiler
Performance is a falsifiable property of the running system, not a vibe; profile before you trade clarity for speed, except for complexity in caller- or attacker-controlled size, which is a correctness bug you fix on sight.

The O(n²) that's instant on dev data melts at production scale, and the per-row round-trip (the N+1 query, the chatty RPC) is the most common latency-and-cost disaster in software and stays invisible right up until the data grows. Your intuition about where the time goes is usually wrong on cold or unfamiliar paths, so measure those first. But there are two carve-outs that override "measure first". One is that complexity which is super-linear in caller- or attacker-controlled input is the DoS of tenets IV and VII rather than a tuning question, so you bound or fix it without a profiler... "dev data was fine" is exactly how it ships. The other is that some antipatterns are reliable enough to fix on recognition, no profile required: the N+1 round-trip, the per-row loop over a vectorisable op, the per-frame allocation. "Measure first" only governs which legible code you're allowed to make illegible. It never licenses an unbounded blowup.

Databases/backend: batch the N+1 SELECT into one query with a join or IN; the innocent-looking loop is 500 round-trips per request.
Data/ML: vectorise or push the filter into the engine instead of a per-row Python loop: hours vs seconds, dollars vs cents.
Game/embedded: lay out data for cache locality and amortise allocation out of the hot loop; a per-frame malloc is the dropped frame you can't profile away later.
Tension: Speed here is paid for in simplicity and the reader (tenets I, XXI). Every optimisation spends clarity. Buy it only where a profiler proved you must, and keep the cold 95% legible, because that's where the next bug hides. And throughput is money: unbounded fan-out, retained data and always-on compute are financial failure modes, not just slow ones.

Ask yourself: Is this cost in caller-controlled size (then bound it now, no profiler) or a known antipattern (then fix it), or am I rewriting cold, readable code into clever code I never measured?

Lineage: premature optimisation / measure first [Knuth 1974], measure before tuning [Pike 1989]; make the common case fast [Hennessy & Patterson 1990], Amdahl's law [Amdahl 1967]; N+1 / chatty interface [Fowler 2002]; algorithmic-complexity DoS [Crosby & Wallach 2003]; vectorise [Iverson 1962]; cache locality [Bell 1978]

XVIII
Make it observable, or you are guessing
Correctness is a property of the running system; emit the signals that prove your invariants held, and instrument the failure modes, not just the happy path.

You will not debug a partial failure from a stack trace, because often there isn't one: there's a latency cliff, a rising error rate, a queue depth creeping up, a retry budget quietly draining away, a silent fallback nobody noticed for a week. Observability is the verification layer, the thing that makes every other tenet checkable in production rather than just intended back in review. Queue depth (V, VII), rejection and retry counts (VI, XIX), breaker state (XIX), source-vs-cache drift (XIV), deadline budget remaining (VI), input-distribution and null-rate drift (IV). And this is not "log everything", because noise is its own kind of failure.

Backend/distributed: a trace id running through every hop turns "it's slow somewhere" into "it's slow here", and RED/USE metrics make saturation legible before it's an outage.
Data/ML: track records-in vs records-out, freshness/lag, and prediction drift. The model didn't throw anything, it just quietly got worse as the world moved on.
Frontend/embedded: real-user monitoring and client error reporting show you the crash on the device you'll never ssh into, and a bounded counter for missed deadlines turns "feels janky" into a number.
Tension: Telemetry is itself an unbounded resource (VII) with a cost and a leak risk: sample it, bound it, and never log the secret.

Ask yourself: When this invariant breaks at 3am, what signal tells me, and is it already being emitted?

Lineage: observability [Kalman 1960], software framing [Bourgon 2017]; three pillars [Bourgon 2017], [Sridharan 2018]; distributed tracing [Sigelman et al. 2010]; RED [Wilkie 2015], USE [Gregg 2012], golden signals & SLOs [Beyer et al. 2016]; alerts must be actionable, noise is its own failure [Ewaschuk 2013]; model/data drift [Schlimmer & Granger 1986]; never log the secret [OWASP Logging Cheat Sheet]

XIX
Degrade in tiers; contain the blast radius
When a dependency dies, lose a feature, not the system, and make sure one tenant's bad day isn't everyone's.

This tenet owns the retry lifecycle the others defer to.

What separates an incident from an outage is whether the failure stays contained. A recommendations service falling over should give you a page without recommendations, not a 500. Design the fallback before you need it, whether that's a cached value, stale-but-serviceable data, or a degraded mode. Containment is the spatial twin: bulkheads, per-tenant quotas, separate pools, and cell isolation all make sure a poisoned input or some greedy customer can't take down the shared substrate. Retries live here, in full: a budget, exponential backoff, jitter so that clients that failed together don't all retry together into a thundering herd, and a circuit breaker that fails fast to give the downstream some room to heal, which is only safe because the operation is idempotent (X) and the wait was deadlined (VI).

Frontend: an error boundary around a widget shows a fallback just for that widget while the rest of the app keeps working, instead of white-screening the whole thing.
Distributed systems: bulkhead thread pools per dependency, so a slow downstream exhausts its pool and not the service's; a breaker plus jittered backoff turns a blip into graceful degradation rather than a retry storm.
Data/ML: if the live feature store is down, serve a cached or default feature vector and a slightly worse prediction instead of erroring the request.
Tension: Fallbacks and bulkheads are real complexity, and an untested degraded path is just a second bug waiting for the worst moment to fire. Build the tiers you'll actually exercise, and rehearse them. (And note the genuine conflict with (XIII)'s fail-fast: degrade where staying up with less is the lesser harm; abort where proceeding corrupts.)

Ask yourself: When this dependency is down or this tenant goes rogue, what's the smallest thing I can lose, and have I ever actually run that path?

Lineage: circuit breaker, bulkheads, fail fast [Nygard 2007], [Shore 2004]; graceful degradation & retry budget & load shedding & cascading failure [Beyer et al. 2016], [Ulrich 2016]; blast radius & cell isolation [AWS 2019]; backoff + jitter [Brooker 2015], thundering herd [Molloy & Lever 2000]; idempotent retry [RFC 7231 2014]; error boundary [React 2017]; rehearse the tiers [Principles of Chaos 2015]

XX
Optimise for reversibility, deletion, and change
Prefer decisions you can undo; build a seam only when you can name the second concrete thing that will go through it.

Software is in motion. The code you write will be wrong about something, and the only real question is how expensive being wrong turns out to be. Reversibility at deploy time, things like feature flags, expand-then-contract migrations, canary and shadow deploys with auto-rollback, soft deletes, lets you ship into reality, watch (XVIII), and back out again without any ceremony. Reversibility at build time, a vendor behind a narrow interface, a feature behind one flag in one folder, a model behind a stable scoring interface, lets you swap or delete a piece without an archaeology dig for all its tendrils. The big-bang rewrite and the irreversible one-shot migration aren't bold, they're bets you've forbidden yourself from losing gracefully.

Backend/DB: expand → backfill → dual-write → switch reads → then drop keeps every intermediate state runnable and rollback-able; the drop-and-rename in one transaction is a cliff.
Frontend/mobile: ship behind a flag and ramp 1% → 100%, so a bad release is a config toggle and not an app-store resubmission.
ML/data: shadow-deploy the new model on live traffic and promote it on evidence; write to a new partition and swap pointers, because overwriting in place destroys the only thing that could have saved you.
Tension: Two faces here, the seam test and the duty to forget. Speculative flexibility is the most expensive clutter there is. The test for a seam is concrete: build it only when you can name the second real thing that will go through it (the second vendor, the actual rollback you'll run) with an owner and an expiry. One hypothetical future is not a seam, it's clutter; give every flag and scaffold an owner and a sunset, or you'll drown in zombie flags. And reversibility collides with a real duty to forget: data you keep is breach surface and legal liability (deletion rights). Soft-delete for recoverability, but keep a true hard-delete path and an encoded retention policy for the data you must destroy: a TTL, a droppable partition, or column-level classification (IV). Resolve it per data class, and never default to keep-forever.

Ask yourself: When this is wrong in a year, is the fix a scalpel or a demolition, can I name the second thing using this seam, and is anything here data I'm obligated to delete?

Lineage: reversible vs irreversible decisions [Bezos 2016]; feature flags / sunset [Hodgson 2017]; expand→contract / parallel change & canary [Sato 2014]; dark/shadow launch [Letuchy 2008]; big-bang rewrite trap [Spolsky 2000], strangler fig [Fowler 2004]; speculative generality [Fowler 1999]; seam [Feathers 2004]; deletion rights [GDPR 2016 (Art. 17)], TTL/retention [RFC 1035 1987]; reversible deploys [Forsgren et al. 2018]

XXI
Simplicity is the budget that funds everything else
The state you don't have can't be wrong; remove the case before you handle it, and delete more than you add.

Software is the only material where having more of it makes the rest heavier. Some complexity is essential, it belongs to the problem itself, and you have to carry it. The rest is accidental, some of it yours and some of it imposed on you: the abstraction for a future that never came, the configurability nobody asked for, the "temporary" flag that became a permanent branch. The most reliable way to handle a failure mode is to not have it in the first place. A stateless handler can't have stale state, an idempotent op can't be corrupted by a retry, a deleted config option can't be misconfigured. Reach for fewer states before more guards. Subtraction is real progress. The dead branch you leave behind is the one that springs back on you in an incident.

Backend: three small obvious services beat one "flexible" engine driven by a config DSL that reinvents a programming language badly; rip out the flag once the rollout is done.
Frontend: local component state beats a global store until shared state actually demands one; delete the unused component and its CSS, since "we might reuse it" is what version control is for.
Data/ML: a SQL query beats a Spark job beats a bespoke framework, until the data size forces the next tier: pay for the tier when the problem bills you, not before.
Tension: Simplicity now can mean rigidity later (vs the seams of tenet XX), and the simplest local choice can end up duplicating something (vs tenet XIV). When those pull against each other, go back to this manifesto's root: keep down what the next human has to hold in their head to make a correct change. YAGNI is about features. It is not about limits (VII) or failure handling, where a missing guardrail is just a liability dressed up to look like simplicity.

Ask yourself: Can I delete this state, flag, or branch entirely instead of writing the code that keeps it correct?

Lineage: essential vs accidental complexity [Brooks 1986], mutable state as accidental complexity [Moseley & Marks 2006]; simplicity → reliability [Dijkstra 1975 (EWD498)], [Hoare 1980]; YAGNI [Beck 1999]; config DSL reinvents a language [Greenspun 1993], worse is better [Gabriel 1990]; subtraction is progress [Saint-Exupéry 1939]; components that aren't there [Bell 1978]; software gets heavier [Lehman 1974]; idempotent [Peirce 1870]

XXII
Name to reveal, not to label
A name is the cheapest documentation and the most-read line of code; encode the one fact a reader gets wrong without it, because a misleading name is worse than none.

A reader spends more time reading names than any other token, and a precise name lets them skip the body altogether. retryWithBackoff tells you more than handle does, and pendingChargesByAccount tells you more than data. A misleading name is worse, because it installs a false model that the reader then debugs against for an hour. So encode the load-bearing fact that the type can't already carry: the unit, the ordering, whether there's a side effect.

Backend: chargeOnceIdempotent(key) warns you about the semantics; doCharge() hides them right up until the duplicate-billing incident.
Data: revenue_usd_cents is unambiguous everywhere it shows up; amount invites the unit-mismatch bug that ships a 100x error.
Frontend: useDebouncedSearch tells you when it fires; with useSearch the reader has to open the file every single time.
Tension: A name that encodes an invariant is, in effect, a duplicate of that invariant (XIV), and the duplicate can drift. The day idempotency gets dropped you have to rename chargeOnceIdempotent everywhere it appears, or the name now lies - which is the exact failure it was meant to warn against. So where a type (III) can carry the invariant, let it, and keep name-encoding for the facts no type captures: units, ordering, whether there's a side effect. Don't try to encode everything either (getUserByIdWithRetryAndCacheFromPrimaryReplica): reveal the one fact and let locality (I) carry the rest. It's precision you want, not length.

Ask yourself: Could a reader predict what this does, its units, and its caveats from the name alone, and is this name a fact no type already carries?

Lineage: naming is hard [Karlton 1996]; intention-revealing / avoid disinformation names [Martin 2008]; ubiquitous language [Evans 2003]; units-in-names / Hungarian [Simonyi 1999; Spolsky 2005], unit-mismatch failure [NASA MCO 1999]; precision-not-length [Fowler 1999]; idempotent semantics in names [Peirce 1870], [RFC 7231 2014]

XXIII
Time is an input that lies; measure with a monotonic clock, order with logic
Wall-clock time is not trustworthy: it steps backwards, skews across machines, and cannot establish causality; treat it as the hostile input (IV) it is.

The manifesto leans on now() and deadlines (II, VI) and ordering (IX), and all of that breaks the moment you trust the wall clock. Measure every duration, deadline, and timeout against a monotonic clock, because the wall clock jumps backwards on NTP correction and on leap seconds. A deadline measured against the wall clock can fire instantly, or it can fail to fire at all. And don't establish ordering or causality across machines by comparing timestamps - two events' wall-clock times prove nothing about which one actually happened first. Use logical or causal ordering instead, or a fenced sequence (IX). A TTL or token expiry checked against the wall clock can be shifted by a clock jump, or by an attacker.

Distributed systems: order events by a logical clock or a fenced sequence, never by created_at across hosts; clock skew is a race (IX) wearing a timestamp.
Billing/security: a token or lease expiry should be a duration on a monotonic base, not a wall-clock comparison that an NTP step or a lying client can move.
Embedded/realtime: a control deadline is elapsed monotonic time; if the RTC resyncs mid-loop, the wall-clock maths corrupts the timing and says nothing about it.
Ask yourself: Am I measuring a duration (use a monotonic clock) or asserting an order across machines (use logical ordering), and would a backward clock jump or a lying peer break this?

Lineage: no global 'now' [Sheehy 2015]; happens-before / logical clocks [Lamport 1978], vector clocks [Fidge & Mattern 1988]; monotonic vs wall clock [POSIX.1j 2000], NTP steps backwards [Mills 2010 (RFC 5905)]; time is an input that lies [Sussman 2012]; fenced sequence [Kleppmann 2016]; TrueTime / bounded uncertainty [Corbett et al. 2012]

XXIV
Make the run reproducible; encode the invariant as a test
A run you can't reproduce you can't debug, audit, or roll back; and where a type can't carry an invariant, an executable test must.

Two failure modes come from one root: correctness that lives in someone's head, or on someone's machine, instead of in the structure. "Works on my machine" and "we can't reproduce the model in production" both come from unpinned dependencies, seeds nobody wrote down, and input data that was never versioned. The defence is structural - lockfiles, pinned toolchains, seeded randomness recorded alongside the output, and immutable, versioned inputs to every build, every pipeline, and every training run. The second mode is the dynamic-language floor for (III) and the verification arm of (XI) and (XV), and an automated test is the canonical structural enforcer here. It re-runs the rule for everyone, forever, including the call sites that don't exist yet. Property- and fuzz-test the parsers (III, IV); test behaviour at the boundaries (XV) and at the decisions (XI), not the internals.

Data/ML: pin the environment, snapshot and version the dataset, and record the seed alongside the metrics: a result you can't regenerate is an anecdote, not a finding.
Builds/scripting: a lockfile and a pinned toolchain make the build deterministic across machines and across months; "it built last quarter" is not a build.
All domains (test as structure): a bug that escaped is a missing test, not just a bad commit, but test the contract, not the internals, or the test turns into a tax that punishes refactoring.
Tension: Tests coupled to the implementation are a tax that punishes the very refactors this manifesto wants to keep cheap (XX). Pin the behaviour at the boundary and at the decision, not the private shape. And reproducibility infrastructure is itself state - lockfiles drift, snapshots cost storage - so own it and expire it like any other state.

Ask yourself: Could someone else regenerate this exact result from pinned inputs, and is this invariant enforced by something that re-runs without me?

Lineage: property-based testing [Claessen & Hughes 2000], fuzzing [Miller et al. 1990]; reproducible & hermetic builds [Reproducible Builds 2013], lockfiles [Reproducible Builds 2013]; reproducible research / seed-recorded [Claerbout & Karrenbach 1992]; tests as spec & test-the-contract [Beck 2002], [Beck 2019]; 'works on my machine' [Cooney 2007]; testing shows presence not absence [Dijkstra 1970 (EWD249)]

XXV
Process is structure when code structure runs out
The 2am pager-holder this manifesto keeps invoking needs structure too: a named owner and a runbook for every service, flag, cache, and risky migration, and a second pair of eyes by process for the irreversible act.

Every preceding tenet pushes correctness into the code, but some correctness just can't live there. When the system breaks at 3am, observability (XVIII) tells the on-call what broke; only a runbook tells them what to do about a known failure mode, and only a named owner tells them who decides when it's something new. The irreversible act (XI) gets a second reviewer enforced by process. Four-eyes is a practice you have to adopt, not just a capability the decision/effect seam happens to enable. Every service, feature flag, cache, and risky migration has one owner of record, so "who owns this?" is never the first question of the incident.

Backend/distributed: each service and on-call rotation has an owner and a runbook of known failure modes and their first responses; the unowned service is the one nobody dares touch during the outage.
Infra/data: the irreversible migration (XI, XX) needs a named approver before it runs - process enforcing the four-eyes the seam made possible.
All domains: every flag (XX), cache (XIV), and quota (VII) has an owner and an expiry, so it doesn't turn into a zombie nobody will delete.
Tension: Process is overhead. Ceremony on the cheap and reversible is just friction, and teams will find ways around it, so keep runbooks and four-eyes for the things that are genuinely irreversible and the things that are genuinely on-call. Bureaucracy for its own sake wears away the trust it was supposed to encode.

Ask yourself: When this breaks and I'm not here, does someone know they own it and know what to do about it, and does the irreversible step force a second human because the process says so, not because somebody happened to be feeling careful?

Lineage: service ownership / you build it you run it [Vogels 2006]; runbook & on-call [Beyer et al. 2016]; four-eyes / separation of privilege [Four-eyes principle], [Saltzer & Schroeder 1975]; flag owner+expiry [Hodgson 2017]; observability cross-ref [Kalman 1960]; pit of success / illegal-states-unrepresentable [Mariani 2003], [Minsky 2010]; ceremony only for the irreversible [Bezos 2016]; humans create safety [Cook 1998]

The through-line
Every tenet here is one move wearing different clothes. Push correctness out of human vigilance and into the structure of the system: types, schemas, ownership, boundaries, atomic steps, deadlines, tests, reproducible runs, and, where the code runs out, process. The illegal state can't be built. The hostile input can't get in, the irreversible act can't fire untested, the clock can't lie without something catching it, and the promise doesn't go unkept. Not because everyone remembered, but because the wrong thing cannot be expressed in the first place.

When two tenets pull against each other (bound-everything vs YAGNI, unrepresentable-states vs dynamic-language reality, locality vs single-source-of-truth, strict-parse vs tolerant-read, fail-fast vs degrade, consistency vs availability under partition, reversibility vs the duty to forget, seams vs simplicity), there's no slogan that settles it. You go back to the objective and say it again: cut down what a tired engineer has to hold in their head, while keeping a bounded blast radius around whatever an attacker or some unlucky caller gets to control. If the blast radius is wide and the input is someone else's, pay for it now. If it's contained and it's yours, you can defer, but write down why you did.

Write for the person who is going to read this at 2am with a pager going off, and who knows less than you know now. Make the right thing the easy thing and make the wrong thing hard to even express, and never make them hold in their head what the code could have held for them.