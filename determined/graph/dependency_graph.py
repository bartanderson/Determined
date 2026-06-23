# tools/analysis/graph/dependency_graph.py

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class DependencyGraph:
    # file → modules it imports
    imports: Dict[str, Set[str]] = field(default_factory=dict)

    # module → files that import it
    dependents: Dict[str, Set[str]] = field(default_factory=dict)