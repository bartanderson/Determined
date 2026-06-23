# tools/analysis/api/query_reasoning.py

from determined.oracle.db_oracle import (
    context,
    surface,
    influence
)

def query_reasoning(graph, intent: dict):
    op = intent["intent"]
    symbol = intent["target"]

    if op == "context":
        return context(graph, symbol)

    if op == "surface":
        return surface(graph, symbol, depth=intent.get("depth", 1))

    if op == "influence":
        return influence(graph, symbol, depth=intent.get("depth", 1))

    raise ValueError(f"Unknown intent: {op}")