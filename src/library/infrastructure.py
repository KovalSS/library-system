"""Зовнішні залежності застосунку, які можна підмінити в тестах: годинник, пошта, головний адміністратор."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ChiefAdmin:
    """Попередньо створений головний адміністратор (REQ-F-009)."""
    email: str
    password: str
    full_name: str = "Головний адміністратор"


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class Mailer(Protocol):
    def send(self, to: str, kind: str, token: str) -> None:
        """kind: `email_confirmation` (REQ-F-016) або `password_reset` (REQ-F-047)."""


class FileOutbox:
    """Пошта для локальної розробки: листи записуються у файл, а не надсилаються."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def send(self, to: str, kind: str, token: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "kind": kind, "token": token}, ensure_ascii=False) + "\n")
