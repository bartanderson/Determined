# tools/analysis/agent/local_agent.py
#
# Local conversational agent backed by llama-server (port 8081).
# Three-phase pipeline (DESIGN.md section 8):
#   Phase 1 DECOMPOSE - AI lists what it needs (NEED: lines)
#   Phase 2 RESOLVE   - deterministic pattern router runs tool calls
#   Phase 3 ASSEMBLE  - AI reads facts and writes plain English answer
#
# Usage:
#   python -m determined.agent.local_agent.py corpus.db
#   python -m determined.agent.local_agent.py corpus.db --verbose
#
# Type 'quit', 'exit', or 'q' to end the session.
# Type 'clear' to reset conversation history.

from __future__ import annotations

import argparse
import re
import sys


from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.agent_resolver import (
    parse_needs, resolve_and_expand, facts_to_text, ground_question,
    detect_heuristic,
)
from determined.agent.knowledge_status import coverage_summary, suggest_followups
from determined.agent.pattern_executor import PatternExecutor, detect_pattern

from determined.agent.llm_client import chat as _llm_chat, LLM_TIMEOUT as _LLM_TIMEOUT
from determined.agent.claim_verifier import verify_answer as _verify_claims, build_correction_block as _correction_block


# ------------------------------------------------------------------
# Phase 1 prompt - DECOMPOSE
# ------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """\
You are a code analysis assistant. Your job is to list what information
you need to answer a question about a codebase. Do NOT answer the
question yet. Just list your needs.

Output exactly one NEED: line per piece of information needed.
Use only these patterns (copy exactly):
  NEED: files in <directory>
  NEED: files matching <substring>
  NEED: symbols named <name>
  NEED: symbols in <file.py>
  NEED: what calls <symbol>
  NEED: callees of <symbol>
  NEED: what does <file.py> do
  NEED: intent of <symbol>
  NEED: findings for <symbol>
  NEED: brief for <symbol>
  NEED: imports of <file.py>

Important:
- To list all methods/functions of a class, use "NEED: symbols in the_file.py"
  (not "symbols named ClassName" -- that only finds the class declaration, not its methods)
- To check which modules/libraries a file depends on, or whether two files share a
  dependency, use "NEED: imports of <file.py>" for each file.
- Extract all symbol and file names explicitly from the question.
- Output only NEED: lines, nothing else."""


def _corpus_index(oracle: DBOracle) -> str:
    """Build a brief corpus map for the DECOMPOSE prompt when grounding is empty.

    Returns a short block listing the top hot files and known entry points so the
    model emits real file/symbol names instead of <placeholder> tokens.
    """
    try:
        rows = oracle.conn.execute(
            "SELECT file_path FROM files WHERE is_hot = 1 LIMIT 8"
        ).fetchall()
        hot = [r[0].replace("\\", "/").split("/")[-1] for r in rows]
    except Exception:
        hot = []

    try:
        ep_rows = oracle.conn.execute(
            "SELECT file_path FROM files WHERE role = 'entry_point' LIMIT 6"
        ).fetchall()
        entries = [r[0].replace("\\", "/").split("/")[-1] for r in ep_rows]
    except Exception:
        entries = []

    if not hot and not entries:
        return ""

    lines = ["Corpus map (use these real names in your NEED: lines):"]
    if hot:
        lines.append("  Key files: " + ", ".join(hot))
    if entries:
        lines.append("  Entry points: " + ", ".join(entries))
    return "\n".join(lines)


def _decompose_prompt(
    question: str,
    history: list[dict],
    grounding: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": _DECOMPOSE_SYSTEM}]
    for turn in history[-6:]:  # last 3 Q/A pairs
        messages.append({"role": turn["role"], "content": turn["content"]})
    user_content = question
    if grounding:
        user_content = f"{question}\n\n{grounding}"
    messages.append({"role": "user", "content": user_content})
    return messages


# ------------------------------------------------------------------
# Phase 3 prompt - ASSEMBLE
# ------------------------------------------------------------------

_ASSEMBLE_SYSTEM = """\
You are a code analysis assistant. Answer the question using ONLY the facts below.
Rules:
- Base every claim on what the facts explicitly say. Do not add knowledge from training.
- Do not name any method, attribute, or symbol that does not appear in the facts below.
- If the facts list callers (lines starting "Direct callers of"), name them in your answer.
- If the facts say "No direct callers found", say so - do not invent callers.
- If the facts contain a [file_purpose] or [design_note] finding, treat it as authoritative.
- Be concise. One short paragraph is enough unless the question asks for more detail."""


def _required_elements(facts: list[dict]) -> str:
    """
    Extract files and callers found in facts and return a 'you must mention' hint
    for the ASSEMBLE prompt. Empty string if nothing notable found.
    """
    files = []
    callers = []
    for f in facts:
        tool = f.get("tool", "")
        result = f.get("result", "") or ""
        if tool == "search_files" and result and not result.startswith("No "):
            for line in result.splitlines()[1:]:
                line = line.strip()
                if line:
                    files.append(line.split("(")[0].strip().split("/")[-1])
        elif tool == "list_callers" and result and "No direct callers" not in result:
            lines = result.splitlines()
            callee = lines[0].replace("Direct callers of", "").strip().strip("':").strip("'")
            for line in lines[1:]:
                line = line.strip()
                if line:
                    callers.append(f"{callee} <- {line}")
    parts = []
    if files:
        parts.append("Files found: " + ", ".join(files))
    if callers:
        parts.append("Callers found: " + "; ".join(callers[:5]))
    return "\n".join(parts)


# Matches questions asking whether any symbol satisfies multiple conditions.
# Requires an explicit conjunction (and/both) or comparative marker (also).
_COMPARATIVE_RE = re.compile(
    r"\b(is there any|does any|are there any|can any|do any"
    r"|which \w+ (has|have|does|handles?|supports?))\b"
    r".*\b(and|both)\b"
    r"|"
    r"\b(does|is|can|are|do)\b.+\balso\b.+\b(and|both)\b",
    re.I,
)


def _assembly_hint(needs: list[str], question: str = "") -> str:
    """
    Per-heuristic focus instruction injected into the ASSEMBLE prompt. Steers LLM
    on genuine synthesis cases (deterministic cases bypass assembly entirely).
    In-code for now; could migrate to knowledge.db for data-level tuning once stable.
    """
    has = lambda p: any(n.startswith(p) for n in needs)
    # comparative: cross-reference facts to find symbols satisfying multiple conditions
    if _COMPARATIVE_RE.search(question):
        return (
            "This is a comparative or yes/no question. "
            "Cross-reference the facts above to find symbols that satisfy ALL stated conditions. "
            "Answer YES or NO first. If YES, name the specific symbol(s) and cite which facts support each condition. "
            "If NO, state which condition no symbol satisfies. Do not summarize facts individually."
        )
    # pattern_similar: callees + what-calls + findings + symbols-named, no intent, no brief
    if (has("callees of") and has("what calls") and has("findings for")
            and has("symbols named") and not has("intent of") and not has("brief for")):
        return ("Name the similar symbols found and what makes them structurally similar "
                "(same name suffix / role). Show their callers. Do not claim similarity "
                "the facts do not support.")
    # (workflow prioritization is now handled deterministically by the prioritize_work
    #  tool + bypass, so no assembly hint is needed for it.)
    return ""


def _assemble_prompt(question: str, facts_text: str, history: list[dict],
                     facts: list[dict] | None = None,
                     needs: list[str] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": _ASSEMBLE_SYSTEM}]
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    required = _required_elements(facts) if facts else ""
    required_block = f"\nMust include in answer:\n{required}\n" if required else ""
    hint = _assembly_hint(needs, question) if needs else ""
    hint_block = f"\nFocus for this question type:\n{hint}\n" if hint else ""
    content = (
        f"Question: {question}\n"
        f"{required_block}{hint_block}\n"
        f"=== FACTS (use only these) ===\n{facts_text}\n=== END FACTS ==="
    )
    messages.append({"role": "user", "content": content})
    return messages


# ------------------------------------------------------------------
# Domain analyst: synthesise a state assessment for a named domain.
# Fires when the question is "what is the state of X / how complete is X".
# Enriches the retrieved facts with stub status and wiring analysis,
# then calls LLM with an analyst prompt — NOT the generic assemble prompt.
# Corpus-agnostic: operates on graph structure, never domain knowledge.
# ------------------------------------------------------------------

_ANALYST_SYSTEM = """\
You are a code analyst. Sections 1-3 are already written. Write only sections 4, 5, and 6.

Writing rules (ASD-STE100):
- Use active voice only. Never use passive voice.
- Do not use the words: may, might, could, would, should, perhaps, probably, note, however, actually, wait.
- Write one claim per sentence. Keep each sentence under 20 words.
- Start each section with its label and one sentence. No reasoning steps before the answer.

4. WIRING GAPS: Name the broken chain from entry point to the unimplemented stub.
5. DESIGN: Name any FSM configs, docstrings, or design notes that exist.
6. FIRST STEP: Name the single function with the most callers waiting for it.

Start with "4. WIRING GAPS:". Zero words before it.
"""

_DOMAIN_STATE_RE = re.compile(
    r"\b(state of|status of|how complete|completeness of|what.s missing in|"
    r"what is.+subsystem|what.s.+subsystem|overview of|survey of|"
    r"what.s built in|what exists in|what.s done in|assess)\b",
    re.I,
)

_SUBSYSTEM_NAME_RE = re.compile(
    r"\b(?:state of|status of|overview of|survey of|completeness of|"
    r"what.s built in|what exists in|what.s done in|what.s missing in|"
    r"assess)\s+(?:the\s+)?(\w+)"
    r"|(\w+)\s+subsystem\b",
    re.I,
)

_CHAIN_STOP = r"(?:from|the|a|an|is|are|does|do|what|how|this|that|it|in|of|for|with|by)"
# Pattern 1: "chain/path/trace from X to Y"
_CHAIN_RE = re.compile(
    r"\b(?:wiring chain|call chain|call path|path|chain|how does|how is|"
    r"how do(?:es)?|what connects|what calls|trace)\b"
    r".{0,40}?\bfrom\s+(?!" + _CHAIN_STOP + r"\b)(\w+)\b"
    r".{1,30}?\b(?:to|reach(?:es)?|into|trigger(?:s)?)\b\s+(?!" + _CHAIN_STOP + r"\b)(\w+)\b",
    re.I,
)
# Pattern 2: "how does X reach/connect/trigger Y" or "what connects X into Y"
_CHAIN_RE2 = re.compile(
    r"\b(?:how does|how do(?:es)?|what connects|what calls)\b\s+"
    r"(?!" + _CHAIN_STOP + r"\b)(\w+)\b"
    r".{1,30}?\b(?:reach(?:es)?|connect(?:s)?|trigger(?:s)?|call(?:s)?|lead(?:s)? to|into)\b"
    r"\s+(?!" + _CHAIN_STOP + r"\b)(\w+)\b",
    re.I,
)


def _extract_chain_endpoints(question: str) -> tuple[str, str] | tuple[None, None]:
    """Extract (src, dst) from chain questions like 'wiring chain from travel to encounter'."""
    m = _CHAIN_RE.search(question)
    if m:
        return m.group(1).lower(), m.group(2).lower()
    m = _CHAIN_RE2.search(question)
    if m:
        return m.group(1).lower(), m.group(2).lower()
    return None, None


def _is_chain_question(question: str) -> bool:
    src, dst = _extract_chain_endpoints(question)
    return src is not None and dst is not None


def build_chain_answer(question: str, oracle) -> str:
    """
    Deterministic chain synthesis — no LLM call.
    Finds the shortest call path between two symbols named in the question,
    annotates stubs, and appends a domain-analysis hint if the terminal is a stub.
    """
    from determined.agent.graph_utils import shortest_path, _shortest_path_by_name

    src, dst = _extract_chain_endpoints(question)
    if src is None:
        return "Could not extract source and destination from question."

    path = shortest_path(oracle, src, dst)
    if path is None:
        path = _shortest_path_by_name(oracle, src, dst)

    # Fuzzy fallback: src/dst may be subsystem words, not exact function names.
    # Expand candidates via (1) source_id/target_id name match, and (2) file path match —
    # so 'travel' finds progress_journey in travel_system.py even though the name itself
    # doesn't contain 'travel'.
    if path is None:
        try:
            conn = oracle.conn

            _GENERIC = frozenset({
                "get", "set", "to_dict", "to_json", "from_dict", "__init__",
                "__str__", "__repr__", "update", "save", "load", "run", "main",
            })

            def _by_name(word: str, id_col: str) -> list[str]:
                return [r[0] for r in conn.execute(
                    f"SELECT DISTINCT {id_col} FROM graph_edges "
                    f"WHERE {id_col} LIKE ? AND {id_col} != ''",
                    (f"%{word}%",)
                ).fetchall()]

            def _by_file(word: str, id_col: str) -> list[str]:
                rows = conn.execute(
                    f"SELECT DISTINCT {id_col} FROM graph_edges ge "
                    f"JOIN functions f ON f.name = ge.{id_col} "
                    f"WHERE (f.file_path LIKE ? OR f.file_path LIKE ?) AND {id_col} != ''",
                    (f"%/{word}%", f"%\\{word}%")
                ).fetchall()
                return [r[0] for r in rows
                        if len(r[0]) > 4 and r[0] not in _GENERIC and not r[0].startswith("__")]

            # Try in confidence order: name×name first, then file×name, then name×file
            src_by_name = _by_name(src, "source_id")
            dst_by_name = _by_name(dst, "target_id")
            # Exclude from file-match candidates any symbol whose name already signals
            # the OTHER subsystem — they're cross-contamination, not origin points.
            src_by_file = [s for s in _by_file(src, "source_id") if dst not in s.lower()]
            dst_by_file = [d for d in _by_file(dst, "target_id") if src not in d.lower()]

            for src_cands, dst_cands in [
                (src_by_name, dst_by_name),
                (src_by_file, dst_by_name),
                (src_by_name, dst_by_file),
                (src_by_file, dst_by_file),
            ]:
                for s in src_cands:
                    for d in dst_cands:
                        p = shortest_path(oracle, s, d)
                        if p:
                            path = p
                            src, dst = s, d
                            break
                    if path:
                        break
                if path:
                    break
        except Exception:
            pass

    if path is None:
        return (
            f"No call path found from '{src}' to '{dst}'. "
            f"They may be in disconnected subgraphs, or one name was not resolved."
        )

    conn = oracle.conn
    # Annotate each hop: mark stubs and file location
    annotated = []
    for name in path:
        try:
            row = conn.execute(
                "SELECT is_stub, file_path FROM functions WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            if row:
                label = f"{name} ({'stub' if row[0] else row[1].split('/')[-1].split(chr(92))[-1]})"
            else:
                label = name
        except Exception:
            label = name
        annotated.append(label)

    chain_str = " → ".join(annotated)
    result = f"Call chain from '{src}' to '{dst}':\n  {chain_str}"

    # If terminal node is a stub, append a one-line action hint
    terminal = path[-1]
    try:
        terminal_row = conn.execute(
            "SELECT is_stub FROM functions WHERE name = ? LIMIT 1", (terminal,)
        ).fetchone()
        if terminal_row and terminal_row[0]:
            callers = conn.execute(
                "SELECT COUNT(*) FROM graph_edges WHERE callee = ? OR callee LIKE ?",
                (terminal, f"%.{terminal}")
            ).fetchone()[0]
            result += f"\n  → '{terminal}' is a stub with {callers} caller(s) waiting — implement it to close this chain."
    except Exception:
        pass

    return result


def _is_domain_analysis_question(question: str, needs: list[str]) -> bool:
    """True when the question asks for a domain state assessment."""
    if _DOMAIN_STATE_RE.search(question):
        return True
    # Also fire when survey heuristic matched (files+symbols+findings) but question
    # has an evaluative word — the user wants analysis, not a data dump.
    evaluative = re.compile(
        r"\b(state|status|complete|missing|done|built|ready|progress|overview|assess)\b", re.I
    )
    return bool(_is_survey_needs(needs) and evaluative.search(question))


def _enrich_with_stub_status(facts: list[dict], oracle, subsystem: str = "") -> dict:
    """
    Augment the fact set with stub/caller status for each symbol found.
    Returns a dict with keys: complete, stubs, orphaned, design_notes.
    Corpus-agnostic: operates purely on graph tables.
    """
    symbol_names = []
    for f in facts:
        if f.get("tool") not in ("search_symbols", "symbols_in_file"):
            continue
        result = f.get("result", "") or ""
        for line in result.splitlines()[1:]:
            line = line.strip()
            if line:
                name = line.split("(")[0].strip().split()[-1]
                if name:
                    symbol_names.append(name)

    conn = oracle.conn
    complete, stubs, orphaned = [], [], []
    seen = set()
    for name in symbol_names[:30]:
        if name in seen:
            continue
        seen.add(name)
        try:
            stub_row = conn.execute(
                "SELECT is_stub, file_path FROM functions WHERE name = ? LIMIT 1",
                (name,)
            ).fetchone()
            caller_count = conn.execute(
                "SELECT COUNT(*) FROM graph_edges WHERE callee = ? OR callee LIKE ?",
                (name, f"%.{name}")
            ).fetchone()[0]
            if not stub_row:
                continue
            fname = stub_row[1].split("/")[-1].split("\\")[-1]
            if stub_row[0]:
                if caller_count:
                    stubs.append(f"{name} ({fname}, {caller_count} caller(s) waiting)")
                else:
                    stubs.append(f"{name} ({fname}, not yet called)")
            else:
                if caller_count:
                    complete.append(f"{name} ({fname}, {caller_count} caller(s))")
                else:
                    orphaned.append(f"{name} ({fname})")
        except Exception:
            pass

    # Surface design notes — search by subsystem name if available, else mine fact words
    design_notes = []
    search_terms = [subsystem] if subsystem else []
    if not search_terms:
        domain_words = set()
        for f in facts:
            result = f.get("result", "") or ""
            for line in result.splitlines()[:5]:
                for word in line.lower().split():
                    if len(word) > 4 and word.isalpha():
                        domain_words.add(word)
        search_terms = list(domain_words)[:5]

    for term in search_terms:
        try:
            rows = conn.execute(
                "SELECT kind, content FROM knowledge_artifacts "
                "WHERE (subject LIKE ? OR content LIKE ?) AND kind IN ('design_note','finding','sots') "
                "LIMIT 3",
                (f"%{term}%", f"%{term}%")
            ).fetchall()
            for kind, content in rows:
                design_notes.append(f"[{kind}] {content[:120]}")
        except Exception:
            pass

    return {
        "complete": complete,
        "stubs": stubs,
        "orphaned": orphaned,
        "design_notes": design_notes[:8],
    }


def _fmt_list(items: list[str]) -> str:
    """Format a list of items as a readable comma-joined string."""
    if not items:
        return "none found."
    return "; ".join(items) + "."


def _build_wiring_gaps(enrichment: dict, oracle) -> str:
    """
    Deterministically derive wiring gaps: for each stub with callers,
    find what calls it and report the broken edge.
    """
    conn = oracle.conn
    gaps = []
    for entry in enrichment["stubs"]:
        # entry looks like "func_name (file.py, N caller(s) waiting)"
        name = entry.split("(")[0].strip()
        if "not yet called" in entry:
            continue
        try:
            rows = conn.execute(
                "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? OR callee LIKE ? LIMIT 3",
                (name, f"%.{name}")
            ).fetchall()
            callers = [r[0].split(".")[-1] for r in rows]
            if callers:
                gaps.append(f"{' / '.join(callers)} → {name} (unimplemented)")
        except Exception:
            pass
    if not gaps:
        return "No direct wiring gaps found in graph data."
    return "; ".join(gaps) + "."


def build_domain_analysis(question: str, facts: list[dict], oracle,
                           history: list[dict]) -> str:
    """
    Fully deterministic domain state assessment — no LLM call.
    All 6 sections derived from graph data and knowledge artifacts.
    """
    subsystem = ""
    m = _SUBSYSTEM_NAME_RE.search(question)
    if m:
        subsystem = (m.group(1) or m.group(2) or "").lower().strip()
    enrichment = _enrich_with_stub_status(facts, oracle, subsystem=subsystem)

    s1 = _fmt_list(enrichment["complete"])
    s2 = _fmt_list(enrichment["stubs"])
    s3 = _fmt_list(enrichment["orphaned"])

    # Section 4: wiring gaps from graph
    s4 = _build_wiring_gaps(enrichment, oracle)

    # Section 5: design artifacts already collected
    if enrichment["design_notes"]:
        s5 = "; ".join(n[:80] for n in enrichment["design_notes"][:3]) + "."
    else:
        s5 = "No design artifacts found — run discovery to build coverage."

    # Section 6: first step = stub with most callers waiting (first in stubs list)
    callers_waiting = [e for e in enrichment["stubs"] if "waiting" in e]
    if callers_waiting:
        first = callers_waiting[0]
        name = first.split("(")[0].strip()
        s6 = f"Implement {name} — it already has callers depending on it."
    elif enrichment["stubs"]:
        name = enrichment["stubs"][0].split("(")[0].strip()
        s6 = f"Implement {name} and wire it into a caller."
    else:
        s6 = "All named symbols are implemented. Run discovery to find deeper gaps."

    return (
        f"1. COMPLETE: {s1}\n"
        f"2. STUBS: {s2}\n"
        f"3. ORPHANED: {s3}\n"
        f"4. WIRING GAPS: {s4}\n"
        f"5. DESIGN: {s5}\n"
        f"6. FIRST STEP: {s6}\n"
    )


def _strip_reasoning_preamble(text: str) -> str:
    """Strip inline reasoning before the first numbered section heading."""
    import re as _re
    m = _re.search(r"(?m)^(\d+\.\s+[A-Z]|COMPLETE:|STUBS:|WIRING|FIRST STEP)", text)
    if m and m.start() > 0:
        return text[m.start():]
    return text


def _strip_to_section(text: str, section_num: int) -> str:
    """Strip everything before the given numbered section heading."""
    import re as _re
    m = _re.search(rf"(?m)^{section_num}\.\s+\S", text)
    if m:
        return text[m.start():]
    # Fallback: try to find any of the expected section labels
    for label in ("WIRING GAPS", "DESIGN", "FIRST STEP"):
        m = _re.search(rf"(?m)\b{label}\b", text)
        if m:
            # Find start of that line
            line_start = text.rfind("\n", 0, m.start()) + 1
            return f"{section_num}. {text[line_start:]}"
    return ""


# ------------------------------------------------------------------
# Survey bypass: build structured answer directly from facts
# (bypasses LLM for survey heuristic - tiny model ignores facts)
# ------------------------------------------------------------------

def _is_survey_needs(needs: list[str]) -> bool:
    # dev_plan heuristic has the same symbols/files/findings pattern but also has
    # "entry points" - exclude those so they go through LLM for synthesis
    if any(n == "entry points" for n in needs):
        return False
    return (any(n.startswith("symbols named ") for n in needs) and
            any(n.startswith("files matching ") for n in needs) and
            any(n.startswith("findings for ") for n in needs))


def build_survey_answer(facts: list[dict]) -> str:
    """
    Deterministic survey answer built directly from facts.
    Used when survey heuristic fires to avoid LLM ignoring the fact set.
    """
    files: list[str] = []
    symbols: list[str] = []
    callers: list[str] = []
    findings: list[str] = []

    for f in facts:
        tool = f.get("tool", "")
        result = f.get("result", "") or ""
        if not result:
            continue

        if tool == "search_files":
            if not result.startswith("No "):
                for line in result.splitlines()[1:]:
                    line = line.strip()
                    if line:
                        files.append(line)

        elif tool == "search_symbols":
            if not result.startswith("No "):
                seen = set()
                for line in result.splitlines()[1:]:
                    line = line.strip()
                    if line and line not in seen:
                        seen.add(line)
                        symbols.append(line)

        elif tool == "list_callers":
            if "No direct callers" not in result:
                lines = result.splitlines()
                callee = lines[0].replace("Direct callers of", "").strip().strip("':").strip("'")
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        callers.append(f"  {callee} <- {line}")

        elif tool == "get_findings":
            if "No stored" not in result:
                findings.append(result)

    sections: list[str] = []

    sections.append("Files:\n" + ("\n".join(f"  {f}" for f in files) if files else "  (none found)"))

    if symbols:
        sections.append("Symbols:\n" + "\n".join(f"  {s}" for s in symbols))
    else:
        sections.append("Symbols: (none found)")

    if callers:
        sections.append("Call relationships:\n" + "\n".join(callers))

    if findings:
        sections.append("Stored findings:\n" + "\n".join(f"  {f}" for f in findings))
    else:
        sections.append("Stored findings: (none - run discovery pass to populate)")

    return "\n\n".join(sections)


# ------------------------------------------------------------------
# git_history bypass: the git log output IS the answer.
# LLM ignores the log fact and talks about callers instead, so
# we return the log directly (same rationale as survey/workflow).
# ------------------------------------------------------------------

def _is_git_history_needs(needs: list[str]) -> bool:
    return any(n.startswith("git history of ") for n in needs)


def build_git_history_answer(facts: list[dict]) -> str:
    """Deterministic git-history answer: return the git_log_for result directly."""
    git_fact = next(
        (f["result"] for f in facts if f["tool"] == "git_log_for" and f["result"]),
        None,
    )
    return git_fact if git_fact else "(no git history found)"


# ------------------------------------------------------------------
# impact bypass: symbol_brief (task_generator output) already IS the
# impact analysis - direct callers + impact zone. LLM degrades it
# (can't synthesize "no direct callers" into "this is an entry point").
# Return the brief directly, append knowledge.db findings for context.
# ------------------------------------------------------------------

def _is_impact_needs(needs: list[str]) -> bool:
    # impact NEEDs: "brief for X" + "what calls X" + "findings for X", no "symbols named"
    # (distinguishes from explain, which has "brief for" but also "symbols named")
    return (any(n.startswith("brief for ") for n in needs) and
            any(n.startswith("what calls ") for n in needs) and
            not any(n.startswith("symbols named ") for n in needs))


def build_impact_answer(facts: list[dict]) -> str:
    """Deterministic impact answer: the symbol_brief (task_generator output) is the
    impact analysis - it already includes direct callers, impact zone, and findings.
    Fall back to raw callers + findings only if the brief is missing."""
    brief = next(
        (f["result"] for f in facts if f["tool"] == "symbol_brief" and f["result"]),
        None,
    )
    if brief:
        return brief
    callers = next((f["result"] for f in facts if f["tool"] == "list_callers"), "")
    findings = [
        f["result"] for f in facts
        if f["tool"] == "get_findings" and f["result"] and "No stored" not in f["result"]
    ]
    parts = [p for p in ([callers] + findings) if p]
    return "\n\n".join(parts) if parts else "(no impact data found)"


def _postprocess_answer(answer: str, facts: list[dict]) -> str:
    """
    Guard against fact-omission: if answer claims no callers but facts list callers,
    append the correct caller list from facts. Pure string post-processing, no AI call.
    """
    import re
    answer_lower = answer.lower()
    no_caller_phrases = ("no direct caller", "no callers", "not called", "no caller found")
    if not any(p in answer_lower for p in no_caller_phrases):
        return answer

    # Extract caller lines from facts
    caller_lines = []
    for f in facts:
        if f.get("tool") != "list_callers" or not f.get("result"):
            continue
        result = f["result"]
        if "No direct callers" in result:
            continue
        for line in result.splitlines():
            line = line.strip()
            if line and not line.startswith("Direct callers"):
                caller_lines.append(line)

    if not caller_lines:
        return answer

    injected = "\n\nNote: Facts show these direct callers: " + "; ".join(caller_lines[:5])
    return answer + injected


# ------------------------------------------------------------------
# LLM call
# ------------------------------------------------------------------

def _call_llm(messages: list[dict], verbose: bool = False, label: str = "") -> str:
    text = _llm_chat(messages, timeout=_LLM_TIMEOUT) or "ERROR: llama-server is not running. Start the UI to launch it automatically, or run llama-server manually on port 8081."
    if verbose and label:
        print(f"\n[{label}]\n{text}\n[/{label}]", flush=True)
    return text


# ------------------------------------------------------------------
# Single question/answer cycle (three-phase)
# ------------------------------------------------------------------

def _answer(
    user_input: str,
    history: list[dict],
    oracle: DBOracle,
    assessor: Assessor,
    verbose: bool = False,
    _trace: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    Run three-phase pipeline for one user question.
    Returns (final_answer, updated_history).
    History is a list of {role, content} dicts (user/assistant pairs),
    extended in place with the (question, answer) pair.
    If _trace dict is provided it is filled with pipeline metadata.
    """
    # Phase 0a: PATTERN EXECUTOR - check for named task patterns before anything else
    pattern_name, subject = detect_pattern(user_input)
    if pattern_name:
        if verbose:
            print(f"\n[pattern detected] {pattern_name} / subject={subject}", flush=True)
        executor = PatternExecutor()
        if pattern_name == "wiring_chain":
            answer = build_chain_answer(user_input, oracle)
        elif pattern_name == "trace_call_chain":
            answer = executor.run_traversal(user_input, oracle, verbose=verbose)
        else:
            answer = executor.run(pattern_name, subject, user_input, oracle, assessor, verbose=verbose)
        if _trace is not None:
            _trace.update({"pattern": pattern_name, "subject": subject, "needs": [], "tools": []})
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": answer})
        return answer, history

    # Phase 0b: GROUND
    grounding = ground_question(user_input, oracle, assessor)
    if verbose and grounding:
        print(f"\n[phase0-ground]\n{grounding}\n[/phase0-ground]", flush=True)

    # Phase 1: DECOMPOSE - try named heuristic first, fall back to LLM
    needs = detect_heuristic(user_input)
    if needs:
        if verbose:
            print(f"\n[heuristic matched] {needs}", flush=True)
        heuristic_matched = True
    else:
        heuristic_matched = False
        # If grounding found nothing, inject corpus index so model has real names to use
        effective_grounding = grounding or _corpus_index(oracle)
        decompose_msgs = _decompose_prompt(user_input, history, grounding=effective_grounding)
        needs_text = _call_llm(decompose_msgs, verbose=verbose, label="phase1-decompose")
        if needs_text.startswith("ERROR:"):
            return needs_text, history
        needs = parse_needs(needs_text)

    if verbose:
        print(f"\n[needs parsed] {needs}", flush=True)

    # Phase 2: RESOLVE
    facts = []
    if needs:
        facts = resolve_and_expand(needs, oracle, assessor)
        if verbose:
            for f in facts:
                print(f"  [tool={f['tool']} args={f['args']}] {f['result'][:120]}", flush=True)
        facts_text = facts_to_text(facts)
    else:
        facts_text = "(no structured needs identified - answering from general knowledge)"

    # Phase 3: ASSEMBLE
    # Several heuristics get a deterministic answer (tiny model ignores or degrades facts).
    bypass = None
    if _is_domain_analysis_question(user_input, needs):
        answer = build_domain_analysis(user_input, facts, oracle, history); bypass = "domain_analyst"
    elif _is_survey_needs(needs):
        answer = build_survey_answer(facts); bypass = "survey"
    elif _is_git_history_needs(needs):
        answer = build_git_history_answer(facts); bypass = "git_history"
    elif _is_impact_needs(needs):
        answer = build_impact_answer(facts); bypass = "impact"
    elif needs == ["workflow status"]:
        wf_fact = next((f["result"] for f in facts if f["tool"] == "workflow_status"), None)
        answer = wf_fact if wf_fact else "(no workflow items found)"; bypass = "workflow_status"
    elif needs == ["prioritize work"]:
        pw_fact = next((f["result"] for f in facts if f["tool"] == "prioritize_work"), None)
        answer = pw_fact if pw_fact else "(no work items found)"; bypass = "prioritize_work"
    elif needs == ["development priorities"]:
        dp_fact = next((f["result"] for f in facts if f["tool"] == "development_priorities"), None)
        answer = dp_fact if dp_fact else "(no features found)"; bypass = "development_priorities"
    else:
        assemble_msgs = _assemble_prompt(user_input, facts_text, history, facts=facts, needs=needs)
        answer = _call_llm(assemble_msgs, verbose=verbose, label="phase3-assemble")
        # Verification loop (RM21 Technique 1): check structural claims against DB
        corrections = _verify_claims(answer, oracle.conn)
        if corrections:
            corrected_facts = facts_text + _correction_block(corrections)
            revised_msgs = _assemble_prompt(user_input, corrected_facts, history, facts=facts, needs=needs)
            if verbose:
                print(f"\n[verify] {len(corrections)} correction(s); re-assembling", flush=True)
            answer = _call_llm(revised_msgs, verbose=verbose, label="phase3-verify")
        answer = _postprocess_answer(answer, facts)

    if _trace is not None:
        _trace.update({
            "pattern": None,
            "heuristic": "matched" if heuristic_matched else "llm",
            "bypass": bypass,
            "needs": needs,
            "tools": [{"tool": f["tool"], "args": f["args"], "preview": (f.get("result") or "")[:120]} for f in facts],
        })

    # Phase 4: SUGGEST
    suggestions = suggest_followups(facts, oracle, assessor)
    if suggestions:
        answer = answer + "\n\n" + suggestions

    history.append({"role": "user",      "content": user_input})
    history.append({"role": "assistant", "content": answer})
    return answer, history


# ------------------------------------------------------------------
# Main REPL
# ------------------------------------------------------------------

def run(db_path: str, verbose: bool = False) -> None:
    print(f"\nLoading corpus: {db_path}")
    try:
        oracle = DBOracle(db_path)
        assessor = Assessor(oracle)
    except Exception as e:
        print(f"ERROR loading corpus: {e}")
        sys.exit(1)

    root = oracle.get_project_root() or db_path
    print(f"Project root:   {root}")
    print(f"Model:          llama-server (port 8081)")
    from determined.agent.knowledge_status import coverage_report
    cov = coverage_report(oracle, assessor)
    pct = int(100 * cov["known_files"] / cov["total_files"]) if cov["total_files"] else 0
    print(f"\n{coverage_summary(oracle, assessor)}")
    if pct < 10:
        print(f"  Coverage is low — answers will be sparse until the corpus is explored.")
        print(f"  Run 'orient' to survey the codebase, or 'discover' to expand coverage.")
    print(f"\nType your question. 'clear' to reset. 'quit' to exit.")
    print(f"Special: 'what do you know?' | 'what haven't you explored?' | 'discover'")
    print(f"Workflow: 'what's next' | 'reprioritize' | 'add to backlog: <item>' | 'reorder as 3,1,2'\n")

    history: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if user_input.lower() == "clear":
            history = []
            print("[conversation history cleared]\n")
            continue

        if user_input.lower() in ("what do you know?", "what do you know"):
            print(f"\n{coverage_summary(oracle, assessor)}\n")
            continue

        if user_input.lower() in ("what haven't you explored?", "what havent you explored?",
                                   "what haven't you explored", "unexplored"):
            from determined.agent.knowledge_status import coverage_report
            r = coverage_report(oracle, assessor)
            unknown = r["unknown_files"]
            if unknown:
                print(f"\nUnexplored files ({len(unknown)} of {r['total_files']}):")
                for f in unknown:
                    print(f"  {f}")
            else:
                print("\nAll files have been surveyed.")
            print()
            continue

        if user_input.lower() == "discover":
            from determined.agent.discovery_agent import run as discover_run
            discover_run(db_path, limit=5, verbose=True)
            print(f"\n{coverage_summary(oracle, assessor)}\n")
            continue

        if user_input.lower() in ("reprioritize", "suggest priorities", "suggest order"):
            status = assessor.workflow_status()
            if status == "No active workflow items.":
                print(f"\n{status}\n")
                continue
            msgs = [
                {"role": "system", "content":
                    "You are a project planning assistant. Given a list of workflow items, "
                    "suggest a priority ordering with brief reasoning for each position. "
                    "End with: 'To apply this order, type: reorder as <id>,<id>,...'"},
                {"role": "user", "content":
                    f"Here are the current workflow items:\n\n{status}\n\n"
                    "Suggest a priority order for the active backlog/next_up items, "
                    "considering dependencies and logical sequencing."},
            ]
            suggestion = _call_llm(msgs, verbose=verbose, label="reprioritize")
            print(f"\nAgent: {suggestion}\n")
            continue

        print("\nThinking...", flush=True)
        answer, history = _answer(user_input, history, oracle, assessor, verbose=verbose)
        print(f"\nAgent: {answer}\n")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _ingest_source(source_dir: str, summarize: bool = False) -> str:
    """Ingest a source directory into a corpus DB, return the DB path."""
    import re
    from pathlib import Path
    from determined.engine.run_engine import EngineRunner
    from determined.persistence.persistence_engine import create_database

    src = Path(source_dir).resolve()
    if not src.is_dir():
        print(f"ERROR: --source path is not a directory: {source_dir}")
        sys.exit(1)

    # derive DB name from full path to match convention: C_Users_bartl_dev_harrow.db
    # Drop colons (drive separator), replace other non-alphanumeric with underscore
    path_str = str(src).replace(":", "")
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", path_str).strip("_")
    db_path = f"{safe}.db"

    print(f"Ingesting {src} -> {db_path} ...")
    db = create_database(db_path)
    corpus = type("Corpus", (), {"root_path": str(src)})()
    EngineRunner().run(corpus=corpus, project_prefixes=[], repo_root=str(src), connection=db)
    db.close()
    print(f"Ingestion complete: {db_path}")

    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor
    oracle = DBOracle(db_path)
    assessor = Assessor(oracle)

    # Auto-extract structural design facts (no LLM, < 1s)
    if assessor._knowledge_conn is not None:
        counts = assessor.extract_design_facts()
        total = sum(counts.values())
        print(f"Knowledge extracted: {total} structural facts "
              f"({counts.get('entry_points',0)} entry points, "
              f"{counts.get('dead_code',0)} dead code candidates, "
              f"{counts.get('hot_symbols',0)} hot symbols, "
              f"{counts.get('stub_files',0)} stub files)")

    # Contract checks: JSON stage invariants + DB-derived symbol checks
    # + persist violations + record drift history for health tracking
    from determined.contracts.persist_contract_violations import persist_contract_violations
    from determined.contracts.contract_drift_classifier import ContractDriftClassifier
    from determined.contracts.load_contract import load_system_contract, ContractLoadError
    from determined.contracts.contract_validator import ContractRuntimeValidator
    from determined.assessor.assessor import ContractReport

    # 1. DB-derived symbol-reference integrity checks (existing)
    reports = assessor.file_contract_reports()

    # 2. JSON stage invariant checks: build contexts from DB facts post-ingest
    try:
        system_contract = load_system_contract()
        validator = ContractRuntimeValidator(system_contract)
        file_count = oracle.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        fn_count = oracle.conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
        edge_count = oracle.conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        ref_count = oracle.conn.execute("SELECT COUNT(*) FROM symbol_references").fetchone()[0]
        # Context keys must match what _check_rule reads, not the invariant names:
        # - edge_conservation invariant reads context["edges"]
        # - classification_must_not_be_in_persistence reads context["classification_called_in_persistence"]
        # - snapshot_must_match_graph reads context["snapshot_mismatch"]
        # Generic boolean invariants read context[invariant_name] directly.
        ref_edge_mismatch = abs(edge_count - ref_count) > max(edge_count, ref_count) * 0.5 if edge_count else False
        stage_contexts = {
            "ingestion": {
                "must_emit_analysis_objects": file_count > 0,
                "must_preserve_raw_ast_structure": fn_count > 0,
            },
            "graph_build": {
                "edges": edge_count,
                "classification_called_in_persistence": False,
                "must_only_consume_classified_edges": edge_count > 0,
            },
            "snapshot": {
                "edges": edge_count,
                "snapshot_mismatch": ref_edge_mismatch,
            },
            "persistence": {
                "no_classification_logic": True,
                "must_accept_flattened_symbols_only": True,
            },
        }
        stage_violations = validator.validate_all_stages(stage_contexts)
        if stage_violations:
            stage_report = ContractReport(
                file_path="<pipeline>",
                violations=stage_violations,
                ok=False,
            )
            reports.append(stage_report)
    except ContractLoadError:
        pass  # JSON missing — skip stage checks, don't block ingest

    # 3. Persist violations and record drift history
    violation_count = sum(len(r.violations) for r in reports)
    if violation_count:
        for report in reports:
            if report.violations:
                persist_contract_violations(oracle.conn, report)
        print(f"Contract violations: {violation_count} persisted")
    signals = ContractDriftClassifier().classify(reports)
    for s in signals:
        oracle.conn.execute(
            "INSERT INTO contract_drift_history (contract_name, classification, layer, count)"
            " VALUES (?, ?, ?, ?)",
            (s.contract_name, s.classification, s.layer, s.count),
        )
    oracle.conn.commit()

    # Optional: generate AI summaries for every file (requires LLM)
    if summarize:
        _summarize_all_files(src, oracle, assessor)

    oracle.conn.close()
    return db_path


_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
_SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "dist", "build", ".mypy_cache", ".pytest_cache",
    "Lib", "Scripts", "Include", "lib", "bin", "include",
    "ai_context", "archive", "archives",
}


def _summarize_all_files(src, oracle, assessor) -> None:
    """
    Walk src to discover files and generate semantic summaries.
    Source pass: .py files processed via semantic_summary().
    Doc pass: text/doc files checked for relevance via doc_extractor,
    then ingested into knowledge_artifacts if they describe the code.
    Skips already-cached. Aborts gracefully if LLM is unreachable.
    """
    from pathlib import Path
    from determined.agent.doc_extractor import discover_docs, extract_rules
    from determined.ingestion.scan_project_files import load_ignore_list

    src = Path(src)
    skip_dirs = _SKIP_DIRS | load_ignore_list(src)

    # --- Pass 1: Python source files ---
    py_files = []
    for p in src.rglob("*.py"):
        if any(part in skip_dirs or part.startswith(".") for part in p.parts):
            continue
        py_files.append(p)
    py_files.sort()

    total_py = len(py_files)
    print(f"Generating AI summaries for {total_py} source files (requires LLM) ...")
    done = skipped = failed = 0

    for p in py_files:
        rel = str(p.relative_to(src)).replace("\\", "/")
        existing = assessor.semantic_summary_if_fresh(rel)
        if existing:
            skipped += 1
            continue
        try:
            result = assessor.semantic_summary(rel)
            if result.get("content"):
                done += 1
                print(f"  [{done+skipped}/{total_py}] {rel}", flush=True)
            else:
                failed += 1
        except Exception as e:
            msg = str(e).lower()
            if "connection" in msg or "refused" in msg or "timeout" in msg:
                print(f"\nLLM unreachable ({e}). Stopping -- {done} summaries written.")
                return
            failed += 1

    print(f"Source summaries: {done} generated, {skipped} already cached, {failed} failed.")

    # --- Pass 2: Text/doc files -- discover and ingest design rules ---
    if assessor._knowledge_conn is None:
        return

    docs = discover_docs(str(src))
    # discover_docs already filters by extension, skip dirs, and constraint density
    if not docs:
        return

    print(f"Found {len(docs)} doc files; ingesting design rules ...")
    rules_written = 0
    corpus = oracle.get_project_root() or str(src)

    for doc in docs:
        rules = extract_rules(doc.path, rel_path=doc.rel_path, source_confidence=doc.confidence)
        for rule in rules:
            try:
                assessor._knowledge_conn.execute(
                    """INSERT OR IGNORE INTO knowledge_artifacts
                       (subject, kind, content, provenance, corpus, created_at)
                       VALUES (?, 'design_note', ?, ?, ?, datetime('now'))""",
                    (rule.subject, rule.rule,
                     f"{rule.provenance}:{rule.kind}", corpus),
                )
                rules_written += 1
            except Exception:
                pass
        assessor._knowledge_conn.commit()

    print(f"Design rules ingested: {rules_written} rules from {len(docs)} docs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Local codebase analysis agent backed by LLM."
    )
    parser.add_argument("db_path", nargs="?",
                        help="Path to corpus DB (e.g. corpus.db). "
                             "Omit when using --source.")
    parser.add_argument("--source", metavar="DIR",
                        help="Source directory to ingest; DB is derived automatically.")
    parser.add_argument("--summarize", action="store_true",
                        help="After ingestion, generate AI file summaries via LLM (slow; skips cached).")
    parser.add_argument("--reingest-file", metavar="FILE",
                        help="Re-ingest a single changed file into an existing corpus DB. "
                             "Requires db_path.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show phase outputs and tool calls")
    parser.add_argument("--ui", action="store_true",
                        help="Start the browser-based dev console instead of the REPL")
    parser.add_argument("--port", type=int, default=5050,
                        help="Port for the UI server (default: 5050)")
    args = parser.parse_args()

    if getattr(args, "summarize", False) and not args.source:
        parser.error("--summarize requires --source")

    reingest_file_arg = getattr(args, "reingest_file", None)
    if reingest_file_arg:
        if not args.db_path:
            parser.error("--reingest-file requires db_path")
        from determined.ingestion.reingest_file import reingest_file
        result = reingest_file(args.db_path, reingest_file_arg)
        print(result)
        raise SystemExit(0)

    if args.source:
        db_path = _ingest_source(args.source, summarize=getattr(args, "summarize", False))
    elif args.db_path:
        db_path = args.db_path
    else:
        db_path = None

    if args.ui:
        from determined.ui.ui_server import run_server
        run_server(db_path, port=args.port)
    else:
        if not db_path:
            parser.error("Provide db_path or --source <dir> when not using --ui.")
        run(db_path, verbose=args.verbose)
