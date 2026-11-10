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
    """Протокол джерела поточного часу для підтримки керованого годинника в тестах."""

    def now(self) -> datetime:
        """Повертає поточний момент часу з інформацією про часовий пояс."""
        ...


class SystemClock:
    """Реалізація годинника реального часу на основі системного годинника ОС (UTC)."""

    def now(self) -> datetime:
        """Повертає поточний час ОС в UTC."""
        return datetime.now(timezone.utc)


class Mailer(Protocol):
    """Протокол надсилання службових листів з одноразовими токенами."""

    def send(self, to: str, kind: str, token: str) -> None:
        """kind: `email_confirmation` (REQ-F-016) або `password_reset` (REQ-F-047)."""


class FileOutbox:
    """Пошта для локальної розробки: листи записуються у файл JSON Lines, а не надсилаються."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def send(self, to: str, kind: str, token: str) -> None:
        """Записує факт надсилання листа з токеном у файл вихідної пошти."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "kind": kind, "token": token}, ensure_ascii=False) + "\n")
