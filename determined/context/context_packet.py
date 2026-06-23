# tools/analysis/context/context_packet.py

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ContextPacket:
    file_path: str
    summary: Dict[str, Any]

    key_functions: List[str]
    key_classes: List[str]

    dependencies: List[str]
    referenced_symbols: List[str]