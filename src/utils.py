from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def round_display(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}".rstrip("0").rstrip(".")
