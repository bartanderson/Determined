# tools/analysis/shared/types.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal

from determined.identity.symbol_identity import SymbolIdentity



# ----------------------------
# Core file-level representation
# ----------------------------

@dataclass
class FilePath:
    """
    Normalized representation of a file path within a project.
    Always stored as relative-to-root, forward-slash separated.
    """
    path: str


@dataclass
class FileMetadata:
    """
    Non-semantic metadata about a file.
    """
    line_count: int
    is_hot: bool = False
    role: Optional[str] = None


# ----------------------------
# Code structure primitives
# ----------------------------

@dataclass
class FunctionRepresentation:
    """
    Fully normalized representation of a function definition.
    """
    name: str
    line_number: int
    arguments: List[str] = field(default_factory=list)
    param_types: Dict[str, str] = field(default_factory=dict)  # param_name -> type_str
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_stub: bool = False
    decorators: List[str] = field(default_factory=list)


@dataclass
class ClassRepresentation:
    """
    Fully normalized representation of a class definition.
    """
    name: str
    line_number: int
    methods: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ImportRepresentation:
    """
    Normalized import statement representation.
    """
    module: str
    import_type: str  # "import" | "from_import"
    line_number: int

@dataclass
class SymbolReference:
    """
    Bridge representation:
    - preserves legacy string-based routing (callee)
    - optionally carries SymbolIdentity for future pipeline stages
    """

    caller: str
    callee: str
    line_number: int

    # A → B bridge field (non-breaking addition)
    identity: Optional[SymbolIdentity] = None

    bucket: Optional[str] = None
    resolved: bool = False  # True = callee derived from type annotation, not heuristic

@dataclass
class ClassAttribute:
    """Type-annotated or constructor-inferred attribute from a class __init__."""
    class_name: str
    attribute: str
    inferred_type: str  # e.g. 'Foo' from self.x = Foo() or self.x: Foo


@dataclass
class SymbolClassification:
    origin: Literal["project", "builtin", "stdlib", "external"]
    binding: Literal["function", "method", "class", "attribute", "module", "unknown"]
    resolution: Literal["static", "dynamic", "unresolved"]


# ----------------------------
# Behavioral analysis layer
# ----------------------------

@dataclass
class BehavioralContract:
    """
    Extracted behavioral expectations from code + docstrings.
    """
    function_name: str
    line_number: int
    description: str = ""
    side_effects: List[str] = field(default_factory=list)
    raises: List[str] = field(default_factory=list)
    testable_behaviors: List[str] = field(default_factory=list)
    complexity_score: int = 0


@dataclass
class MutationEvent:
    """
    Represents a detected state mutation in code.
    """
    line_number: int
    target: str
    operation: str
    raw_expression: str
    intent: str = ""


# ----------------------------
# File-level aggregation
# ----------------------------

@dataclass
class FileAnalysis:
    """
    Full normalized output of ingestion + representation phase.
    """
    file_path: str
    metadata: FileMetadata

    functions: List[FunctionRepresentation] = field(default_factory=list)
    classes: List[ClassRepresentation] = field(default_factory=list)
    imports: List[ImportRepresentation] = field(default_factory=list)
    symbol_references: List[SymbolReference] = field(default_factory=list)
    class_attributes: List["ClassAttribute"] = field(default_factory=list)

    runtime_bindings: dict[str, str] = field(default_factory=dict)
    
    behavioral_contracts: List[BehavioralContract] = field(default_factory=list)
    mutations: List[MutationEvent] = field(default_factory=list)

    phase_violations: List[Any] = field(default_factory=list)