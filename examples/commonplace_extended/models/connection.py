from dataclasses import dataclass
from typing import Optional

CONNECTION_TYPES = ("related", "contradicts", "extends", "source")


@dataclass
class Connection:
    id: Optional[int]
    from_entry_id: int
    to_entry_id: int
    relation: str  # one of CONNECTION_TYPES
    note: Optional[str] = None

    # DESIGN TENSION: directionality is not enforced. A->B and B->A can both
    # exist with the same relation type, which may or may not be intended.
    # Determined: ask "should connections be symmetric?"

    def validate(self):
        if self.relation not in CONNECTION_TYPES:
            raise ValueError(f"Invalid relation type: {self.relation}")
        if self.from_entry_id == self.to_entry_id:
            raise ValueError("Cannot connect an entry to itself")
