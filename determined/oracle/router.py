# tools/analysis/oracle/router.py

from typing import Dict, Any

VALID_INTENTS = {"context", "surface", "influence"}


def route_question(llm_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts structured LLM output and validates it into a DB oracle intent.
    """

    intent = llm_output.get("intent")
    target = llm_output.get("target")
    depth = llm_output.get("depth", 1)

    if intent not in VALID_INTENTS:
        raise ValueError(f"Invalid intent: {intent}")

    if not isinstance(target, str) or not target:
        raise ValueError("Invalid target")

    if not isinstance(depth, int) or depth < 1:
        depth = 1

    return {
        "intent": intent,
        "target": target,
        "depth": depth,
    }