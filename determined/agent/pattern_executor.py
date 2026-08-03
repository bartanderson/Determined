"""
Pattern executor for the Determined analysis agent.

When a named task pattern is detected, this executor drives the tool sequence
mechanically. The model's only job is to interpret each step's result in 1-2
sentences. Tool selection is NOT the model's problem.

Architecture:
  PatternExecutor.run(pattern_name, subject, oracle, assessor, verbose)
    -> for each step in TASK_PATTERNS[pattern_name]:
         1. fill in args from subject
         2. dispatch tool -> result string
         3. ask model: "what does this tell you about <subject>?"
         4. accumulate interpretation
    -> final pass: ask model to synthesize all interpretations into an answer

detect_pattern(user_input) -> (pattern_name, subject) or (None, None)
  Recognizes phrases that map to a named pattern and extracts the subject.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

from determined.agent.tool_registry import TASK_PATTERNS
from determined.agent.agent_tools import dispatch


# ------------------------------------------------------------------
# Pattern detection
# Maps user phrases -> (pattern_name, subject)
# subject is None for patterns that don't need one (orient, find_dead_code)
# ------------------------------------------------------------------

_DETECT_RULES: list[tuple] = [
    # file_size_analysis — "why is X.py so big" / "what to pull out of X.py"
    # Must be FIRST so these specific-file questions don't fall through to orient_to_codebase
    (re.compile(
        r"why\s+is\s+['\"]?([A-Za-z_][\w/]*\.py)['\"]?\s+(?:so\s+)?(?:big|large|huge|fat|bloated)|"
        r"what\s+should\s+I\s+(?:pull|extract|factor|move|split)\s+out\s+(?:of|from)\s+['\"]?([A-Za-z_][\w/]*\.py)['\"]?",
        re.I,
    ), "file_size_analysis", (1, 2)),

    # js_to_python_trace — JS function → Python handler cross-language trace
    # Must come before wiring_chain/trace_call_chain to intercept JS→Python questions
    (re.compile(
        r"trace\s+(?:the\s+)?(?:call\s+from\s+)?([A-Za-z_][\w.]+)"
        r"(?:\s+in\s+['\"]?([A-Za-z_][\w./]*\.(?:js|ts))['\"]?)?"
        r"\s+to\s+(?:the\s+)?(?:python\s+)?(?:handler|endpoint|server|backend|route)",
        re.I,
    ), "js_to_python_trace", (1, 2)),

    # orient_to_codebase - must come before understand_symbol/explain/describe rules
    # to prevent "explain this codebase" from being captured as understand_symbol("this")
    (re.compile(
        r"orient"
        r"|where (?:do I|should I) start"
        r"|what is this (?:project|codebase|repo|code)"
        r"|give me (?:a\s+)?(?:\w+\s+)?overview"
        r"|(?:\w+\s+)?overview of (?:what )?this"
        r"|what does this (?:codebase|project|repo|code|tool) do"
        r"|explain (?:this\s+)?(?:the\s+)?(?:codebase|project|repo|code|tool)"
        r"|describe (?:this\s+|the\s+)?(?:system|codebase|project|repo)"
        r"|(?:i(?:'m| am) new|just (?:joined|started)|never seen this)",
        re.I,
    ), "orient_to_codebase", None),

    # symbol_context (direct single-tool path)
    # "show me" only when followed by a single bare symbol/path -- not a multi-word phrase
    (re.compile(r"(?:context for|everything about|what do you know about)\s+(?:the\s+)?(?:symbol\s+)?['\"]?(\S+)['\"]?", re.I),
     "understand_symbol", 1),
    (re.compile(r"show me\s+['\"]?(\S+)['\"]?$", re.I),
     "understand_symbol", 1),

    # understand_symbol (alias)
    (re.compile(r"(?:understand|explain|tell me about|describe)\s+(?:the\s+)?(?:symbol\s+)?['\"]?(\S+)['\"]?", re.I),
     "understand_symbol", 1),

    # concept_search
    (re.compile(r"(?:find everything about|search for|what mentions|concept search)\s+['\"]?(.+?)['\"]?$", re.I),
     "concept_search", 1),

    # assess_change_risk
    (re.compile(r"(?:risk of (?:changing\s+)?|safe to change\s+|impact of (?:changing|modifying)\s+|should I (?:change|modify|touch)\s+)['\"]?(\S+)['\"]?", re.I),
     "assess_change_risk", 1),

    # explore_file
    (re.compile(r"(?:explore|look at|what(?:'s| is) in)\s+['\"]?(\S+\.py)['\"]?", re.I),
     "explore_file", 1),

    # wiring_chain — concrete symbol-to-symbol shortest-path queries.
    # Must come before trace_data_flow and trace_call_chain so "wiring chain from X to Y"
    # is handled deterministically via graph_utils.shortest_path rather than LLM decomposition.
    # The trace arm requires identifiers (not bare English noun phrases after articles).
    (re.compile(
        r"\b(?:wiring chain|call chain|call path)\b.{0,50}?\bfrom\s+(?!(?:the|a|an)\s)\w.{1,30}?\bto\s+(?!(?:the|a|an)\s)\w|"
        r"\bhow does\s+\w.{1,30}?\breach(?:es)?\s+\w|"
        r"\bwhat connects\s+\w.{1,30}?\binto\s+\w|"
        r"\btrace\b.{0,20}?\bfrom\s+(?!(?:the|a|an)\s)\w{3}.{1,30}?\bto\s+(?!(?:the|a|an)\s)\w{3}",
        re.I,
    ), "wiring_chain", None),

    # trace_call_chain — traversal queries with high-level source/sink descriptions
    # Matches before trace_data_flow so "path from HTTP route to database" is handled
    # deterministically (graph walk) rather than treated as symbol-to-symbol.
    (re.compile(
        r"(?:trace|walk|follow)\s+(?:\w+\s+){0,3}(?:path|chain|route|flow)\s+from\s+.+?"
        r"\s+(?:to|through|into)\s+(?:the\s+)?(?:database|db|storage)|"
        r"(?:which|what)\s+functions?\s+run\s+between\s+.+?"
        r"\s+(?:and|to)\s+(?:the\s+)?(?:database|db|insert)|"
        r"(?:trace|walk)\s+(?:the\s+)?(?:full\s+)?(?:call\s+)?(?:path|chain)\s+from\s+"
        r"(?:the\s+)?(?:http|route|web|endpoint|handler|entry)|"
        r"(?:what\s+is|show me|describe)\s+the\s+path\s+from\s+(?:the\s+)?(?:web|http|route|request|endpoint|handler|entry)\b.+?"
        r"\s+(?:to|through|into)\s+(?:the\s+)?(?:database|db|storage)",
        re.I,
    ), "trace_call_chain", None),

    # trace_data_flow
    (re.compile(r"(?:trace|how does|path from)\s+(?:a\s+|an\s+|the\s+)?['\"]?(\S+)['\"]?\s+(?:to|reach)\s+(?:a\s+|an\s+|the\s+)?['\"]?(\S+)['\"]?", re.I),
     "trace_data_flow", (1, 2)),

    # find_dead_code - no subject
    (re.compile(r"find (?:dead|unused) code|what(?:'s| is) dead|unused (?:functions?|code)", re.I),
     "find_dead_code", None),

    # session_startup - no subject
    (re.compile(r"session start(?:up)?|what(?:'s| is) next.*where.*left off|morning check", re.I),
     "session_startup", None),

    # goal_intake - subject is the full goal text
    (re.compile(r"(?:i want to|i(?:'m| am) trying to|help me|how do i|i need to)\s+(?:add|build|implement|create|write|extend|make)\s+(.+)", re.I),
     "goal_intake", 1),

    # docstring_health - no subject
    (re.compile(r"docstring\s+health|missing\s+docstrings?|stale\s+docstrings?|document(?:ation)?\s+(?:gaps?|coverage|health)", re.I),
     "docstring_health", None),

    # gap_analysis - no subject (or subject is the area)
    (re.compile(r"gap\s+analysis|what(?:'s| is)\s+missing|what\s+could\s+bridge|analyze\s+(?:the\s+)?gaps?", re.I),
     "gap_analysis", None),

    # blast_radius (1): "what would break if X were removed/deleted/gone/changed"
    (re.compile(
        r"what\s+(?:would\s+|will\s+)?breaks?\s+"
        r"(?:if|when|by\s+removing|by\s+deleting|by\s+changing)\s+"
        r"(?:I\s+)?(?:change[sd]?\s+|modif\w*\s+|refactor\w*\s+|remove[ds]?\s+|delete[ds]?\s+|eliminat\w*\s+)?"
        r"(?:a\s+|an\s+|the\s+)?"
        r"['\"]?([A-Za-z_][\w./\\]*)['\"]?",
        re.I,
    ), "blast_radius", 1),

    # blast_radius (2): "impact of removing/deleting X"
    (re.compile(
        r"impact\s+of\s+(?:removing?|deleting?|eliminat\w+)\s+"
        r"(?:a\s+|the\s+)?"
        r"['\"]?([A-Za-z_][\w./\\]*)['\"]?",
        re.I,
    ), "blast_radius", 1),

    # corpus_synthesis - two-pass architectural analysis
    # Note: "what would break if X" is handled above by blast_radius
    (re.compile(r"corpus\s+synthesis|synthesize\s+(?:the\s+)?corpus|architectural?\s+gaps?|full\s+(?:system\s+)?analysis|what\s+(?:is\s+)?broken", re.I),
     "corpus_synthesis", None),
]


def detect_pattern(user_input: str) -> tuple[str | None, object]:
    """
    Returns (pattern_name, subject) if input matches a known pattern.
    subject is a string, tuple of strings (for two-subject patterns), or None.
    Returns (None, None) if no pattern matches.

    Detection is two-stage:
    1. Regex rules (_DETECT_RULES) -- fast, structurally certain, tried first.
    2. Scoring fallback (pattern_detector) -- covers natural phrasings regex misses.
    """
    for pattern, name, group in _DETECT_RULES:
        m = pattern.search(user_input)
        if m:
            if group is None:
                return name, None
            if isinstance(group, tuple):
                return name, tuple(m.group(g) for g in group)
            return name, m.group(group)

    from determined.agent.pattern_detector import detect_by_score
    return detect_by_score(user_input)


# ------------------------------------------------------------------
# Arg substitution: fill <X> placeholders in step args_hint
# ------------------------------------------------------------------

def _fill_args(args_hint: dict, subject: object) -> dict:
    """Replace <name>, <path>, <source>, <sink> etc. with actual subject value(s)."""
    if subject is None:
        return {k: v for k, v in args_hint.items() if not v.startswith("<")}

    if isinstance(subject, tuple):
        src, dst = subject[0], subject[1] if len(subject) > 1 else ""
        result = {}
        for k, v in args_hint.items():
            if "<source>" in v or "<src>" in v:
                result[k] = src
            elif "<sink>" in v or "<dst>" in v:
                result[k] = dst
            elif v.startswith("<"):
                result[k] = src
            else:
                result[k] = v
        return result

    result = {}
    for k, v in args_hint.items():
        if v.startswith("<") and v.endswith(">"):
            result[k] = str(subject)
        else:
            result[k] = v
    return result


# ------------------------------------------------------------------
# PatternExecutor
# ------------------------------------------------------------------

_STEP_SYSTEM = """\
You are a codebase analysis assistant. A tool was just run as part of an
investigation. Read the result and say in 1-2 sentences what it tells you
about the subject. Be specific. Do not speculate beyond the result."""

_FINAL_SYSTEM = """\
You are a codebase analysis assistant. You just completed a structured
investigation using multiple tools. Synthesize the findings below into a
clear, concise answer to the original question. Base every claim on the
findings. Be direct - lead with the most important thing."""


class PatternExecutor:
    """
    Drives a named task pattern step-by-step. Model interprets; executor navigates.
    """

    def _call_llm(self, messages: list[dict], label: str = "", verbose: bool = False) -> str:
        from determined.agent.llm_client import chat as _llm_chat
        text = _llm_chat(messages) or "(interpretation unavailable: no response)"
        if verbose and label:
            print(f"\n  [{label}] {text}", flush=True)
        return text

    def run(
        self,
        pattern_name: str,
        subject: object,
        question: str,
        oracle: "DBOracle",
        assessor: "Assessor",
        verbose: bool = False,
    ) -> str:
        pattern = TASK_PATTERNS.get(pattern_name)
        if not pattern:
            return f"Unknown pattern: {pattern_name}"

        subject_label = (
            " + ".join(subject) if isinstance(subject, tuple)
            else str(subject) if subject
            else "codebase"
        )

        if verbose:
            print(f"\n[pattern-executor] {pattern_name} / subject={subject_label}", flush=True)

        steps = pattern["steps"]
        findings: list[dict] = []  # {step, tool, result, interpretation}

        for i, step in enumerate(steps):
            tool = step["tool"]
            args = _fill_args(step.get("args_hint", {}), subject)
            why = step.get("why", "")

            if verbose:
                print(f"\n  [step {i+1}/{len(steps)}] {tool}({args}) — {why}", flush=True)

            # Run the tool
            try:
                result = dispatch(tool, args, oracle, assessor)
            except Exception as e:
                result = f"(tool error: {e})"

            if verbose:
                print(f"  [result] {result[:200]}", flush=True)

            # Skip interpretation if result is empty or trivially negative
            skip_interp = (
                not result
                or result.startswith("ERROR:")
                or result.startswith("(tool error")
                or "No " in result[:30] and len(result) < 60
            )

            if skip_interp:
                interpretation = f"(no data from {tool})"
            else:
                msgs = [
                    {"role": "system", "content": _STEP_SYSTEM},
                    {"role": "user", "content":
                        f"Subject: {subject_label}\n"
                        f"Tool: {tool} — {why}\n\n"
                        f"Result:\n{result[:1500]}\n\n"
                        f"What does this tell you about {subject_label}? (1-2 sentences)"},
                ]
                interpretation = self._call_llm(msgs, label=f"step-{i+1}-interp", verbose=verbose)

            findings.append({
                "step": i + 1,
                "tool": tool,
                "result": result,
                "interpretation": interpretation,
            })

        # Final synthesis
        findings_text = "\n\n".join(
            f"[Step {f['step']}: {f['tool']}]\n"
            f"Result: {f['result'][:800]}\n"
            f"Interpretation: {f['interpretation']}"
            for f in findings
        )

        final_msgs = [
            {"role": "system", "content": _FINAL_SYSTEM},
            {"role": "user", "content":
                f"Original question: {question}\n"
                f"Subject: {subject_label}\n\n"
                f"=== INVESTIGATION FINDINGS ===\n{findings_text}\n=== END ===\n\n"
                f"Synthesize these findings into a concise answer."},
        ]
        answer = self._call_llm(final_msgs, label="pattern-final", verbose=verbose)

        if verbose:
            print(f"\n[pattern-executor complete]\n", flush=True)

        return answer

    def run_traversal(
        self,
        question: str,
        oracle: "DBOracle",
        verbose: bool = False,
    ) -> str:
        """
        RM21 Technique 3: deterministic call-chain walk + one LLM synthesis.

        1. Find HTTP route handlers from the corpus (http_route column).
        2. Pick the best match for the question's intent (keyword search).
        3. walk_call_chain() from the matched handler, depth 5.
        4. One LLM synthesis call over the structured chain.
        """
        from determined.agent.agent_tools import walk_call_chain

        # Find HTTP route handlers — prefer http_route column, fall back to name heuristics
        route_rows = []
        try:
            route_rows = oracle.conn.execute(
                "SELECT name, file_path, http_route FROM functions "
                "WHERE http_route IS NOT NULL AND http_route != '' ORDER BY name"
            ).fetchall()
        except Exception:
            pass

        if not route_rows:
            # Fallback: function names that look like web handlers
            _handler_pat = (
                "name LIKE '%_get' OR name LIKE '%_post' OR name LIKE '%_put' OR "
                "name LIKE '%_delete' OR name LIKE '%route%' OR name LIKE '%view%' OR "
                "name LIKE '%handler%' OR name LIKE '%endpoint%' OR name LIKE '%capture%'"
            )
            try:
                rows = oracle.conn.execute(
                    f"SELECT name, file_path, NULL FROM functions WHERE {_handler_pat} ORDER BY name"
                ).fetchall()
                route_rows = rows
            except Exception:
                pass

        if verbose:
            print(f"\n[trace_call_chain] found {len(route_rows)} HTTP route handlers", flush=True)

        # Pick best handler: score by keyword overlap with question
        question_lower = question.lower()
        keywords = re.findall(r"[a-z]{3,}", question_lower)

        def _score(row) -> int:
            name, fp, route = row
            target = f"{name} {fp or ''} {route or ''}".lower()
            return sum(1 for kw in keywords if kw in target)

        start_symbol = None
        if route_rows:
            best = max(route_rows, key=_score)
            start_symbol = best[0]
            if verbose:
                print(f"[trace_call_chain] start node: {start_symbol} ({best[2]})", flush=True)

        if start_symbol is None:
            return (
                "No HTTP route handlers found in this corpus. "
                "The corpus may not include a web layer, or routes may not have been captured during ingestion."
            )

        # Walk the call chain
        chain = walk_call_chain(start_symbol, oracle, max_depth=5)

        if not chain:
            return f"Could not trace a call chain from '{start_symbol}' — symbol may have no recorded callees."

        if verbose:
            print(f"[trace_call_chain] chain length: {len(chain)} nodes", flush=True)

        # Build structured summary for LLM synthesis
        lines = [f"Call chain from HTTP handler '{start_symbol}':"]
        for node in chain:
            indent = "  " * node["depth"]
            stub_tag = " [STUB]" if node["is_stub"] else " [impl]"
            ret = f" -> {node['returns']}" if node["returns"] else ""
            lines.append(f"{indent}{node['symbol']} in {node['file']}{stub_tag}{ret}")
            if node["docstring"]:
                lines.append(f"{indent}  doc: {node['docstring']}")
            if node["callees"]:
                callee_list = ", ".join(node["callees"][:6])
                lines.append(f"{indent}  calls: {callee_list}")

        chain_text = "\n".join(lines)

        if verbose:
            print(f"\n[trace_call_chain chain]\n{chain_text}\n", flush=True)

        synthesis_msgs = [
            {"role": "system", "content": (
                "You are a codebase analysis assistant. "
                "A call chain has been traced deterministically from the database. "
                "Summarize it clearly: for each function in the chain, state what it does "
                "(from docstring if present), whether it is implemented or a stub, "
                "and what data it passes to the next hop. Be factual — only use what is in the chain."
            )},
            {"role": "user", "content": (
                f"Question: {question}\n\n"
                f"=== CALL CHAIN ===\n{chain_text}\n=== END ===\n\n"
                "Describe the full path from the HTTP handler to the deepest layer reached, "
                "noting stub vs implemented status for each function."
            )},
        ]
        return self._call_llm(synthesis_msgs, label="trace-synthesis", verbose=verbose)

    def run_js_to_python_trace(
        self,
        subject: object,
        question: str,
        oracle: "DBOracle",
        verbose: bool = False,
    ) -> str:
        """
        Trace a JS function → Python HTTP handler path.
        Uses find_fetch_calls to get fetch() URLs, matches to Python routes.
        One LLM synthesis call — no orient/orient overhead.
        """
        js_func = subject[0] if subject and subject[0] else None
        js_file = subject[1] if subject and len(subject) > 1 else None
        # Scope to the JS file if known, else the object prefix (e.g. "world" from "world.sendCmd")
        scope = js_file or (js_func.split(".")[0] if js_func and "." in js_func else js_func) or ""

        # Resolved cross-language edges (fetch + socket.emit → Python handler)
        cross_result = dispatch("find_cross_language_calls", {"scope": scope}, oracle, None)

        # Raw fetch() call strings as fallback detail
        fetch_result = dispatch("find_fetch_calls", {"scope": scope}, oracle, None)

        if verbose:
            print(f"\n[js-to-python] scope={scope!r} cross={cross_result[:100]}", flush=True)

        msgs = [
            {"role": "system", "content": (
                "You are a codebase analysis assistant tracing a JavaScript-to-Python call. "
                "Use the resolved cross-language call graph to find the path. "
                "State: the JS function name, how it calls Python (fetch/HTMX/socket.emit), "
                "and the Python function name that handles the request. "
                "If the specific function is not in the call graph, say so explicitly — do not invent a path."
            )},
            {"role": "user", "content": (
                f"Question: {question}\n\n"
                f"Resolved JS→Python call graph (scope: {scope or 'all'}):\n{cross_result[:2500]}\n\n"
                f"Raw fetch() call strings (for URL detail):\n{fetch_result[:1000]}\n\n"
                "Find the JS function mentioned, identify which Python function it calls, "
                "and state the communication mechanism (HTTP fetch, HTMX, or socket.emit)."
            )},
        ]
        return self._call_llm(msgs, label="js-to-python-synthesis", verbose=verbose)

    def run_file_size_analysis(
        self,
        subject: object,
        question: str,
        oracle: "DBOracle",
        assessor: "Assessor",
        verbose: bool = False,
    ) -> str:
        """
        Explain why a specific file is large and what to extract from it.
        Pulls symbols, coupling, and large-files context.
        One LLM synthesis call — no orient overhead.
        """
        file_path = (subject[0] if subject and subject[0] else None) or (
            subject[1] if subject and len(subject) > 1 else None
        )
        if not file_path:
            return "Could not identify which file to analyze from the question."

        sym_result  = dispatch("symbols_in_file", {"file_path": file_path}, oracle, assessor)
        large_result = dispatch("find_large_files", {}, oracle, assessor)
        cluster_result = dispatch("graph_clusters", {}, oracle, assessor)

        if verbose:
            print(f"\n[file-size] analyzing {file_path}", flush=True)

        msgs = [
            {"role": "system", "content": (
                "You are a codebase analysis assistant. "
                "Explain why a file is large and name 2-3 concrete things that could be extracted "
                "into separate modules. Base every claim on the facts. "
                "Name actual function groups from the symbol list — do not speculate."
            )},
            {"role": "user", "content": (
                f"Question: {question}\n\n"
                f"File: {file_path}\n\n"
                f"Symbols in file (first 2000 chars):\n{sym_result[:2000]}\n\n"
                f"Large-files ranking:\n{large_result[:600]}\n\n"
                f"File coupling (entangled pairs):\n{cluster_result[:800]}\n\n"
                "Why is this file so large? What specific function groups should be extracted?"
            )},
        ]
        return self._call_llm(msgs, label="file-size-synthesis", verbose=verbose)

    def run_no_llm(
        self,
        pattern_name: str,
        subject: object,
        oracle: "DBOracle",
        assessor: "Assessor",
        verbose: bool = False,
    ) -> str:
        """
        Run the pattern tool sequence and return structured results without
        any LLM calls. Used for testing pattern execution independently
        of model availability.
        Returns a formatted string of tool results.
        """
        pattern = TASK_PATTERNS.get(pattern_name)
        if not pattern:
            return f"Unknown pattern: {pattern_name}"

        lines = [f"Pattern: {pattern_name}", f"Subject: {subject}", ""]
        for i, step in enumerate(pattern["steps"]):
            tool = step["tool"]
            args = _fill_args(step.get("args_hint", {}), subject)
            try:
                result = dispatch(tool, args, oracle, assessor)
            except Exception as e:
                result = f"(tool error: {e})"
            lines.append(f"[{i+1}] {tool}: {result[:300]}")
        return "\n".join(lines)
