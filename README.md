Why Determined exists:
I started writing an ambitious project. It grew complex fast — I reached for AI to help with functions I was unfamiliar with, then had to dig in and actually learn them when things broke. I built a tools section to generate context, to give the AI grounding so it could understand what I was doing. I told it what I wanted. I reworked things. I threw things away.

Determined grew out of the second version of those analysis tools.

The insight that changed everything was determinism. Not as a performance property — as a design principle. I'd been trying to keep AI within bounds using guardrails, but it would ignore them. Then I learned about contracts and assertions: if you build the constraints in structurally, you can't break them without knowing. The system tells you. That's a different kind of control.

I kept asking questions, kept guiding the model — first Deepseek, then ChatGPT and others, eventually Claude when I finally got a subscription. The conversation became the tool. Determined is what happened when I decided to make that process explicit: find what's there, find what isn't, understand the shape of the system well enough to know what belongs next. And I wanted to keep it general and eventually make it available to others for their use.

What it does
Determined is a local developer intelligence tool. You point it at a codebase and it builds a structural model of the code — call graphs, role inferences, design constraint checks — then gives you a browser UI to navigate and reason about what you're looking at.

The core idea is that understanding a codebase is an investigation, not a search. You don't just want to find things; you want to see their shape, recognize patterns, and project what should exist but doesn't. Determined is built around that cycle:

See the shape (frontier graph, call tree, corpus map) → Recognize the pattern (Wirfs-Brock roles, GRASP, design tenets) → Project what's missing (stub projection, gap analysis) → Test the candidate (constraint scoring, LLM judgment) → Realize it (editor, reingest, frontier advances)

What's in the tool today
Frontier graph — nodes colored by completion status; amber nodes are the boundary between working and not-working code
Spotlight — per-symbol deep-dive: inferred role, design violations, callers/callees, data flow trace, structural pattern match
Role inference — classifies every function as COORDINATOR, CONTROLLER, SERVICE-PROVIDER, INFORMATION-HOLDER, INTERFACER, STRUCTURER, or PURE-FABRICATION (Wirfs-Brock RDD)
Design violation check — scores symbols against 25 design tenets from The Shape of the System and any design notes you've added
Stub projection — generates a candidate implementation for any stub from its calling context
Gap analysis — brainstorms what's structurally absent relative to what's there
Corpus synthesis — maps subsystems and their connections at the architectural level
Editor — read, edit, save, and reingest files without leaving the tool
Evaluate kernel — build_eval_request / execute_eval_request split enables MCTS-style (Monte Carlo) multi-candidate scoring (in progress)
How it works
Everything runs locally. No cloud API, no telemetry. I do use Claude to check how I am doing and compare my capabilities to its. Then when I found gaps I challenged him to add capabilities so that the gaps kept narrowing.

Static analysis: Python AST parser extracts functions, call edges, imports, docstrings into a SQLite corpus DB
Semantic layer: design notes, SOTS tenets, and inferred facts stored as embeddings in the same DB
Reasoning: local LLM via llama-server (tested with 3B and 8B models over Ollama-compatible API)
UI: Flask + Socket.IO server, Cytoscape.js for graph views, vanilla JS frontend
Point it at any Python codebase. The tool is code-agnostic by design — it reads structure and design intent, not language semantics.

Status
Active development. Core analysis and UI are functional. MCTS reasoning and frontier graph are the current build frontier.