from __future__ import annotations

from pathlib import Path


class PipelineError(Exception):
    """Base pipeline error with step metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: int = 1,
        step: str,
        path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.step = step
        self.path = path


class ConfigurationError(PipelineError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=2, step="config")


class ValidationError(PipelineError):
    def __init__(self, message: str, *, step: str = "validation") -> None:
        super().__init__(message, code=3, step=step)
