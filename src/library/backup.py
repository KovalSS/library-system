"""Автоматичне резервне копіювання бази не рідше разу на добу (REQ-NF-002).

Копія робиться при першому зверненні до системи, якщо остання старша за добу:
без звернень дані не змінюються, тож фонове завдання не потрібне.
"""
import logging
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from library.logging_setup import LOGGER_NAME

BACKUP_INTERVAL = timedelta(days=1)
NAME_FORMAT = "library-%Y%m%dT%H%M%S.db"

backup_log = logging.getLogger(f"{LOGGER_NAME}.backup")


class DailyBackup:
    """Менеджер щодобового резервного копіювання бази даних SQLite (REQ-NF-002).

    Копія створюється онлайн через механізм sqlite3.backup() без блокування читачів.
    """

    def __init__(self, database_url: str, backup_dir: Path):
        self.database = Path(database_url.removeprefix("sqlite:///")) if database_url.startswith("sqlite:///") else None
        self.backup_dir = Path(backup_dir)
        self.lock = threading.Lock()
        self.last = self._latest_existing()

    def _latest_existing(self) -> datetime | None:
        """Знаходить часову мітку найсвіжішої резервної копії в теці бекапів."""
        moments = []
        for path in self.backup_dir.glob("library-*.db") if self.backup_dir.exists() else []:
            try:
                moments.append(datetime.strptime(path.name, NAME_FORMAT))
            except ValueError:
                continue
        return max(moments, default=None)

    def run_if_due(self, now: datetime) -> None:
        """Створює нову резервну копію, якщо минуло більше доби з попередньої."""
        if self.database is None:
            return
        with self.lock:
            if self.last is not None and now - self.last < BACKUP_INTERVAL:
                return
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            target = self.backup_dir / now.strftime(NAME_FORMAT)
            # `with sqlite3.connect()` не закриває з'єднання, тому — closing().
            with closing(sqlite3.connect(self.database)) as source, closing(sqlite3.connect(target)) as copy:
                source.backup(copy)            # цілісна копія навіть під час роботи бази (у тому числі WAL)
            self.last = now
            backup_log.info("Резервну копію бази створено: %s", target)
