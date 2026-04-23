from __future__ import annotations

import logging
from pathlib import Path


class SecretFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self.secrets = [secret for secret in secrets if secret]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secrets:
            if secret in message:
                message = message.replace(secret, f"...{secret[-4:]}")
        record.msg = message
        record.args = ()
        if not hasattr(record, "step"):
            record.step = "-"
        return True


def configure_logging(log_path: Path, level: str, secrets: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s step=%(step)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    stream_handler.addFilter(SecretFilter(secrets))
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.addFilter(SecretFilter(secrets))
    file_handler.setFormatter(formatter)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)


def get_logger(name: str, *, step: str) -> logging.LoggerAdapter[logging.Logger]:
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, extra={"step": step})
