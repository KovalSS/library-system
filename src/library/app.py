"""Фабрика застосунку FastAPI.

Зовнішній інтерфейс визначає затверджений контракт `spec/openapi.yaml`;
маршрути додаються лише разом із тестами (TDD, SRS розд. 1.4).
"""
import logging
import os
import time
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from library.backup import DailyBackup
from library.db import Account, make_session_factory, to_db
from library.errors import install_error_handlers
from library.infrastructure import ChiefAdmin, Clock, FileOutbox, Mailer, SystemClock
from library.logging_setup import LOGGER_NAME, configure_logging, request_id_var
from library.routers import (accounts, audit_log, auth, catalog, fines, loans, notifications, readers,
                             recommendations, reports, reservations)
from library.security import DEFAULT_ITERATIONS, hash_password

DEFAULT_LOG_FILE = Path("var/log/library.log")
DEFAULT_DATABASE_URL = "sqlite:///var/library.db"
DEFAULT_BACKUP_DIR = Path("var/backups")
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "spec" / "openapi.yaml"

http_log = logging.getLogger(f"{LOGGER_NAME}.http")


def default_chief_admin() -> ChiefAdmin:
    """Отримує облікові дані головного адміністратора за замовчуванням або зі змінних середовища."""
    # Значення для локальної розробки; у розгортанні задаються змінними середовища.
    return ChiefAdmin(
        email=os.environ.get("LIBRARY_CHIEF_EMAIL", "chief@library.local"),
        password=os.environ.get("LIBRARY_CHIEF_PASSWORD", "Chief-Pass-2026"),
    )


def seed_chief_admin(sessions, chief: ChiefAdmin, clock: Clock, iterations: int) -> None:
    """Єдиний попередньо створений головний адміністратор (REQ-F-009)."""
    with sessions() as session:
        if session.scalar(select(Account).where(Account.role == "chief_admin")) is None:
            session.add(Account(email=chief.email, full_name=chief.full_name, role="chief_admin",
                                password_hash=hash_password(chief.password, iterations), created_at=to_db(clock.now())))
            session.commit()


def approved_contract() -> dict:
    """Затверджений контракт (API-GATE) для /openapi.json і /docs замість опису, згенерованого з коду.

    Адреса сервера в контракті — mock лаб. №4, тому публікується відносна адреса самого сервера.
    """
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return {**contract, "servers": [{"url": "/"}]}


def create_app(
    log_file: Path = DEFAULT_LOG_FILE,
    database_url: str = DEFAULT_DATABASE_URL,
    chief_admin: ChiefAdmin | None = None,
    mailer: Mailer | None = None,
    clock: Clock | None = None,
    password_iterations: int = DEFAULT_ITERATIONS,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
) -> FastAPI:
    """Фабрика створення екземпляра застосунку FastAPI з повною конфігурацією інфраструктури."""
    configure_logging(log_file)
    app = FastAPI(title="Library System API", version="1.0.0")
    app.state.database_url = database_url
    app.state.chief_admin = chief_admin or default_chief_admin()
    app.state.mailer = mailer or FileOutbox(Path("var/mail/outbox.jsonl"))
    app.state.clock = clock or SystemClock()
    app.state.password_iterations = password_iterations
    app.state.backup_dir = Path(backup_dir)
    if database_url.startswith("sqlite:///"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    app.state.sessions = make_session_factory(database_url)
    seed_chief_admin(app.state.sessions, app.state.chief_admin, app.state.clock, password_iterations)
    app.state.backup = DailyBackup(database_url, backup_dir)

    published_contract = approved_contract()
    app.openapi = lambda: published_contract
    install_error_handlers(app)
    for module in (auth, accounts, readers, catalog, loans, reservations, fines, reports, recommendations,
                   notifications, audit_log):
        app.include_router(module.router)

    @app.middleware("http")
    async def log_every_request(request: Request, call_next):
        token = request_id_var.set(f"req-{uuid.uuid4().hex[:12]}")
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                http_log.exception("Необроблена помилка: %s %s", request.method, request.url.path)
                response = JSONResponse(
                    status_code=500,
                    content={"message": "Внутрішня помилка сервера.", "requestId": request_id_var.get()},
                )
            elapsed_ms = (time.perf_counter() - started) * 1000
            http_log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
            return response
        finally:
            request_id_var.reset(token)

    return app
