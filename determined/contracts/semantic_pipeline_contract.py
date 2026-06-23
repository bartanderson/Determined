from dataclasses import dataclass
from typing import Literal, Set


SymbolBucket = Literal[
    "project",
    "builtin",
    "stdlib",
    "runtime",
    "external_lib",
    "external_unknown",
    "classification_gap",
    "unresolved_qualified_reference",
    "unknown",
]


@dataclass(frozen=True)
class SemanticPipelineContract:
    """
    HARD SYSTEM CONTRACT (v1 — DO NOT SOFTEN)

    This is the single authoritative definition of:
    - allowed classification outputs
    - evaluation priority semantics
    - structural invariants of the pipeline
    """

    # ----------------------------
    # CLASSIFICATION VALID SPACE
    # ----------------------------
    ALLOWED_BUCKETS: Set[str] = frozenset({
        "project",
        "builtin",
        "stdlib",
        "runtime",
        "external_lib",
        "external_unknown",
        "classification_gap",
        "unresolved_qualified_reference",
        "unknown",
    })

    # ----------------------------
    # PRIORITY ORDER (STRICT)
    # ----------------------------
    PRIORITY_ORDER: tuple[str, ...] = (
        "project",
        "builtin",
        "stdlib",
        "runtime",
        "unknown",
    )

    # ----------------------------
    # HARD RULES
    # ----------------------------

    @staticmethod
    def validate_bucket(bucket: str) -> None:
        if bucket not in SemanticPipelineContract.ALLOWED_BUCKETS:
            raise AssertionError(f"invalid bucket emitted: {bucket}")

    @staticmethod
    def enforce_priority(current: str, candidate: str) -> str:
        """
        Deterministic resolution rule:
        lower index in PRIORITY_ORDER wins.
        """
        order = SemanticPipelineContract.PRIORITY_ORDER
        return candidate if order.index(candidate) < order.index(current) else current

    @staticmethod
    def is_project(bucket: str) -> bool:
        return bucket == "project"

    @staticmethod
    def is_runtime(bucket: str) -> bool:
        return bucket == "runtime"

    @staticmethod
    def is_builtin(bucket: str) -> bool:
        return bucket == "builtin"