# tools/analysis/engine/engine_logger.py

from pathlib import Path
# tools/analysis/engine/engine_log.py

from pathlib import Path
from typing import Optional

class EngineLogger:
    def __init__(self, enabled: bool, path: Path):
        self.enabled = enabled
        self.path = path
        self._buffer = []

    def write(self, *args):
        if not self.enabled:
            return

        msg = " ".join(str(a) for a in args)
        self._buffer.append(msg)

    def flush(self):
        if not self.enabled:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._buffer))