# tools/analysis/graph/build_dependency_graph.py

from __future__ import annotations

from typing import List, Dict, Any
from determined.graph.module_resolution import (
    module_name_from_file_path,
    file_path_from_module_name,
)


def build_dependency_graph(file_analyses: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build resolved file-to-file dependency edges from FileAnalysis objects.

    Output format:
        [
            {
                "from_file": "...",
                "to_file": "...",
                "module": "...",
            }
        ]
    """
    seen_edges = set()
    
    edges: List[Dict[str, str]] = []

    # Build quick lookup: module -> file
    module_to_file: Dict[str, str] = {}

    for analysis in file_analyses:
        file_path = analysis["file"]["file_path"]

        # NOTE: project_root is inferred implicitly from path structure
        module = module_name_from_file_path(
            file_path=file_path,
            project_root=_infer_root(file_path),
        )

        module_to_file[module] = file_path

    # Resolve dependencies
    for analysis in file_analyses:
        from_file = analysis["file"]["file_path"]
        imports = analysis.get("imports", [])

        for imp in imports:
            module = imp["module"]

            to_file = module_to_file.get(module)

            if to_file is None:
                continue

            to_file = module_to_file.get(module)

            if to_file is None:
                continue

            edge = (from_file, to_file)

            if edge in seen_edges:
                continue

            seen_edges.add(edge)

            edges.append({
                "from_file": from_file,
                "to_file": to_file,
                "module": module,
            })

    return edges


def _infer_root(file_path: str) -> str:
    """
    Minimal heuristic:
    assumes project root is everything up to 'tools'
    """
    normalized = file_path.replace("\\", "/")

    if "/tools/" in normalized:
        return normalized.split("/tools/")[0]

    # fallback: parent of file
    from pathlib import Path
    return str(Path(file_path).parent)