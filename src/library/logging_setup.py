"""Системний журнал (REQ-NF-005): JSON Lines у файл, окремо від аудит-логу (REQ-F-049).

Кожен запис містить часову мітку, рівень, джерело (ім'я логера), повідомлення та
`requestId` поточного запиту; для помилок - стек.
"""
import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

LOGGER_NAME = "library"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
            "requestId": request_id_var.get(),
        }
        if record.exc_info:
            entry["stack"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(log_file: Path) -> logging.Logger:
    """Налаштовує логер застосунку на запис у `log_file` (замінює попередні обробники)."""
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
