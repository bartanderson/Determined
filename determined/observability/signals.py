# tools/analysis/observability/signals.py

from dataclasses import dataclass
from typing import Any, Literal


SignalClass = Literal[
    "structure",
    "propagation",
    "invariant",
]


@dataclass
class Signal:
    name: str
    value: Any
    unit: str = "count"
    stage: str = ""
    signal_class: SignalClass = "structure"