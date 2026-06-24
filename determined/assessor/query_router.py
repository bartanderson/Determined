# tools/analysis/assessor/query_router.py
#
# Assessor-owned query routing layer (Phase 3 boundary completion).
# Moved here from api/oracle_router.py so the query path is fully Assessor-owned
# and has no dependency on engine-layer objects (GraphBundle, GraphEdge).
#
# Public interface:
#   route_query(text, oracle, logger=None, seeds=None) -> RouteResult
#
# oracle must provide:
#   oracle.get_edge_maps()          -> (forward_dict, reverse_dict)
#   oracle.discover_seed_symbols()  -> list[str]
#   oracle.builtin_symbols()        -> set

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from determined.oracle.symbol_noise import is_noise_symbol


# =========================================================
# ROUTE RESULT CONTRACT (STABLE OUTPUT SHAPE)
# =========================================================

@dataclass
class RouteResult:
    intent: str
    seed_symbols: List[str]
    expanded_symbols: List[str]
    execution_plan: Dict[str, Any]
    raw_query: str
    edge_count: int = 0


# =========================================================
# INTENT DETECTION
# =========================================================

def _detect_intent(text: str) -> str:
    t = text.lower()

    if "what depends" in t or "impact" in t:
        return "impact_query"

    if "what uses" in t or "used by" in t:
        return "reverse_query"

    if "what does" in t or "surface" in t:
        return "surface_query"

    if any(k in t for k in ("broken", "failing", "crashed", "erroring", "not working")) or \
       ("why" in t and any(k in t for k in ("fail", "wrong", "error", "bug", "crash", "exception"))):
        return "debug_query"

    if "mutates" in t or "who mutates" in t or \
       ("modif" in t and any(k in t for k in ("where", "what", "who"))) or \
       ("changes" in t and any(k in t for k in ("where", "what", "who"))):
        return "mutation_query"

    if "purpose" in t or "why does" in t or "why is" in t or "role of" in t or "what role" in t or "what kind of" in t:
        return "role_query"

    return "general_query"


# =========================================================
# PRIMITIVE SELECTION
# =========================================================

def _select_primitives(intent: str) -> List[str]:
    if intent == "impact_query":
        return ["impact", "context"]
    if intent == "reverse_query":
        return ["impact"]
    if intent == "surface_query":
        return ["surface", "context"]
    if intent == "role_query":
        return ["role"]
    if intent == "debug_query":
        return ["findings", "impact", "context"]
    if intent == "mutation_query":
        return ["mutations", "impact", "context"]
    return ["context", "surface", "impact"]


# =========================================================
# EXECUTION PLAN BUILDER
# =========================================================

def _build_plan(symbols: List[str], primitives: List[str], trace: Dict[str, Any] = None) -> Dict[str, Any]:
    return {
        "symbols": symbols,
        "primitives": primitives,
        "trace": trace or {}
    }


# =========================================================
# GRAPH EXPANSION (works on forward/reverse dicts, no GraphBundle)
# =========================================================

def _is_valid_symbol(sym: str, builtin_symbols=frozenset()) -> bool:
    return not is_noise_symbol(sym, builtin_symbols)


def _route_expand(forward: dict, reverse: dict, seeds: List[str], intent: str, builtin_symbols=frozenset()) -> dict:
    visited = set()
    expanded = set()

    trace = {
        "seed_paths": {},
        "edges": {}
    }

    def add(node, reason, source=None):
        if not node:
            return
        if node not in visited:
            visited.add(node)
            expanded.add(node)
        trace["seed_paths"].setdefault(node, []).append(reason)
        if source:
            trace["edges"].setdefault(source, []).append(node)

    def expand_forward(node, depth=1):
        if depth <= 0:
            return
        for n in forward.get(node, []):
            if not _is_valid_symbol(n, builtin_symbols):
                continue
            add(n, f"forward:{node}", source=node)
            expand_forward(n, depth - 1)

    def expand_reverse(node, depth=1):
        if depth <= 0:
            return
        for n in reverse.get(node, []):
            if not _is_valid_symbol(n, builtin_symbols):
                continue
            add(n, f"reverse:{node}", source=node)
            expand_reverse(n, depth - 1)

    # Intent budget calibration locked in by test_intent_budget_calibration.py
    intent_budget = {
        "surface_query":  {"forward_depth": 2, "reverse": False, "reverse_depth": 0},
        "impact_query":   {"forward_depth": 0, "reverse": True,  "reverse_depth": 2},
        "reverse_query":  {"forward_depth": 0, "reverse": True,  "reverse_depth": 1},
        "general_query":  {"forward_depth": 1, "reverse": True,  "reverse_depth": 1},
        "role_query":     {"forward_depth": 0, "reverse": False, "reverse_depth": 0},
        "debug_query":    {"forward_depth": 0, "reverse": True,  "reverse_depth": 2},
        "mutation_query": {"forward_depth": 1, "reverse": True,  "reverse_depth": 1},
    }

    budget = intent_budget.get(intent, intent_budget["general_query"])

    for s in seeds:
        add(s, "seed")
        if budget["forward_depth"] >= 1:
            expand_forward(s, depth=budget["forward_depth"])
        if budget["reverse"]:
            expand_reverse(s, depth=budget["reverse_depth"])

    node_reasons = {}
    for node, reasons in trace["seed_paths"].items():
        if "seed" in reasons:
            node_reasons[node] = "direct seed match"
        else:
            forward_sources = [r.split(":", 1)[1] for r in reasons if r.startswith("forward:")]
            reverse_sources = [r.split(":", 1)[1] for r in reasons if r.startswith("reverse:")]
            parts = []
            if forward_sources:
                parts.append(f"reachable from {', '.join(forward_sources[:2])}")
            if reverse_sources:
                parts.append(f"depends on {', '.join(reverse_sources[:2])}")
            node_reasons[node] = "; ".join(parts) if parts else "included via traversal"

    trace["node_reasons"] = node_reasons

    return {"nodes": list(expanded), "trace": trace}


def _score_symbol(symbol: str, seeds: List[str], forward: dict, reverse: dict) -> float:
    score = 0.0
    if symbol in seeds:
        score += 5.0
    for s in seeds:
        if s.split(".")[-1] in symbol:
            score += 2.0
    degree = len(forward.get(symbol, set())) + len(reverse.get(symbol, set()))
    score += min(degree * 0.1, 3.0)
    return score


def _prune(symbols: List[str], seeds: List[str], forward: dict, reverse: dict, limit: int = 40) -> List[str]:
    scored = [(  _score_symbol(sym, seeds, forward, reverse), sym) for sym in symbols]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [s for _, s in scored[:limit]]


# =========================================================
# MAIN ROUTER ENTRYPOINT (Assessor-owned)
# =========================================================

def route_query(text: str, oracle, logger=None, seeds: Optional[List[str]] = None) -> RouteResult:
    """
    Assessor-owned query router. Takes an oracle (DBOracle or compatible duck-type)
    instead of raw graph + fn params. No dependency on GraphBundle or graph engine.

    oracle must provide get_edge_maps(), discover_seed_symbols(), builtin_symbols().

    seeds: if provided, skip seed discovery (see api/oracle_router.py docstring).
    logger: optional callable(str) for observability output.
    """
    intent = _detect_intent(text)
    builtin_syms = oracle.builtin_symbols()

    if seeds is None:
        seeds = oracle.discover_seed_symbols(text, limit=20)

    forward, reverse = oracle.get_edge_maps()
    edge_count = sum(len(v) for v in forward.values())

    expand_result = _route_expand(forward, reverse, seeds, intent, builtin_symbols=builtin_syms)

    expanded = expand_result["nodes"]
    expansion_trace = expand_result["trace"]

    trace = {
        "seeds": seeds,
        "intent": intent,
        "expanded": expanded,
        "expansion_trace": expansion_trace,
        "seed_paths": expansion_trace.get("seed_paths", {}),
        "node_reasons": expansion_trace.get("node_reasons", {}),
        "edges": expansion_trace.get("edges", {}),
    }

    filtered = _prune(expanded, seeds, forward, reverse)
    primitives = _select_primitives(intent)
    plan = _build_plan(filtered, primitives, trace)

    if logger:
        logger(f"\n=== ROUTE METRICS ===")
        logger(f"intent: {intent}")
        logger(f"seed_count: {len(seeds)}")
        logger(f"expanded_count: {len(expanded)}")
        logger(f"filtered_count: {len(filtered)}")
        logger(f"removed_count: {len(expanded) - len(filtered)}")

    return RouteResult(
        intent=intent,
        seed_symbols=seeds,
        expanded_symbols=expanded,
        execution_plan=plan,
        raw_query=text,
        edge_count=edge_count,
    )
