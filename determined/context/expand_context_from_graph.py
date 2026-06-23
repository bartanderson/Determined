# tools/analysis/context/expand_context_from_graph.py

from typing import List

from determined.shared.types import FileAnalysis
from determined.graph.dependency_graph import DependencyGraph
from determined.representation.context_bundle import ContextBundle


def expand_context_from_graph(
    target_file: str,
    analyses: List[FileAnalysis],
    graph: DependencyGraph,
) -> ContextBundle:

    lookup = {a.file_path: a for a in analyses}

    root = lookup.get(target_file)
    if not root:
        raise ValueError(f"Unknown file: {target_file}")

    imported_modules = graph.imports.get(target_file, set())

    imports = [
        a
        for a in analyses
        if any(mod in a.file_path for mod in imported_modules)
    ]

    dependents = [
        lookup[f]
        for f in graph.dependents.get(target_file, set())
        if f in lookup
    ]

    return ContextBundle(
        root=root,
        imports=imports,
        dependents=dependents,
    )