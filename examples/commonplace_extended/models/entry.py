from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

ENTRY_TYPES = ("url", "snippet", "note", "code")


@dataclass
class Entry:
    id: Optional[int]
    type: str
    content: str
    title: Optional[str]
    source_url: Optional[str]
    excerpt: Optional[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: list = field(default_factory=list)

    def validate(self):
        if self.type not in ENTRY_TYPES:
            raise ValueError(f"Invalid entry type: {self.type}")
        if not self.content or not self.content.strip():
            raise ValueError("Entry content cannot be empty")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "title": self.title,
            "source_url": self.source_url,
            "excerpt": self.excerpt,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }
