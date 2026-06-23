# tools/analysis/representation/context_bundle.py

from dataclasses import dataclass
from typing import List

from determined.shared.types import FileAnalysis


@dataclass
class ContextBundle:
    root: FileAnalysis
    imports: List[FileAnalysis]
    dependents: List[FileAnalysis]