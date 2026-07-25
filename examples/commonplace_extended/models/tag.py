from dataclasses import dataclass
from typing import Optional

TAG_SOURCES = ("manual", "llm")


@dataclass
class Tag:
    id: Optional[int]
    name: str
    source: str  # "manual" or "llm"

    def validate(self):
        if self.source not in TAG_SOURCES:
            raise ValueError(f"Invalid tag source: {self.source}")
        if not self.name or not self.name.strip():
            raise ValueError("Tag name cannot be empty")
