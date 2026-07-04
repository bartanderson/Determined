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
    # symbol_context (direct single-tool path)
    (re.compile(r"(?:context for|everything about|show me|what do you know about)\s+(?:the\s+)?(?:symbol\s+)?['\"]?(\S+)['\"]?", re.I),
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

    # trace_data_flow
    (re.compile(r"(?:trace|how does|path from)\s+['\"]?(\S+)['\"]?\s+(?:to|reach)\s+['\"]?(\S+)['\"]?", re.I),
     "trace_data_flow", (1, 2)),

    # orient_to_codebase - no subject
    (re.compile(r"orient|where (?:do I|should I) start|what is this (?:project|codebase)|give me an overview", re.I),
     "orient_to_codebase", None),

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

    # corpus_synthesis - two-pass architectural analysis
    (re.compile(r"corpus\s+synthesis|synthesize\s+(?:the\s+)?corpus|architectural?\s+gaps?|full\s+(?:system\s+)?analysis|what\s+(?:is\s+)?broken|what\s+(?:would\s+)?break", re.I),
     "corpus_synthesis", None),
]


def detect_pattern(user_input: str) -> tuple[str | None, object]:
    """
    Returns (pattern_name, subject) if input matches a known pattern.
    subject is a string, tuple of strings (for two-subject patterns), or None.
    Returns (None, None) if no pattern matches.
    """
    for pattern, name, group in _DETECT_RULES:
        m = pattern.search(user_input)
        if m:
            if group is None:
                return name, None
            if isinstance(group, tuple):
                return name, tuple(m.group(g) for g in group)
            return name, m.group(group)
    return None, None


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

    def __init__(self):
        pass

    def _call_ollama(self, messages: list[dict], label: str = "", verbose: bool = False) -> str:
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
                interpretation = self._call_ollama(msgs, label=f"step-{i+1}-interp", verbose=verbose)

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
        answer = self._call_ollama(final_msgs, label="pattern-final", verbose=verbose)

        if verbose:
            print(f"\n[pattern-executor complete]\n", flush=True)

        return answer

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
