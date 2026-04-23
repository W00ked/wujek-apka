from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    def synthesize(self, text: str, output_path: Path) -> Path:
        """Generate one audio file for the provided text."""
