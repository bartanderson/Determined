# tools/analysis/ingestion/build_file_analysis.py

from __future__ import annotations

import ast
from typing import Optional

from determined.types import FileAnalysis
from determined.extractors import (
    extract_functions,
    extract_classes,
    extract_imports,
    extract_mutations,
    extract_behavioral_contracts,
)


def build_file_analysis(
    file_path: str,
    source: str,
    tree: ast.AST,
    bucket
) -> Optional[FileAnalysis]:
    """
    SINGLE SOURCE OF TRUTH ASSEMBLER.

    Only place where FileAnalysis is constructed.
    """

    functions = extract_functions(bucket)
    classes = extract_classes(bucket)
    imports = extract_imports(bucket)
    mutations = extract_mutations(bucket)
    contracts = extract_behavioral_contracts(bucket, source)

    return FileAnalysis(
        file_path=file_path,
        functions=functions,
        classes=classes,
        imports=imports,
        mutations=mutations,
        behavioral_contracts=contracts,
        metadata={
            "line_count": len(source.splitlines()),
            "role": None,  # keep in utils if needed, but DO NOT recompute elsewhere
            "is_hot": bool(mutations or contracts),
        },
    )