# tools/analysis/truth/query_ast.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union, Any

## 2.2 SELECT NODE

@dataclass(frozen=True)
class Select:
    view: str
    metric: Optional[str] = None
    filter: Optional["Filter"] = None

    def __init__(self, view: str, metric: Optional[str] = None, filter: Optional["Filter"] = None):
        object.__setattr__(self, "view", view)
        object.__setattr__(self, "metric", metric)
        object.__setattr__(self, "filter", filter)

## 2.3 FILTER (SELECT MODIFIER ONLY — NOT A ROOT NODE)
##
## Filter is not executable on its own.
## It only exists as Select.filter and is applied during execution.
## This is part of the deterministic model (no standalone predicate nodes).
@dataclass(frozen=True)
class Filter:
    key: str
    op: str
    value: Any

# Examples (applied as Select modifiers only):
#
# Select("STRUCTURE", filter=Filter("caller", "==", "determined"))
# Select("STRUCTURE", filter=Filter("edges", ">", 10))
# Select("INTEGRITY", filter=Filter("errors", ">", 0))

## 2.4 COMBINATION NODE

@dataclass(frozen=True)
class Combine:
    left: "Query"
    right: "Query"


## 2.5 FULL QUERY NODE
Query = Union[Select, Filter, Combine]