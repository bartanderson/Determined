# Canned reasoning lenses for the investigation clue board (RM43).
# Each lens composes a structured prompt from clue summaries + optional DB context.
# UI reads LENS_CATALOG via /api/reasoning_lenses to render the selector buttons.

LENS_CATALOG = [
    {
        "id": "next_action",
        "name": "Next action",
        "description": "What should I work on next?",
        "prompt_template": (
            "Given these investigation findings:\n{clues}\n\n"
            "Identify the single most valuable next action. "
            "Consider: which item is unblocked, has high connectivity to other issues, "
            "and has the shortest path to closure? "
            "Respond with:\n"
            "**Finding:** one sentence naming the top next action\n"
            "**Evidence:** 2-3 clue refs that support this\n"
            "**Next step:** one concrete, specific action to take"
        ),
    },
    {
        "id": "blast_radius",
        "name": "Blast radius",
        "description": "If I change the subject(s) in my clues, what breaks?",
        "prompt_template": (
            "Given these investigation findings:\n{clues}\n\n"
            "For each subject (function, file, or module) mentioned, identify blast radius: "
            "callers, cross-layer boundaries (HTTP, socket, thread), and design violations "
            "that could be triggered by a change. "
            "Respond with:\n"
            "**Finding:** summary of highest-risk change\n"
            "**Evidence:** which clues indicate the most coupling\n"
            "**Next step:** the specific query to run to confirm the blast radius "
            "(e.g. blast_radius('<symbol>') or find_callers('<function>'))"
        ),
    },
    {
        "id": "open_questions",
        "name": "Open questions",
        "description": "What don't I know yet?",
        "prompt_template": (
            "Given these investigation findings:\n{clues}\n\n"
            "Identify what the current clue board cannot answer: "
            "missing edges, unresolved names, zero-result queries, or gaps between clues. "
            "Respond with:\n"
            "**Finding:** the most critical unknown\n"
            "**Evidence:** which clues expose the gap\n"
            "**Next step:** the targeted next query to fill in the gap "
            "(be specific: tool name + argument)"
        ),
    },
    {
        "id": "convergence",
        "name": "Convergence check",
        "description": "Are these clues pointing at the same root cause?",
        "prompt_template": (
            "Given these investigation findings:\n{clues}\n\n"
            "Look for shared functions, shared callers, shared design violations, "
            "or shared modules across the clues. Cluster clues that point at the same root cause. "
            "Respond with:\n"
            "**Finding:** are these clues convergent (same root) or divergent (different issues)?\n"
            "**Evidence:** the specific overlap or lack thereof\n"
            "**Next step:** name the root pattern (if convergent) or the distinct threads (if divergent)"
        ),
    },
    {
        "id": "not_ready",
        "name": "Not ready",
        "description": "What is NOT ready to work on yet?",
        "prompt_template": (
            "Given these investigation findings:\n{clues}\n\n"
            "Identify items with unresolved prerequisites, missing edges, incomplete data, "
            "or dependencies on work not yet done. "
            "Respond with:\n"
            "**Finding:** the item that is most blocked\n"
            "**Evidence:** clue refs showing the unresolved dependency\n"
            "**Next step:** what must be completed first before this item can proceed"
        ),
    },
]


def get_lens(lens_id: str) -> dict | None:
    return next((l for l in LENS_CATALOG if l["id"] == lens_id), None)
